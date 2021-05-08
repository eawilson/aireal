from datetime import datetime, timezone

from flask import url_for

from ..utils import Blueprint, navbar, tablerow, render_page, Transaction
from ..i18n import _




app = Blueprint("reception", __name__, "Reception")


@navbar("Reception")
def reception_navbar():
    return [{"text": _("Collections"), "href":  url_for("reception.collection_list")}]



@app.route("/collections")
def collection_list():
    now = utcnow()
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    filters = [collection.c.received_datetime >= today]
    
    sql = select([collection.c.id, project.c.name.label("project"), subjects.c.name.label("subject"), material.c.name.label("material"), collection.c.received_datetime, users.c.name.label("user"), collection.c.deleted]). \
            select_from(join(collection, samples, samples.c.collection_id == collection.c.id). \
                        join(subjects, collection.c.subject_id == subjects.c.id). \
                        join(project, subjects.c.project_id == project.c.id). \
                        join(material, material.c.id == samples.c.material_id). \
                        join(logs, and_(logs.c.row_id == collection.c.id, logs.c.tablename == collection.name)). \
                        join(users, users.c.id == logs.c.user_id)). \
            where(and_(*filters)). \
            order_by(collection.c.received_datetime.desc())
    
    head=(_("Subject"), _("Project"), _("Samples"), _("Date Received"), _("Received By"))
    body = []
    last_id = None
    with engine.connect() as conn:
        for row in conn.execute(sql):
            if row["id"] == last_id:
                body[-1][0][2] += f', {row["material"]}'
            body += [[row["subject"],
                      row["project"],
                      row["material"],
                      Local(row["received_datetime"]),
                      row["user"]],
                     {"deleted": row["deleted"],
                      "id": row["id"]}
                    ]
    actions = ({"name": _("View"), "href": url_for(".view_collection", collection_id=0)},
               {"name": _("Edit"), "href": url_for(".edit_collection", collection_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_collection", collection_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_collection", collection_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".collection_log", collection_id=0)})
    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": ("", url_for(".new_collection")), "title": _("Collections")},
                       buttons=())

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
