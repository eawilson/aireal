import pdb

from flask import redirect, url_for, request
from werkzeug import exceptions

from psycopg2.errors import UniqueViolation

from ..utils import Cursor, login_required, abort, tablerow, render_page, dict_from_select, unique_key
from ..forms import ActionForm
from .views import app
from ..logic import crud
from ..i18n import _
from ..models import projects
from ..view_helpers import log_table

from .forms import ProjectForm



@app.route("/projects/<int:project_id>/log")
@login_required("Admin")
def project_log(project_id):
    with Cursor() as cur:
        table = log_table(cur, "projects", project_id)

    table["title"] = _("Project Log")
    buttons={"back": (_("Back"), url_for(".projects_list"))}
    return render_page("table.html", table=table, buttons=buttons)

        

@app.route("/projects/new", defaults={"project_id": None}, methods=["GET", "POST"])
@app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required("Admin")
def edit_project(project_id):
    with Cursor() as cur:
        if project_id is not None:
            sql = """SELECT id, name, deleted
                        FROM projects
                        WHERE id = %(project_id)s;"""
            old = dict_from_select(cur, sql, {"project_id": project_id})
        else:
            old = {}
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                crud(cur, "projects", {"deleted": True}, old)
            elif action == _("Restore"):
                crud(cur, "projects", {"deleted": False}, old)
            return redirect(request.referrer)
        
        form = ProjectForm(request.form if request.method=="POST" else old)

        if request.method == "POST" and form.validate():
            new = form.data
            try:
                crud(cur, "projects", new, old)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                return redirect(url_for(".projects_list"))

    title = _("Edit Project") if project_id is not None else _("New Project")
    buttons={"submit": (_("Save"), url_for(".edit_project", project_id=project_id)),
             "back": (_("Cancel"), url_for(".projects_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/projects")
@login_required("Admin")
def projects_list():
    sql = """SELECT id, name, deleted
             FROM projects
             ORDER BY name;"""
    
    body = []
    with Cursor() as cur:
        cur.execute(sql)
        for project_id, name, deleted in cur:
            body.append(((name,), 
                        {"id": project_id,
                        "deleted": deleted}))
    
    head = (_("Name"),)
    actions = ({"name": _("Edit"), "href": url_for(".edit_project", project_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_project", project_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_project", project_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".project_log", project_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".edit_project"), "title": "Projects"},
                       buttons={"back": (_("Back"), url_for(".editmenu"))})
