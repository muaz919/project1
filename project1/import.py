import csv
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine("postgres://osxvrpxjoxuwlm:38bf3cd2e0655e7fb0e0e6827955dbba7eceb2e349686dffce73355fb47af3e9@ec2-18-233-32-61.compute-1.amazonaws.com:5432/damepngmrr7kl2")
db = scoped_session(sessionmaker(bind=engine))

def main():
    f = open("books.csv")
    reader = csv.reader(f)
    for isbn, title, author, year in reader:
        db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
                   {"isbn": isbn, "title": title, "author": author, "year":year})
        print(f"Added book {title} to database.")
    db.commit()

if __name__ == "__main__":
    main()
