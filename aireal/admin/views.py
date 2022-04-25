from flask import url_for

from ..flask import Blueprint, render_page
from ..utils import tablerow
from ..i18n import _



def admin_navbar():
    return [{"text": _("Users"), "href":  url_for("Admin.list_users")},
            {"text": _("Projects"), "href":  url_for("Admin.list_projects")},
            {"text": _("Edit"), "href":  url_for("Admin.editmenu")}]

Blueprint.navbars["Admin"] = admin_navbar
app = Blueprint("Admin", __name__)



@app.route("/admin/edit")
def editmenu():
    body = [tablerow(_("Locations"), id="locations"),
            tablerow(_("Location Models"), id="locationmodels"),
            tablerow(_("Pathology Sites"), id="pathologysites")]
    
    actions = ({"name": _("View"), "href": "/0"},) # Not ideal
    table = {"head": (_("Tables"),), "body": sorted(body), "actions": actions}
    return render_page("table.html", table=table, buttons=())

