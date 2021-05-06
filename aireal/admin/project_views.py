import pdb

from flask import redirect, url_for, request
from werkzeug import exceptions

from psycopg2.errors import UniqueViolation

from ..utils import Cursor, abort, tablerow, render_page, dict_from_select, unique_key, Transaction
from ..forms import ActionForm
from .views import app
from ..logic import perform_edit, perform_delete, perform_restore
from ..i18n import _
from ..view_helpers import log_table

from .forms import ProjectForm



@app.route("/projects/<int:project_id>/log")
def project_log(project_id):
    with Cursor() as cur:
        table = log_table(cur, "project", project_id)

    table["title"] = _("Project Log")
    buttons={"back": (_("Back"), url_for(".project_list"))}
    return render_page("table.html", table=table, buttons=buttons)

        

@app.route("/projects/new", defaults={"project_id": None}, methods=["GET", "POST"])
@app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
def edit_project(project_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            if project_id is not None:
                sql = """SELECT id, name, deleted
                        FROM project
                        WHERE id = %(project_id)s;"""
                old = dict_from_select(cur, sql, {"project_id": project_id})
            else:
                old = {}
            
            form = ActionForm(request.form)
            if request.method == "POST" and form.validate():
                action = form.action.data
                if action == _("Delete"):
                    perform_delete(cur, "project", project_id)
                elif action == _("Restore"):
                    perform_restore(cur, "project", project_id)
                return redirect(request.referrer)
            
            form = ProjectForm(request.form if request.method=="POST" else old)

            if request.method == "POST" and form.validate():
                new = form.data
                try:
                    perform_edit(cur, "project", new, old, form)
                except UniqueViolation as e:
                    trans.rollback()
                    form[unique_key(e)].errors = _("Must be unique.")
                else:
                    return redirect(url_for(".project_list"))

    title = _("Edit Project") if project_id is not None else _("New Project")
    buttons={"submit": (_("Save"), url_for(".edit_project", project_id=project_id)),
             "back": (_("Cancel"), url_for(".project_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/projects")
def project_list():
    sql = """SELECT id, name, deleted
             FROM project
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
