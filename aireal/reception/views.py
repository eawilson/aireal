from datetime import datetime, timezone

from flask import url_for

from ..utils import Cursor, Transaction, tablerow, iso8601_to_utc
from flask import session, redirect, url_for, request, send_file, current_app
from ..flask import abort, render_page, render_template, Blueprint, sign_token, absolute_url_for
from ..i18n import _



def reception_navbar():
    return [{"text": _("Collections"), "href":  url_for("Reception.collection_list")}]


app = Blueprint("Reception", __name__, navbar=reception_navbar)



@app.route("/collections")
def collection_list():
    #with Cursor() as cur:
        #sql = """SELECT bsaccount.id, bsaccount.name, bsserver.region, bsserver.country
                 #FROM bsaccount
                 #JOIN users_bsaccount ON bsaccount.id = users_bsaccount.bsaccount_id
                 #JOIN bsserver ON bsserver.id = bsaccount.bsserver_id
                 #WHERE users_bsaccount.users_id = %(users_id)s
                 #ORDER BY bsaccount.name;"""
        #body = []
        #cur.execute(sql, {"users_id": session["id"]})
        #for bsaccount_id, bsaccount_name, region, country in cur:
            #body.append(((bsaccount_name,
                          #"{} ({})".format(region, _(country))),
                          #{"id": bsaccount_id}))
    
    #actions = ({"name": _("Select"), "href": url_for("Bioinformatics.Basespace.runs", account_id=0)},)
    table = {"head": [],
             "body": []}
    #now = utcnow()
    #today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    #filters = [collection.c.received_datetime >= today]
    
    #sql = select([collection.c.id, project.c.name.label("project"), subjects.c.name.label("subject"), material.c.name.label("material"), collection.c.received_datetime, users.c.name.label("user"), collection.c.deleted]). \
            #select_from(join(collection, samples, samples.c.collection_id == collection.c.id). \
                        #join(subjects, collection.c.subject_id == subjects.c.id). \
                        #join(project, subjects.c.project_id == project.c.id). \
                        #join(material, material.c.id == samples.c.material_id). \
                        #join(logs, and_(logs.c.row_id == collection.c.id, logs.c.tablename == collection.name)). \
                        #join(users, users.c.id == logs.c.user_id)). \
            #where(and_(*filters)). \
            #order_by(collection.c.received_datetime.desc())
    
    #head=(_("Subject"), _("Project"), _("Samples"), _("Date Received"), _("Received By"))
    #body = []
    #last_id = None
    #with engine.connect() as conn:
        #for row in conn.execute(sql):
            #if row["id"] == last_id:
                #body[-1][0][2] += f', {row["material"]}'
            #body += [[row["subject"],
                      #row["project"],
                      #row["material"],
                      #Local(row["received_datetime"]),
                      #row["user"]],
                     #{"deleted": row["deleted"],
                      #"id": row["id"]}
                    #]
    #actions = ({"name": _("View"), "href": url_for(".view_collection", collection_id=0)},
               #{"name": _("Edit"), "href": url_for(".edit_collection", collection_id=0)},
               #{"name": _("Delete"), "href": url_for(".edit_collection", collection_id=0), "class": "!deleted", "method": "POST"},
               #{"name": _("Restore"), "href": url_for(".edit_collection", collection_id=0), "class": "deleted", "method": "POST"},
               #{"name": _("Log"), "href": url_for(".collection_log", collection_id=0)})
    return render_page("table.html", table=table, buttons=())
    _("Reception")
    _("LoBind")
    _("Standard")
    _("Home")
    _("Site")
    _("Building")
    _("Room")
    _("Archive")
    _("Fridge")
    _("Freezer")
    _("Cupboard")
    _("Rack")
    _("Shelf")
    _("Tray")
    _("Box")
    _("Tube")


@app.route("/collections/<int:collection_id>")
def view_collection(collection_id):
    pass

@app.route("/collections/<int:collection_id>/edit")
def edit_collection(collection_id):
    pass

@app.route("/collections/<int:collection_id>/edit")
def collection_log(collection_id):
    pass

@app.route("/collections/new")
def new_collection():
    pass
