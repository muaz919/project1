import os, json

from flask import Flask, flash, request, session, redirect, render_template, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
from login import login_required
import requests


app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine("PostgreSQl Host")
db = scoped_session(sessionmaker(bind=engine))



@app.route('/')
@login_required
def index():
    return render_template("index.html", username=session["user_name"])


    
@app.route("/login", methods=["GET", "POST"])
def login():
    """ Log user in """

    session.clear()

    username = request.form.get("username")

    if request.method == "POST":

        if not request.form.get("username"):
            return render_template("error.html", message="must provide username")

        elif not request.form.get("password"):
            return render_template("error.html", message="must provide password")

        rows = db.execute("SELECT * FROM login WHERE username = :username",
                            {"username": username})
        
        result = rows.fetchone()

        if result == None or not check_password_hash(result[2], request.form.get("password")):
            return render_template("error.html", message="invalid username and/or password")

        session["user_id"] = result[0]
        session["user_name"] = result[1]

        return render_template("index.html")

    else:
        return render_template("login.html")



@app.route('/register', methods=["POST","GET"])
def register():

    session.clear()
    
    if request.method == "POST":

        if not request.form.get("username"):
            return render_template("error.html", message="must provide username")

        userCheck = db.execute("SELECT * FROM login WHERE username = :username",
                          {"username":request.form.get("username")}).fetchone()

        if userCheck:
            return render_template("error.html", message="username already exist")

        elif not request.form.get("password"):
            return render_template("error.html", message="must provide password")

        elif not request.form.get("pass2"):
            return render_template("error.html", message="must confirm password")

        elif not request.form.get("password") == request.form.get("pass2"):
            return render_template("error.html", message="passwords didn't match")
        
        hashedPassword = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)
        
        db.execute("INSERT INTO login (username, password) VALUES (:username, :password)",
                    {"username":request.form.get("username"), 
                    "password":hashedPassword})

        db.commit()

        flash('Account created', 'info')

        return redirect("/login")

    else:
        return render_template("register.html")



@app.route("/logout")
def logout():
    """ Log user out """
    session.clear()
    return redirect("/login")

    

@app.route("/search", methods=["GET"])
@login_required
def search():
    """ Get books results """

    if not request.args.get("book"):
        return render_template("error.html", message="you must provide a book.")

    # take input
    query = "%" + request.args.get("book") + "%"

    # capitalize the word input
    query = query.title()
    
    rows = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn LIKE :query OR \
                        title LIKE :query OR \
                        author LIKE :query LIMIT 15",
                        {"query": query})
    
    if rows.rowcount == 0:
        return render_template("error.html", message="we can't find books with that description.")
    
    books = rows.fetchall()

    return render_template("results.html", books=books)
   


@app.route("/book/<isbn>", methods=["GET","POST"])
@login_required
def book(isbn):
    """ Save user review and load same page with reviews updated."""

    if request.method == "POST":

        currentUser = session["user_id"]
        
        rating = request.form.get("rating")
        comment = request.form.get("comment")
        
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        bookId = row.fetchone() 
        bookId = bookId[0]

        row2 = db.execute("SELECT * FROM review WHERE user_id = :user_id AND book_id = :book_id",
                    {"user_id": currentUser,
                     "book_id": bookId})

        if row2.rowcount == 1:
            
            flash('You already submitted a review for this book', 'warning')
            return redirect("/book/" + isbn)

        rating = int(rating)

        db.execute("INSERT INTO review (user_id, book_id, comment, rating) VALUES \
                    (:user_id, :book_id, :comment, :rating)",
                    {"user_id": currentUser, 
                    "book_id": bookId, 
                    "comment": comment, 
                    "rating": rating})

        db.commit()

        flash('Review submitted!', 'info')

        return redirect("/book/" + isbn)
    
    else:

        row = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn = :isbn",
                        {"isbn": isbn})

        bookInfo = row.fetchall()

        """ GOODREADS reviews """

        key = "BqVKiykrTu0gxqs5CgU4DQ"
        
        query = requests.get("https://www.goodreads.com/book/review_counts.json",
                params={"key": key, "isbns": isbn})
        if query.status_code != 200:
            raise Exception("ERROR: API request unsuccessful.")


        response = query.json()

        response = response['books'][0]

        bookInfo.append(response)

        """ Users reviews """

        row = db.execute("SELECT id FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        book = row.fetchone() 
        book = book[0]

        results = db.execute("SELECT user_id, comment, rating \
                            FROM review \
                            INNER JOIN login \
                            ON login.id = review.user_id \
                            WHERE book_id = :book",
                            {"book": book})

        review = results.fetchall()

        return render_template("book.html", bookInfo=bookInfo, review=review)



@app.route("/api/<isbn>", methods=['GET'])
@login_required
def api_call(isbn):


    row = db.execute("SELECT title, author, year, isbn, \
                    COUNT(review.user_id) as review_count, \
                    AVG(review.rating) as average_score \
                    FROM books \
                    INNER JOIN review \
                    ON books.id = review.book_id \
                    WHERE isbn = :isbn \
                    GROUP BY title, author, year, isbn",
                    {"isbn": isbn})

    if row.rowcount != 1:
        return jsonify({"Error": "Invalid book ISBN"}), 422

    tmp = row.fetchone()

    result = dict(tmp.items())

    result['average_score'] = float('%.2f'%(result['average_score']))

    return jsonify(result)
