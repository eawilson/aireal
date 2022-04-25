#!/usr/bin/env python3

import argparse
import sys
import aireal
from flask import url_for



def main():
    """ Force reset a users password and two factor authentication. 
        This script is designed to be run by the server administrator
        to gain access at initial set up or if all users have locked
        themselves out and are unable to reset their passwords
        themselves. Output is printed to the connsole where it can be
        copied and pasted into a web browser address bar.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("instance_path", nargs="?", help="path to instance folder containing the config file with database connection uri.", default=".")    
    parser.add_argument("-e", "--email", help="email address of the user to reset.", default="someone@example.com")    
    args = parser.parse_args()
    
    app = aireal.create_app(args.instance_path)
    with app.test_request_context():
        with aireal.utils.Transaction() as trans:
            with trans.cursor() as cur:
                sql = """UPDATE users
                         SET reset_datetime = clock_timestamp(), totp_secret = NULL
                         WHERE users.email = %(email)s
                         RETURNING users.reset_datetime;"""
                cur.execute(sql, {"email": args.email})
                row = cur.fetchone()
                if row:
                    token = aireal.flask.sign_token({"email": args.email, "reset_datetime": row[0]}, salt="set_password")
                    path = url_for("Auth.set_password", token=token)
                    print(f"path = '{path}'")
                else:
                    exit(f"email '{args.email}' not found in database")



if __name__ == "__main__":
    main()
