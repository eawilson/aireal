#!/usr/bin/env python3

from aireal import create_app
from aireal.models import locationtypes, locationtypes_locationtypes, locationmodels, locations
from aireal.i18n import _
from aireal.utils import engine
import pdb

conn = None



def prime_db():
    """ Must be called from the instance folder containing the details of the
        database to be migrated. Initialises db with base information.
    """
    global conn
    app = create_app(".")
    
    with app.test_request_context():
        with engine.begin() as conn:
            root = new_type("")
            site = new_type(_("Site"))
            building = new_type(_("Building"))
            room = new_type(_("Room"))
            archive = new_type(_("Archive"), attr={"temperature": True})
            fridge = new_type(_("Fridge"), attr={"temperature": True, "shelves": True})
            freezer = new_type(_("Freezer"), attr={"temperature": True, "shelves": True})
            cupboard = new_type(_("Cupboard"), attr={"shelves": True})
            shelf = new_type(_("Shelf"), attr={"size": True})
            rack = new_type(_("Rack"), attr={"movable": True, "trays": True})
            tray = new_type(_("Tray"), attr={"size": True})
            box = new_type(_("Box"), attr={"movable": True, "size": True, "capacity": True})
            
            can_contain(root, [site])
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
             
            root_model = new_model("", locationtype=root_type)            
            site_model = new_model("Site", locationtype=site_type)
            
            new_location("", locationmodel_id=root_model, site_id=1, parent_id=1)



def new_type(_(name, movable, **kwargs):
    sql = locationtypes.insert().values(name=name, movable=movable, **kwargs)
    return conn.execute(sql).inserted_primary_key[0]



def new_model(name, locationtype, movable=movable, **kwargs):
    sql = locationmodels.insert().values(name=name, locationtype=locationtype, movable=movable, **kwargs)
    return conn.execute(sql).inserted_primary_key[0]



def new_location(name, locationmodel_id, site_id, parent_id, **kwargs):
    sql = locations.insert().values(name=name, locationmodel_id=locationmodel_id, site_id=site_id, parent_id=parent_id, **kwargs)
    return conn.execute(sql).inserted_primary_key[0]



def can_contain(parent, children):
    vals = [{"parent_id": parent, "child_id": child} for child in children]
    sql = locationtypes_locationtypes.insert()
    conn.execute(sql, vals)



if __name__ == "__main__":
    prime_db()


    
