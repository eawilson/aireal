from sqlalchemy import select, join, or_, outerjoin, and_
from flask import Blueprint, url_for

from ..utils import navbar, login_required, tablerow, render_page
from ..i18n import _

from ..models import collections, samples, subjects, users, projects, materials



app = Blueprint("reception", __name__)


@navbar("Reception")
def reception_navbar():
    return [{"text": _("Samples"), "href":  url_for("reception.list_samples")}]



@app.route("/samples")
@login_required("Reception")
def list_samples():
    sql = select([samples.c.id, samples.c.name.label("slide"), users.c.name.label("user"), sites.c.name.label("site"), samples.c.created_datetime, samples.c.status, samples.c.deleted]). \
            select_from(join(samples, users, users.c.id == samples.c.user_id). \
                        join(sites, sites.c.id == samples.c.site_id)). \
            where(samples.c.project_id == session.get("project_id", None)). \
            order_by(samples.c.name)

    buttons = {"new": ("", url_for(".new_sample"))}
    if "show" in request.args:
        buttons["info"] = (_("Hide Deleted"), url_for(".list_samples"))
    else:
        sql = sql.where(samples.c.deleted == False)
        buttons["info"] = (_("Show Deleted"), url_for(".list_samples", show="True"))
    
    head=(_("Slide"), _("Site"), _("Uploaded By"), _("Date Uploaded"), _("Status"))
    body = []
    with engine.connect() as conn:
        for row in list(conn.execute(sql)):
            body += [tablerow(row["slide"],
                              row["site"],
                              row["user"],
                              Local(row["created_datetime"]),
                              row["status"],
                              deleted=row["deleted"],
                              id=row["id"]
                              )]
    actions = ({"name": _("View"), "href": url_for(".view_slide", slide_id=0)},
               {"name": _("Edit"), "href": url_for(".edit_slide", slide_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_slide", slide_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_slide", slide_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".view_log", slide_id=0)})
    return render_page("table.html",
                       title=_("Slides"),
                       table={"head": head, "body": body, "actions": actions},
                       buttons=buttons)

