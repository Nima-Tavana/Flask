import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    user_id = session["user_id"]

    stock = db.execute(
        "SELECT symbol, name, price, SUM(shares) as Tshares FROM trans WHERE user_id = ? GROUP BY symbol", user_id)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[
        0]["cash"]

    TOTAL = cash
    for s in stock:
        TOTAL += s["price"] * s["Tshares"]

    return render_template("index.html", stock=stock, cash=cash, usd=usd, total=TOTAL)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        sym = request.form.get("symbol").upper()
        itm = lookup(sym)
        if not sym:
            return apology("You can't leave this field empty!")
        elif not itm:
            return apology("You must enter a valid input!")

        try:
            shr = int(request.form.get("shares"))
        except:
            return apology("Input must be an integer")

        if shr < 1:
            return apology("input must be positive")

        user_id = session["user_id"]
        money = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[
            0]["cash"]

        itemprice = itm["price"]
        itemname = itm["name"]
        totalprice = itemprice * shr

        if money < totalprice:
            return apology("You don't have enough credit!")
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?",
                       money - totalprice, user_id)
            db.execute("INSERT INTO trans (user_id, name, shares, price, type, symbol) VALUES(?, ?, ?, ?, ?, ?)",
                       user_id, itemname, shr, itemprice, 'buy', sym)

        return redirect('/')
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    trans = db.execute(
        "SELECT type, symbol, price, shares, time FROM trans WHERE user_id = ?", user_id)

    return render_template("history.html", trans=trans, usd=usd)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Please enter a username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Please enter a password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("Username and/or password are/is invalid", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        sym = request.form.get('symbol')
        if not sym:
            return apology("Input can't be empty!")

        stock = lookup(sym)
        if not stock:
            return apology("Selected stock is invalid!")

        return render_template("quoted.html", stock=stock, uf=usd)

    else:
        return render_template('quote.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if (request.method == "POST"):
        username = request.form.get('username')
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')

        if not username:
            return apology('Username can not be empty!')
        elif not password:
            return apology('Password can not be empty!')
        elif not confirmation:
            return apology('You must confirm your password!')

        if password != confirmation:
            return apology('Incorrect!')

        hash = generate_password_hash(password)

        try:
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
            return redirect('/')
        except:
            return apology('It is used before!')
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        if shares < 1:
            return apology("You must enter a positive number!")
        itemPrice = lookup(symbol)["price"]
        itemName = lookup(symbol)["name"]
        price = shares * itemPrice

        so = db.execute(
            "SELECT shares FROM trans WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)[0]["shares"]

        if so < shares:
            return apology("You don't have enough amount of share!")

        cc = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[
            0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?",
                   cc + price, user_id)
        db.execute("INSERT INTO trans (user_id, name, shares, price, type, symbol) VALUES (?, ?, ?, ?, ?, ?)",
                   user_id, itemName, -shares, itemPrice, "sell", symbol)

        return redirect('/')
    else:
        sym = db.execute(
            "SELECT symbol FROM trans WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols=sym)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
