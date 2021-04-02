from sqlalchemy import select, join, or_, and_
from sqlalchemy.exc import IntegrityError

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import engine, login_required, abort, tablerow, render_page
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
    return render_page("table.html",
                       table=log_table("projects", project_id),
                       buttons={"back": (_("Back"), url_for(".projects_list"))},
                       title=_("Project Log"))
        
        

@app.route("/projects/new", defaults={"project_id": None}, methods=["GET", "POST"])
@app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required("Admin")
def edit_project(project_id):
    with engine.begin() as conn:
        if project_id is not None:
            sql = select([projects.c.id, projects.c.name, projects.c.deleted]). \
                    where(projects.c.id == project_id)
            old = dict(conn.execute(sql).first() or abort(exceptions.BadRequest))
        else:
            old = {}
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                crud(conn, projects, {"deleted": True}, old)
            elif action == _("Restore"):
                crud(conn, projects, {"deleted": False}, old)
            return redirect(request.referrer)
        
        form = ProjectForm(request.form if request.method=="POST" else old)

        if request.method == "POST" and form.validate():
            new = form.data
            try:
                crud(conn, projects, new, old)
            except IntegrityError as e:
                form[unique_violation_or_reraise(e)].errors = _("Must be unique.")
            else:
                return redirect(form.back)
    
    title = _("Edit Project") if project_id is not None else _("New Project")
    buttons={"submit": (_("Save"), url_for(".edit_project", project_id=project_id)),
             "back": (_("Cancel"), url_for(".projects_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/projects")
@login_required("Admin")
def projects_list():
    sql = select([projects.c.id, projects.c.name, projects.c.deleted]). \
            order_by(projects.c.name)
    
    buttons = {"new": ("", url_for(".edit_project")),
               "back": (_("Back"), url_for(".editmenu"))}
    args = dict(request.args)
    show = args.pop("show", False)
    if show:
        buttons["info"] = (_("Hide Deleted"), url_for(request.endpoint, **request.view_args, **args))
    else:
        sql = sql.where(projects.c.deleted == False)
        buttons["info"] = (_("Show Deleted"), url_for(request.endpoint, show="True", **request.view_args, **args))
    
    body = []
    with engine.connect() as conn:
        for row in conn.execute(sql):
            body.append(((row[projects.c.name],), 
                         {"id": row[projects.c.id],
                          "deleted": row[projects.c.deleted]}))
    
    head = (_("Name"),)
    actions = ({"name": _("Edit"), "href": url_for(".edit_project", project_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_project", project_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_project", project_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".project_log", project_id=0)})

    return render_page("table.html",
                       title="Projects",
                       table={"head": head, "body": body, "actions": actions},
                       buttons=buttons)
