import argparse
import os
import sys

from psycopg2 import IntegrityError

import aireal
from aireal.utils import valid_groups, Transaction
from aireal import logic, auth


def init_db(command, instance_path):
    """ 
    """
    app = aireal.create_app(instance_path)
    with app.test_request_context():
        with Transaction() as trans:
            with trans.cursor() as cur:

                # Delete all tables of old database
                if command == "init":
                    sql = """DO $$ DECLARE
                                 r RECORD;
                             BEGIN
                                 FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = current_schema()) LOOP
                                     EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                                 END LOOP;
                             END $$;"""
                    cur.execute(sql)
                    trans.commit()

                # Create new tables
                for root, dirs, files in os.walk(os.path.dirname(aireal.__file__)):
                    for fn in files:
                        if fn.endswith(".sql"):
                            path = os.path.join(root, fn)
                            with open(path) as f_in:
                                sql = f_in.read()
                            cur.execute(sql)
                trans.commit()
    

                for name in valid_groups:
                    sql = "INSERT INTO groups (name) VALUES (%(name)s);"
                    try:
                        cur.execute(sql, {"name": name})
                        trans.commit()
                    except IntegrityError:
                        trans.rollback()
                
                
                if command == "init":
                    sql = "SELECT id FROM groups WHERE name = 'Admin';"
                    cur.execute(sql)
                    group_id = cur.fetchone()[0]
                    
                    email = "someone@example.com"
                    new = {"email": email,
                            "name": "A.Admin",
                            "forename": "Admin",
                            "surname": "Admin",
                            "groups": [group_id]}
                    group_id_choices = ((group_id, "Admin"),)
                    user_id = logic.crud(cur, "users", new, groups=group_id_choices)
                    auth.send_setpassword_email(cur, email)
                    trans.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")    
    parser.add_argument("path", nargs="?", default=".")    
    args = parser.parse_args()
    
    if args.command not in ("init", "update"):
        sys.exit(f"{args.command} is not a recognised command")
        
    try:
        init_db(args.command, args.path)
    except OSError as e:
        # File input/output error. This is not an unexpected error so just
        # print and exit rather than displaying a full stack trace.
        sys.exit(str(e))



if __name__ == "__main__":
    main()



    
