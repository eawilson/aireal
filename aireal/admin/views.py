from flask import Blueprint, url_for

from ..utils import navbar, login_required, tablerow, render_page
from ..i18n import _

app = Blueprint("admin", __name__)


@navbar("Admin")
def admin_navbar():
    return [{"text": _("Users"), "href":  url_for("admin.list_users")},
            {"text": _("Edit"), "href":  url_for("admin.editmenu")}]



@app.route("/admin/edit")
@login_required("Admin")
def editmenu():
    body = [tablerow(_("Projects"), id="projects"),
            tablerow(_("Sites"), id="sites")]
    
    actions = ({"name": _("View"), "href": "/0?dir=1"},) # Not ideal
    table = {"head": (_("Tables"),), "body": sorted(body), "actions": actions}
    return render_page("table.html", table=table, buttons=())

