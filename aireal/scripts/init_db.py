#!/usr/bin/env python3

import argparse
import os
import aireal
import sys
import pdb
import psycopg2



def main():
    """ Create all database tables and initialise with essential
        data. Creates admin user but this must account must be
        activated with the force_reset.sh script before it can
        be used. This script is designed to be run within an
        empty database and cannot be used to perform migrations.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to instance folder containing the config file with database connection uri.")    
    args = parser.parse_args()
    
    hierarchy = []
    for root, dirs, files in os.walk(os.path.dirname(aireal.__file__)):
        for fn in files:
            if fn.endswith(".sql"):
                path = os.path.join(root, fn)
                hierarchy.append((len(path.split("/")), path))

    app = aireal.create_app(args.path)
    with app.test_request_context():
        with aireal.utils.Transaction() as trans:
            with trans.cursor() as cur:
                for i, path in sorted(hierarchy):
                    print(path, file=sys.stderr)
                    with open(path) as f_in:
                        sql = f_in.read()
                    try:
                        cur.execute(sql)
                    except psycopg2.Error as e:
                        sys.exit(e)



if __name__ == "__main__":
    main()


    
