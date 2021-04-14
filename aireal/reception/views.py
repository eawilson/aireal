from datetime import datetime, timezone

from sqlalchemy import select, join, or_, outerjoin, and_
from flask import Blueprint, url_for

from ..utils import navbar, login_required, tablerow, render_page, utcnow, Transaction
from ..i18n import _

from ..models import collections, samples, subjects, users, projects, materials, logs



app = Blueprint("reception", __name__)


@navbar("Reception")
def reception_navbar():
    return [{"text": _("Collections"), "href":  url_for("reception.list_collections")}]



@app.route("/collections")
@login_required("Reception")
def list_collections():
    now = utcnow()
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    filters = [collections.c.received_datetime >= today]
    
    sql = select([collections.c.id, projects.c.name.label("project"), subjects.c.name.label("subject"), materials.c.name.label("material"), collections.c.received_datetime, users.c.name.label("user"), collections.c.deleted]). \
            select_from(join(collections, samples, samples.c.collection_id == collections.c.id). \
                        join(subjects, collections.c.subject_id == subjects.c.id). \
                        join(projects, subjects.c.project_id == projects.c.id). \
                        join(materials, materials.c.id == samples.c.material_id). \
                        join(logs, and_(logs.c.row_id == collections.c.id, logs.c.tablename == collections.name)). \
                        join(users, users.c.id == logs.c.user_id)). \
            where(and_(*filters)). \
            order_by(collections.c.received_datetime.desc())
    
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
@login_required("Reception")
def view_collection(collection_id):
    pass

@app.route("/collections/<int:collection_id>/edit")
@login_required("Reception")
def edit_collection(collection_id):
    pass

@app.route("/collections/<int:collection_id>/edit")
@login_required("Reception")
def collection_log(collection_id):
    pass

@app.route("/collections/new")
@login_required("Reception")
def new_collection():
    pass
