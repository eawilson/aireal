import argparse
import os
import sys
import pdb
from functools import partial

from psycopg2 import IntegrityError

import aireal
from aireal.flask import valid_roles
from aireal.utils import Transaction
from aireal.auth import send_setpassword_email
from aireal.admin.forms import UserForm
from aireal.logic import perform_edit

trans = None
cur = None

def _(text):
    return text



def init_db(nstance_path, no_data):
    """ 
    """
    global trans
    global cur
    
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
                             END $$;
                             
                             DROP TYPE IF EXISTS movability;"""
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
    

                sql = "INSERT INTO role (name) VALUES (%(name)s) ON CONFLICT DO NOTHING;"
                cur.executemany(sql, [{"name": name} for name in valid_roles])
                
                
                if no_data:
                    return
                
                email = "someone@example.com"
                form = UserForm({"email": email,
                                    "forename": "Admin",
                                    "surname": "Admin",
                                    "role": ["Admin"]})
                form.role.choices = (("Admin", "Admin"),)
                perform_edit(cur, "users", form.data, form=form)
                send_setpassword_email(cur, email)

                new_type = partial(upsert, "locationtype", pk="name")
                root = new_type("Home", movable="inbuilt")
                site = new_type(_("Site"), movable="fixed")
                building = new_type(_("Building"), movable="fixed")
                room = new_type(_("Room"), movable="fixed", attr={"has-temperature": True})
                archive = new_type(_("Archive"), movable="fixed", attr={"has-temperature": True})
                fridge = new_type(_("Fridge"), movable="fixed", attr={"has-temperature": True, "has-shelves": True})
                freezer = new_type(_("Freezer"), movable="fixed", attr={"has-temperature": True, "has-shelves": True})
                cupboard = new_type(_("Cupboard"), movable="fixed", attr={"has-shelves": True})
                rack = new_type(_("Rack"), movable="mobile", attr={"has-size": True, "has-trays": True})
                shelf = new_type(_("Shelf"), movable="inbuilt", attr={"has-internal-size": True})
                tray = new_type(_("Tray"), movable="inbuilt", attr={"has-positions": True})
                box = new_type(_("Box"), movable="mobile", attr={"has-size": True, "has-positions": True, "min-volume": "?", "max-volume": "?", "content-brand": "?"})
                tube = new_type(_("Tube"), movable="mobile", attr={"contains-material": True})
                
                can_contain(root, [site, building, room, archive, fridge, freezer, cupboard])
                can_contain(site, [building, room, archive, fridge, freezer, cupboard])
                can_contain(building, [room, archive, fridge, freezer, cupboard])
                can_contain(room, [archive, fridge, freezer, cupboard])
                can_contain(archive, [box])
                can_contain(fridge, [shelf])
                can_contain(freezer, [shelf])
                can_contain(cupboard, [shelf])
                can_contain(shelf, [rack, box])
                can_contain(rack, [tray])
                can_contain(tray, [box])
                can_contain(box, [tube])
                
                root_model = upsert("locationmodel", _("Home"), locationtype=root, movable="inbuilt")
                site_model = upsert("locationmodel", _("Site"), locationtype=site, movable="fixed")
                site_model = upsert("locationmodel", _("Room"), locationtype=room, movable="fixed")
                building_model = upsert("locationmodel", _("Building"), locationtype=building, movable="fixed")

                upsert("location", _("Home"), locationmodel_id=root_model, movable="inbuilt")

                upsert("tubematerial", "LoBind")
                upsert("tubematerial", "Standard")



def upsert(tablename, name, pk="id", **kwargs):
    keys = list(kwargs.keys()) + ["name"]
    cols = ", ".join(keys)
    vals = ", ".join(f"%({key})s" for key in keys)
    sql = f"INSERT INTO {tablename} ({cols}) VALUES ({vals}) RETURNING {pk};"
    #if kwargs:
        #update = ", ".join(f"{col} = %({col})s" for col in kwargs.keys())
        #sql += f"ON CONFLICT (name) DO UPDATE SET {update} WHERE {tablename}.name = %(name)s RETURNING {pk};"
    #else:
        #sql += f"ON CONFLICT (name) DO NOTHING RETURNING {pk};"
    #print(sql, file=sys.stderr)
    cur.execute(sql, {"name": name, **kwargs})
    return cur.fetchone()[0]



def can_contain(parent, children):
    sql = "INSERT INTO locationtype_locationtype (parent, child) VALUES (%(parent)s, %(child)s) ON CONFLICT DO NOTHING;"
    #print(sql, file=sys.stderr)
    for child in children:
        cur.execute(sql, {"parent": parent, "child": child})



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", help="path to instance folder containing config file with database connection uri.", default=".")    
    parser.add_argument("-n", "--no-data", action="store_const", help="database will be initialised after creation unless passed the --no-data arguent", const=True, default=False)    
    args = parser.parse_args()
    
    try:
        init_db(args.path, args.no_data)
    except OSError as e:
        # File input/output error. This is not an unexpected error so just
        # print and exit rather than displaying a full stack trace.
        sys.exit(str(e))



if __name__ == "__main__":
    main()



    
