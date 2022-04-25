import pdb

from flask import redirect, url_for, request, abort
from werkzeug.exceptions import NotFound

from psycopg2.errors import UniqueViolation

from ..utils import Cursor, tablerow, dict_from_select, unique_key, Transaction, audit_log, right_click_action, keyvals_from_form
from ..flask import abort, render_page, abort
from ..forms import ActionForm
from .views import app
from ..i18n import _
from ..generic_views import audit_view

from .forms import ProjectForm



def project_tabs(project_id, endpoint):
    return ({"text": _("Main"), "href": url_for(".edit_project", project_id=project_id) if endpoint != ".edit_project" else "#"},
            {"text": _("Identifiers"), "href": url_for(".list_projectidentifiers", project_id=project_id) if endpoint != ".list_projectidentifiers" else "#"})



@app.route("/projects/<int:project_id>/log")
def project_audittrail(project_id):
    sql = """SELECT name FROM project WHERE id = %(project_id)s"""
    with Cursor() as cur:
        cur.execute(sql, {"project_id": project_id})
        project = (cur.fetchone() or abort(NotFound))[0]
    return audit_view("project", project_id, url_for(".list_projects"), title=_("Audit Trail: {}").format(project))

        

@app.route("/projects/<int:project_id>/main", methods=["GET", "POST"])
def edit_project(project_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT id, name, deleted, fastq_s3_path, fastq_command_line
                     FROM project
                     WHERE id = %(project_id)s;"""
            old = dict_from_select(cur, sql, {"project_id": project_id})
            
            if right_click_action("project", project_id, "Project", old["name"]):
                return redirect(request.referrer)
            
            form = ProjectForm(request.form if request.method=="POST" else old)

            if request.method == "POST" and form.validate():
                sql = """UPDATE project
                         SET name = %(name)s, fastq_s3_path = %(fastq_s3_path)s, fastq_command_line = %(fastq_command_line)s
                         WHERE id = %(project_id)s;"""
                try:
                    cur.execute(sql, {"project_id": project_id, **form.data})
                except UniqueViolation as e:
                    trans.rollback()
                    form.name.errors = _("Must be unique.")
                else:
                    audit_log(cur, "Edited", "Project", form.name.data, keyvals_from_form(form, old), "", ("project", project_id))
                    return redirect(url_for(".list_projects"))

    title = _("Edit Project: {}").format(old["name"])
    buttons={"submit": (_("Save"), url_for(".edit_project", project_id=project_id)),
             "back": (_("Back"), url_for(".list_projects"))}
    return render_page("form.html", form=form, buttons=buttons, tabs=project_tabs(project_id, ".edit_project"), title=title)



@app.route("/projects/new", methods=["GET", "POST"])
def new_project():
    form = ProjectForm(request.form if request.method=="POST" else {})
    
    if request.method == "POST" and form.validate():
        sql = """INSERT INTO project (name, fastq_s3_path, fastq_command_line)
                 VALUES (%(name)s, %(fastq_s3_path)s, %(fastq_command_line)s)
                 RETURNING id;"""
        with Transaction() as trans:
            with trans.cursor() as cur:
                try:
                    cur.execute(sql, form.data)
                except UniqueViolation as e:
                    trans.rollback()
                    form.name.errors = _("Must be unique.")
                else:
                    project_id = cur.fetchone()[0]
                    sql = """INSERT INTO project_identifiertype (identifiertype_id, project_id)
                             SELECT identifiertype.id, %(project_id)s
                             FROM identifiertype
                             WHERE identifiertype.name = 'Trial ID';"""
                    cur.execute(sql, {"project_id": project_id})
                    audit_log(cur, "Created", "Project", form.name.data, keyvals_from_form(form), "", ("project", project_id))
                    return redirect(url_for(".edit_project", project_id=project_id))
    
    buttons={"submit": (_("Save"), url_for(".new_project")),
             "back": (_("Back"), url_for(".list_projects"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("New Project"))



@app.route("/projects")
def list_projects():
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
               {"name": _("View Audit Trail"), "href": url_for(".project_audittrail", project_id=0)})
    table = {"head": head, "body": body, "actions": actions, "new": url_for(".new_project")}
    return render_page("table.html", table=table, title=_("Projects"))
