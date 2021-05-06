from flask import url_for

from ..utils import Blueprint, navbar, tablerow, render_page
from ..i18n import _

app = Blueprint("admin", __name__, "Admin")


@navbar("Admin")
def admin_navbar():
    return [{"text": _("Users"), "href":  url_for("admin.list_users")},
            {"text": _("Edit"), "href":  url_for("admin.editmenu")}]



@app.route("/admin/edit")
def editmenu():
    body = [tablerow(_("Projects"), id="projects"),
            tablerow(_("Locations"), id="locations"),
            tablerow(_("Location Models"), id="locationmodels"),
            tablerow(_("Pathology Sites"), id="pathologysites")]
    
    actions = ({"name": _("View"), "href": "/0"},) # Not ideal
    table = {"head": (_("Tables"),), "body": sorted(body), "actions": actions}
    return render_page("table.html", table=table, buttons=())

