# --------------------------- Beguin of the code provided by CS50x --------------------------------------------
import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
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

# -------------------------------- End of the code provided by CS50x ------------------------------------------

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Look up the current user
    user = db.execute("SELECT * FROM users WHERE id=:user_id", user_id=session["user_id"])

    # Look up the user's stocks
    stocks = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id=:user_id GROUP BY symbol HAVING total_shares > 0",
                        user_id=session["user_id"])

    # Gather all the user's quotes (stock's symbol, stock's name, stock's current price)
    quotes = []

    # Look up the current price of the user's stocks
    for row in stocks:
        tmp = lookup(row["symbol"])
        quote = {
            "symbol": tmp["symbol"],
            "name": tmp["name"],
            "price": tmp["price"],
            "shares": row["total_shares"],
            "total": tmp["price"] * row["total_shares"]
        }
        quotes.append(quote)

    # Sum all the user's stocks prices
    total = 0
    for row in quotes:
        total += row["total"]

    total += user[0]["cash"]

    # Format the quote's values into a usd string pattern
    for row in quotes:
        row["price"] = usd(row["price"])
        row["total"] = usd(row["total"])

    return render_template("portfolio.html", total=usd(total), quotes=quotes, cash_remain=usd(user[0]["cash"]))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # Check if the symbol is valid
        if quote == None:
            return apology("Invalid symbol")

        # Check if the quantitie of shares is not an integer
        try:
            shares = int(request.form.get("shares"))

        except:
            return apology("Invalid number of shares")

        # Check if the quantitie of shares is greater than 0
        if not shares > 0:
            return apology("Invalid number of shares")

        # Query the user from the database
        user = db.execute("SELECT * FROM users WHERE id=:user_id", user_id=session["user_id"])

        # Keep track of the remaining user's cash
        cash_remain = user[0]["cash"]

        # Transation's total value
        total_value = quote["price"] * shares

        # Check if the user has enough funds in the wallet
        if total_value > cash_remain:
            return apology("Not enough funds in the wallet")

        # Insert a new transaction into the database linked to the current user
        db.execute("INSERT INTO transactions (user_id, symbol, name, shares, price, total_price) VALUES (:user_id, :symbol, :name, :shares, :price, :total_price)",
                   user_id=session["user_id"], symbol=quote["symbol"], name=quote["name"], shares=shares, price=quote["price"], total_price=quote["price"]*shares)

        # Update the user's cash
        db.execute("UPDATE users SET cash=cash - :value WHERE id=:user_id",
                   value=total_value, user_id=session["user_id"])

        # Highlight a Bought message
        flash("Bought")

        # Redirect the page to the index page, avoind the form to resend all the informations into the database
        return redirect(url_for("index"))

    else:
        return render_template("buy.html")


@app.route("/portfolio")
@login_required
def portfolio():
    """Render the portfolio template"""
    user_updated = db.execute("SELECT * FROM users JOIN transactions ON users.id=transactions.user_id WHERE users.id=:user_id",
                              user_id=session["user_id"])

    return render_template("portfolio.html", user=user_updated)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Look up in the data base for all the user's transactions
    transactions = db.execute("SELECT * FROM users JOIN transactions ON users.id=transactions.user_id WHERE users.id=:user_id",
                              user_id=session["user_id"])

    transactions_formatted = []

    for row in transactions:
        transaction = {
            "symbol": row["symbol"],
            "shares": row["shares"],
            "price": row["price"],
            "time": row["date"]
        }
        transactions_formatted.append(transaction)

    return render_template("history.html", transactions=transactions_formatted)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
        symbol = request.form.get("symbol").upper()
        symbol_look = lookup(symbol)
        # Check the symbol
        if symbol_look != None:
            return render_template("quoted.html", quote=symbol_look, price=usd(symbol_look["price"]))

        else:
            return apology("Invalid Symbol")

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    render_template("register.html")

    # New registrant
    registrant = {}

    if request.method == "POST":
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        # Ensure username typed is valid
        if not username or len(rows) == 1:
            return apology("invalid / existing username", 403)

        # Register a username
        registrant["username"] = username

        password = request.form.get("password")
        password_confirmation = request.form.get("confirmation")

        # Ensure passwords typed match
        if not password or not password_confirmation or password != password_confirmation:
            return apology("passwords do not match", 403)

        # Check if the password is strong enough
        if not any(char.isdigit() for char in password):
            return apology("Password not strong enough")

        if not any(char.isalpha() for char in password):
            return apology("Password not strong enough")

        # Register a password
        registrant["password"] = generate_password_hash(password)

        # Insert the new user in the database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                   username=registrant["username"], hash=registrant["password"])

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Highlight a regitered message
        flash("Registered")

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Look up for the current user stocks's symbol in the database
    symbols = db.execute(
        "SELECT symbol FROM transactions JOIN users ON users.id=transactions.user_id WHERE users.id=:user_id GROUP BY symbol", user_id=session["user_id"])

    stocks = []

    # append into the stocks list only the user stock's symbol
    for row in symbols:
        stocks.append(row["symbol"])

    if request.method == "POST":

        symbol = request.form.get("symbol")

        if not symbol in stocks:
            return apology("Invalid symbol")

        # Check if the quantitie of shares is not an integer
        try:
            shares = int(request.form.get("shares"))

        except:
            return apology("Invalid number of shares")

        if shares < 0:
            return apology("Invalid number of shares")

        # Look up for the current quantitie of stocks that the current user has
        user_stocks = db.execute(
            "SELECT symbol, SUM(shares) AS total_shares FROM transactions JOIN users ON users.id=transactions.user_id WHERE users.id=:user_id GROUP BY symbol", user_id=session["user_id"])

        quant_stocks = []

        for row in user_stocks:
            unit = {
                "symbol": row["symbol"],
                "total_shares": row["total_shares"]
            }
            quant_stocks.append(unit)

        # Check if the user has enough stocks to sell
        for row in quant_stocks:
            if row["symbol"] == shares and row["total_shares"] < shares:
                return apology("Not enough stocks to sell")

        # Look up for the current stock's price
        updated_stock = lookup(symbol)

        # Insert a new transaction into the database
        db.execute("INSERT INTO transactions (user_id, symbol, name, shares, price, total_price) VALUES (:user_id, :symbol, :name, :shares, :price, :total_price)",
                   user_id=session["user_id"], symbol=updated_stock["symbol"], name=updated_stock["name"], shares=-shares,
                   price=updated_stock["price"], total_price=shares*updated_stock["price"])

        # Seach for the current user
        user = db.execute("SELECT * FROM users WHERE id=:user_id", user_id=session["user_id"])

        # Update the user's cash
        db.execute("UPDATE users SET cash=:new_cash WHERE id=:user_id",
                   new_cash=user[0]["cash"]+(shares*updated_stock["price"]), user_id=session["user_id"])

        # Highlight a sold message
        flash("Sold")

        return redirect("/")

    else:

        return render_template("sell.html", stocks=stocks)


# --------------------------------- Beguin of the code provided by CS50x --------------------------------------
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

# ------------------------------- End of the code provided by CS50x -------------------------------------------
