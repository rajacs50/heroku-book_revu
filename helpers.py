import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(rating):
    """Look up ratings for the books from Goodreads.
        Takes a dict that has the ISBN of the book for the rating var"""

    # Contact API
    try:
        # api_key = dict(key='DRlaz1Ww2G1eiNKq7luQWA')
        api_key = dict(key=os.environ.get("API_KEY"))
        request_dict = {**api_key, **rating}
        response = requests.get("https://www.goodreads.com/book/review_counts.json", params=request_dict)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        book_rating = response.json()
        return {
            "average_rating": book_rating['books'][0]['average_rating'],
            "num_rating": book_rating['books'][0]['ratings_count']
        }
    except (KeyError, TypeError, ValueError):
        return None

# book = dict(isbns='9781632168146')