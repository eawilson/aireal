import pdb

from flask import redirect, url_for, request
from werkzeug.exceptions import NotFound

from psycopg2.errors import UniqueViolation

from ..utils import Cursor, tablerow, dict_from_select, unique_key, Transaction, audit_log, right_click_action, keyvals_from_form
from ..flask import abort, render_page, render_template
from ..forms import ActionForm
from .views import app
from ..i18n import _
from ..generic_views import audit_view

from .forms import ProjectIdentifierForm
from .project_views import project_tabs



@app.route("/projectidentifiers/<int:project_identifiertype_id>/log")
def projectidentifier_log(project_identifiertype_id):
    sql = """SELECT name
             FROM project
             JOIN project_identifiertype ON project_identifiertype.project_id = project.id
             WHERE project_identifiertype.id = %(project_identifiertype_id)s"""
    with Cursor() as cur:
        cur.execute(sql, {"project_identifiertype_id": project_identifiertype_id})
        project = (cur.fetchone() or abort(NotFound))[0]
    return audit_view("project_identifiertype", project_identifiertype_id, url_for(".list_projects"), title=_("Audit Trail: {}").format(project))



@app.route("/projectidentifiers/<int:project_identifiertype_id>", methods=["GET", "POST"])
def edit_projectidentifier(project_identifiertype_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT identifiertype.id, identifiertype.name, identifiertype.datatype, project_identifiertype.regex, project_identifiertype.required, project.name, project.id
                     FROM project_identifiertype
                     JOIN identifiertype ON identifiertype.id = project_identifiertype.identifiertype_id
                     JOIN project ON project.id = project_identifiertype.project_id
                     WHERE project_identifiertype.id = %(project_identifiertype_id)s;"""
            cur.execute(sql, {"project_identifiertype_id": project_identifiertype_id})
            identifiertype_id, identifiertype, datatype, regex, required, project, project_id = cur.fetchone() or abort(NotFound)
            old = {"identifiertype_id": identifiertype_id, "required": required, "regex": regex}
            
            if right_click_action("project_identifiertype", project_identifiertype_id, "Project Identifiers", identifiertype):
                return redirect(request.referrer)
            
            form = ProjectIdentifierForm(request.form if request.method == "POST" else old)
            form.identifiertype_id.choices = ((identifiertype_id, _(identifiertype)),)
            
            if request.method == "POST" and form.validate():
                del form["identifiertype_id"]
                sql = """UPDATE project_identifiertype
                         SET regex = %(regex)s, required = %(required)s
                         WHERE project_identifiertype.id = %(project_identifiertype_id)s;"""
                cur.execute(sql, {"project_identifiertype_id": project_identifiertype_id, **form.data})
                keyvals = keyvals_from_form(form, old)
                audit_log(cur, "Edited", "Project Identifiers", identifiertype, keyvals, "", ("project", project_id), ("project_identifiertype", project_identifiertype_id))
                return redirect(url_for(".list_projectidentifiers", project_id=project_id))
    
    if datatype != "String":
        del form["regex"]
            
    title = _("Edit Project: {}").format(project)
    buttons={"submit": (_("Save"), url_for(".edit_projectidentifier", project_identifiertype_id=project_identifiertype_id)),
             "back": (_("Back"), url_for(".list_projectidentifiers", project_id=project_id))}
    tabs = project_tabs(project_id, ".list_projectidentifiers")
    return render_page("form.html", form=form, buttons=buttons, tabs=tabs, title=title)



@app.route("/projects/<int:project_id>/identifiers/new", methods=["GET", "POST"])
def new_projectidentifier(project_id):
    selected_identifiertype_id = request.form.get("identifiertype_id") or request.args.get("identifiertype_id")
    try:
        selected_identifiertype_id = int(selected_identifiertype_id)
    except TypeError:
        selected_identifiertype_id = None
    selected_datatype = None
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT name FROM project WHERE project.id = %(project_id)s;"""
            cur.execute(sql, {"project_id": project_id})
            row = cur.fetchone() or abort(NotFound)
            project = row[0]

            sql = """SELECT identifiertype.id, identifiertype.name, identifiertype.datatype
                     FROM identifiertype
                     LEFT OUTER JOIN project_identifiertype ON project_identifiertype.project_id = %(project_id)s AND
                                                               project_identifiertype.identifiertype_id = identifiertype.id AND
                                                               project_identifiertype.deleted = false
                     WHERE identifiertype.deleted = false AND project_identifiertype.project_id IS NULL
                     ORDER BY identifiertype.name;"""
            cur.execute(sql, {"project_id": project_id})
            
            identifiertypes = {}
            for identifiertype_id, identifiertype, datatype in cur:
                if identifiertype_id == selected_identifiertype_id:
                    selected_datatype = datatype
                identifiertypes[identifiertype_id] = identifiertype
            
            form = ProjectIdentifierForm(request.form)
            form.identifiertype_id.choices = sorted (((identifiertype_id, _(identifiertype)) for identifiertype_id, identifiertype in identifiertypes.items()), key=lambda x:x[1])
            
            if request.args.get("identifiertype_id"):
                if selected_datatype != "String":
                    del form["regex"]
                del form["identifiertype_id"]
                return render_template("formfields.html", form=form)
            
            if selected_datatype != "String":
                form["regex"].data = ""
            
            if request.method == "POST" and form.validate():
                sql = """INSERT INTO project_identifiertype (project_id, identifiertype_id, regex, required)
                         VALUES (%(project_id)s, %(identifiertype_id)s, %(regex)s, %(required)s)
                         ON CONFLICT ON CONSTRAINT uq_project_identifiertype_project_id_identifiertype_id
                         DO UPDATE SET regex = %(regex)s, required = %(required)s, deleted = false
                         WHERE project_identifiertype.deleted = true
                         RETURNING project_identifiertype.id;"""
                cur.execute(sql, {"project_id": project_id, **form.data})
                ret = cur.fetchone()
                if ret:
                    project_identifiertype_id = ret[0]
                    keyvals = keyvals_from_form(form, {"regex": ""})
                    name = identifiertypes[int(keyvals.pop("Identifier Type")["val"])]
                    audit_log(cur, "Added", "Project Identifiers", name, keyvals, "", ("project", project_id), ("project_identifiertype", project_identifiertype_id))
                return redirect(url_for(".list_projectidentifiers", project_id=project_id))
    
    del form["required"]
    del form["regex"]
    
    title = _("Edit Project: {}").format(project)
    buttons={"submit": (_("Save"), url_for(".new_projectidentifier", project_id=project_id)),
             "back": (_("Back"), url_for(".list_projectidentifiers", project_id=project_id))}
    tabs = project_tabs(project_id, ".list_projectidentifiers")
    return render_page("form.html", form=form, buttons=buttons, tabs=tabs, title=title)



@app.route("/projects/<int:project_id>/identifiers", methods=["GET"])
def list_projectidentifiers(project_id):
    with Cursor() as cur:
        sql = """SELECT name FROM project WHERE project.id = %(project_id)s;"""
        cur.execute(sql, {"project_id": project_id})
        row = cur.fetchone() or abort(NotFound)
        project = row[0]

        sql = """SELECT identifiertype.name, identifiertype.datatype, identifiertype.uniq, project_identifiertype.id, project_identifiertype.regex, project_identifiertype.required, project_identifiertype.deleted
                 FROM project_identifiertype
                 JOIN identifiertype ON identifiertype.id = project_identifiertype.identifiertype_id
                 WHERE project_identifiertype.project_id = %(project_id)s;"""
        cur.execute(sql, {"project_id": project_id})
        
        body = []
        for identifiertype, datatype, uniq, project_identifiertype_id, regex, required, deleted in cur:
            body.append(((identifiertype,
                          datatype,
                          regex,
                          uniq,
                          required),
                         {"id": project_identifiertype_id,
                          "deleted": deleted}))
    
    head = (_("Identifier"), _("Datatype"), _("Regular Expression"), _("Unique"), _("Required"))
    edit_projectidentifier_url = url_for(".edit_projectidentifier", project_identifiertype_id=0)
    actions = ({"name": _("Edit"), "href": edit_projectidentifier_url},
               {"name": _("Delete"), "href": edit_projectidentifier_url, "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": edit_projectidentifier_url, "class": "deleted", "method": "POST"},
               {"name": _("View Audit Trail"), "href": url_for(".projectidentifier_log", project_identifiertype_id=0)})
    table = {"head": head, "body": body, "actions": actions, "new": url_for(".new_projectidentifier", project_id=project_id)}
    
    tabs = project_tabs(project_id, ".list_projectidentifiers")
    title = _("Edit Project: {}").format(project)
    buttons={"back": (_("Back"), url_for(".list_projects"))}
    return render_page("table.html", table=table, tabs=tabs, title=title, buttons=buttons)


