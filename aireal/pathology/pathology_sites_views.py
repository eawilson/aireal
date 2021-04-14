from flask import redirect, url_for, request
from werkzeug import exceptions

from psycopg2.errors import UniqueViolation

from ..utils import Cursor, login_required, abort, tablerow, render_page, dict_from_select, unique_key
from ..forms import ActionForm
from .views import app
from ..logic import crud
from ..i18n import _
from ..view_helpers import log_table

from ..forms import NameForm



@app.route("/pathology_sites/<int:pathology_site_id>/log")
@login_required("Admin")
def pathology_site_log(pathology_site_id):
    with Cursor() as cur:
        table = log_table(cur, "pathology_sites", pathology_site_id)

    table["title"] = _("Pathology Sites Log")
    buttons={"back": (_("Back"), url_for(".pathology_sites_list"))}
    return render_page("table.html", table=table, buttons=buttons)

        

@app.route("/pathology_sites/new", defaults={"pathology_site_id": None}, methods=["GET", "POST"])
@app.route("/pathology_sites/<int:pathology_site_id>/edit", methods=["GET", "POST"])
@login_required("Admin")
def edit_pathology_site(pathology_site_id):
    with Cursor() as cur:
        if pathology_site_id is not None:
            sql = """SELECT id, name, deleted
                     FROM pathology_sites
                     WHERE id = %(pathology_site_id)s;"""
            old = dict_from_select(cur, sql, {"pathology_site_id": pathology_site_id})
        else:
            old = {}
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                crud(cur, "pathology_sites", {"deleted": True}, old)
            elif action == _("Restore"):
                crud(cur, "pathology_sites", {"deleted": False}, old)
            return redirect(request.referrer)
        
        form = NameForm(request.form if request.method=="POST" else old)

        if request.method == "POST" and form.validate():
            new = form.data
            try:
                crud(cur, "pathology_sites", new, old)
            except UniqueViolation as e:
                pdb.set_trace()
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                return redirect(url_for(".pathology_sites_list"))

    title = _("Edit Pathology Site") if pathology_site_id is not None else _("New Pathology Site")
    buttons={"submit": (_("Save"), url_for(".edit_pathology_site", pathology_site_id=pathology_site_id)),
             "back": (_("Cancel"), url_for(".pathology_sites_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/pathology_sites")
@login_required("Admin")
def pathology_sites_list():
    body = []
    with Cursor() as cur:
        cur.execute(sql)
        sql = """SELECT id, name, deleted
                 FROM pathology_sites
                 ORDER BY name;"""
        for pathology_site_id, name, deleted in cur:
            body.append(((name,), 
                        {"id": pathology_site_id,
                        "deleted": deleted}))
    
    head = (_("Name"),)
    actions = ({"name": _("Edit"), "href": url_for(".edit_pathology_site", pathology_site_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_pathology_site", pathology_site_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_pathology_site", pathology_site_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".pathology_site_log", pathology_site_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".edit_pathology_site"), "title": "Pathology Sites"},
                       buttons={"back": (_("Back"), url_for(".editmenu"))})
