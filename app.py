import os
import redis

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup

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


# Setting up redis
r = redis.from_url(os.environ.get("REDIS_URL"))

# Configure session to use redis
app.config["SESSION_REDIS"] = r
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "redis"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
@login_required
def search():
    """ Show search field for book"""
    return render_template("index.html")

@app.route("/search", methods=["GET", "POST"])
@login_required
def results():
    """ Show search field for book"""
    if request.method == "GET":
        return render_template("index.html")
    
    else:
        search_item = request.form.get("search")
        if len(search_item) == 0:
            flash("Please enter a name of a Book, Author, or ISBN that you would like to search.")
            return render_template("index.html")
        else:
            # search_string = dict(search_string=search_item)
            search_string = dict(search_string="%" + search_item + "%")
            res = db.execute("SELECT * FROM books WHERE (isbn ILIKE :search_string) OR (bookname ILIKE :search_string) OR (author ILIKE :search_string)", search_string).fetchall()
            keys = ("book_id", "isbn", "bookname", "author", "year")
            result = [dict(zip(keys, values)) for values in res]
            return render_template("results.html", result=result)


@app.route("/book/<int:book_id>", methods=["GET", "POST"])
@login_required
def book(book_id):
    """ Show the results based on user search query"""
    # get the book ID
    id_book = dict(id_book=str(book_id))
    # if the req came in through GET, then display the book details
    if request.method == "GET":
        # Query the book details
        selected_book = db.execute("SELECT bookname, author, year, isbn FROM books WHERE book_id = :id_book", id_book).fetchall()
        # get the tuple, change it to a list of dict, and get the dict out
        # we must do this because we need to send this as variables to jinja
        book_keys = ("bookname", "author", "year", "isbn")
        book_result = [dict(zip(book_keys, values)) for values in selected_book]
        book_result_dict = book_result[0]
        # Query the reviews
        selected_book_review = db.execute("SELECT review FROM reviews WHERE book_id = :id_book", id_book).fetchall()
        # get the tuple, change it to a list of dict
        # send it to jinja for loop to print the reviews
        review_keys = ("review",)
        book_review = [dict(zip(review_keys, values)) for values in selected_book_review]
        # Query the goodreads rating details and add it to a dict
        goodread = lookup(dict(isbns=book_result_dict['isbn']))

        return render_template("book.html", bookname=book_result_dict['bookname'], author=book_result_dict['author'], year=book_result_dict['year'],isbn=book_result_dict['isbn'], book_review=book_review, average_rating=goodread['average_rating'], num_rating=goodread['num_rating'])

    else:
        # check if the user has already reviews the book
        uid = dict(uid=session['user_id'])
        ubrs = {**uid, **id_book}
        user_review_status = db.execute("SELECT * FROM reviews WHERE uid = :uid and book_id = :id_book", ubrs).fetchall()
        revu_keys = ("reviews",)
        ubrs_status = [dict(zip(revu_keys, values)) for values in user_review_status]
        book_get_url = url_for('book', book_id=id_book["id_book"])
        # if yes, just show the reviews
        if len(ubrs_status) > 0:
            flash("Sorry, you have already reviewed this book, users can review a book only once!")
            return redirect(book_get_url)
        
        # if not let them write a review and store it
        else:
            user_review = request.form.get("review")
            user_rating = int(request.form.get("rating"))
            u_revu = dict(review=user_review)
            u_rate = dict(rating=user_rating)
            urrb = {**uid, **id_book, **u_revu, **u_rate}
            record_user_rating = db.execute("INSERT INTO reviews (uid, book_id, review, rating) VALUES (:uid, :id_book, :review, :rating)", urrb)
            db.commit()
            flash("Thank you for reviewing this book!")
            return redirect(book_get_url)


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
        username = dict(username=request.form.get("username"))
        rows = db.execute("SELECT * FROM users WHERE username = :username", username).fetchall()
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][2], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0][0]

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


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not (request.form.get("password") and request.form.get("confirmation")):
            return apology("must provide password", 403)

        # Query database for username
        username = dict(username=request.form.get("username"))
        check_username = db.execute("SELECT * FROM users WHERE username = :username", username).fetchall()

        # Ensure username does not exist in the DB
        if len(check_username) > 0:
            flash("Sorry, username is already taken!")
            return render_template("register.html")

        else:
            # Add username, hash the password and add it to the DB
            hashed_pass = dict(hashed_pass=generate_password_hash(request.form.get("password")))
            create_creds = {**username, **hashed_pass}
            new_user = db.execute("INSERT INTO users (username, password) VALUES (:username, :hashed_pass) RETURNING uid", create_creds).fetchall()
            db.commit()
            flash("Registration Successfull!")
            session["user_id"] = new_user[0][0]
            return redirect("/")

    else:
        return render_template("register.html")


@app.route("/api/isbn/<isbn>", methods=["GET"])
def book_api(isbn):
    """Return details about a single ISBN."""
    # Make sure ISBN exists.
    rq_isbn = dict(isbn=str(isbn))
    req_isbn = db.execute("""SELECT b.bookname, b.author, b.year, b.isbn,
                                    COUNT(r.review) AS review_count, COALESCE(ROUND(AVG(r.rating), 2),0) AS average_score
                            FROM books b
                            LEFT JOIN reviews r ON b.book_id=r.book_id
                            WHERE b.isbn = :isbn
                            GROUP BY b.bookname, b.author, b.year, b.isbn""", rq_isbn).fetchall()

    if len(req_isbn) > 0:
        req_isbn_keys = ("bookname", "author", "year", "isbn", "review_count", "average_score")
        req_isbn_result = [dict(zip(req_isbn_keys, values)) for values in req_isbn]
        req_isbn_dict = req_isbn_result[0]
        # https://floating-point-gui.de/languages/python/
        req_isbn_dict["review_count"] = float(req_isbn_dict['review_count'])
        req_isbn_dict["average_score"] = float('%.2f'%(req_isbn_dict['average_score']))
        return jsonify(req_isbn_dict)

    else:
        return jsonify({"error": "Invalid isbn"}), 422


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
