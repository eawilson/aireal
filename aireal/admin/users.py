from sqlalchemy import select, join, and_
from sqlalchemy.exc import IntegrityError

from flask import session, redirect, url_for, request
from werkzeug import exceptions

from ..models import (users,
                     groups,
                     sites,
                     projects,
                     users_sites,
                     users_projects,
                     users_groups)
from ..utils import (render_page,
                    tablerow,
                    initial_surname,
                    surname_forename,
                    engine,
                    navbar,
                    login_required,
                    valid_groups,
                    abort,
                    unique_violation_or_reraise)
from ..wrappers import Local
from ..logic import crud
from ..auth import send_setpassword_email
from ..i18n import _
from ..view_helpers import log_table
from ..forms import ActionForm

from .views import app
from .forms import UserForm


@app.route("/users/<int:user_id>/log")
@login_required("Admin")
def user_log(user_id):
    return render_page("table.html",
                       table=log_table("users", user_id),
                       buttons={"back": (_("Back"),  url_for(".list_users"))},
                       title=_("User Log"))
        
        

@app.route("/users/new", defaults={"user_id": None}, methods=["GET", "POST"])
@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required("Admin")
def edit_user(user_id):
    with engine.begin() as conn:
        if user_id is not None:
            sql = select([users.c.id, users.c.forename, users.c.surname, users.c.email, users.c.restricted, users.c.deleted]). \
                    where(users.c.id == user_id)
            old = dict(conn.execute(sql).first() or abort(exceptions.BadRequest))
        else:
            old = {}
        
        if user_id is not None:
            form = ActionForm(request.form)
            if request.method == "POST" and form.validate():
                action = form.action.data
                if action == _("Delete") and user_id != session["id"]:
                    crud(conn, users, {"deleted": True}, old)
                elif action == _("Restore"):
                    crud(conn, users, {"deleted": False}, old)
                elif action == _("Reset Password"):
                    send_setpassword_email(old["email"], conn)
                return redirect(url_for(".list_users"))
        
        sql = select([groups.c.id, groups.c.name, users_groups.c.user_id]). \
                select_from(join(groups, users_groups, and_(groups.c.id == users_groups.c.group_id, users_groups.c.user_id == user_id), isouter=True)). \
                where(groups.c.name.in_(valid_groups)). \
                order_by(groups.c.name)
        old_groups = []
        group_id_choices = []
        my_group_id = None
        for row in conn.execute(sql):
            group_id_choices.append((row[groups.c.id], row[groups.c.name]))
            if row[users_groups.c.user_id] is not None:
                old_groups.append(row[groups.c.id])
                if user_id == session["id"] and row[groups.c.name] == session["group"]:
                    group_id_choices[-1] += ("disabled",)
                    my_group_id = row[groups.c.id]
        old["groups"] = old_groups
        sql = select([sites.c.name, sites.c.id, users_sites.c.user_id]). \
                select_from(join(sites, users_sites, and_(sites.c.id == users_sites.c.site_id, users_sites.c.user_id == user_id), isouter=True)). \
                where(sites.c.deleted == False). \
                order_by(sites.c.name)
        old_sites = []
        site_id_choices = []
        for row in conn.execute(sql):
            site_id_choices += [(row[sites.c.id], row[sites.c.name])]
            if row[users_sites.c.user_id] is not None:
                old_sites.append(row[sites.c.id])
        old["sites"] = old_sites
        
        sql = select([projects.c.name, projects.c.id, users_projects.c.user_id]). \
                select_from(join(projects, users_projects, and_(projects.c.id == users_projects.c.project_id, users_projects.c.user_id == user_id), isouter=True)). \
                where(projects.c.deleted == False). \
                order_by(projects.c.name)
        old_projects = []
        project_id_choices = []
        for row in conn.execute(sql):
            project_id_choices += [(row[projects.c.id], row[projects.c.name])]
            if row[users_projects.c.user_id] is not None:
                old_projects.append(row[projects.c.id])
        old["projects"] = old_projects
        
        form = UserForm(request.form if request.method=="POST" else old)
        form.groups.choices = group_id_choices
        form.sites.choices = site_id_choices
        form.projects.choices = project_id_choices
        
        # Disabled control data will not be returned, therefore add it back in
        if my_group_id is not None and my_group_id not in form.groups.data:
            form.groups.data.append(my_group_id)

        if request.method == "POST" and form.validate():
            new = form.data
            new["name"] = initial_surname(new["forename"], new["surname"])
            try:
                row_id = crud(conn, users, new, old, groups=group_id_choices,
                                                     sites=site_id_choices,
                                                     projects=project_id_choices)
            except IntegrityError as e:
                form[unique_violation_or_reraise(e)].errors = _("Must be unique.")
            else:
                if user_id is None:
                    send_setpassword_email(form.email.data, conn)
                return redirect(url_for(".list_users"))
                
    title = _("Edit") if user_id is not None else _("New")
    buttons={"submit": (_("Save"), url_for(".edit_user", user_id=user_id)),
             "back": (_("Cancel"), url_for(".list_users"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/groups")
@login_required("Admin")
def list_groups():
    sql = select([groups.c.name]).order_by(groups.c.name)
    
    body = []
    with engine.connect() as conn:
        for row in conn.execute(sql):
            body += [tablerow(row[groups.c.name])]
            
    head = (_("Name"),)
    
    return render_page("table.html",
                       title="Groups",
                       table={"head": head, "body": body},
                       buttons={})



@app.route("/users")
@login_required("Admin")
def list_users():
    sql = select([users.c.id, users.c.surname, users.c.forename, users.c.email, users.c.deleted, groups.c.name]). \
            select_from(join(users, users_groups, users.c.id == users_groups.c.user_id, isouter=True). \
                join(groups, and_(users_groups.c.group_id == groups.c.id, groups.c.name.in_(valid_groups)), isouter=True)). \
            order_by(users.c.surname, users.c.forename, groups.c.name)
    
    buttons = {"new": ("", url_for(".edit_user"))}
    args = dict(request.args)
    show = args.pop("show", False)
    if show:
        buttons["info"] = (_("Hide Deleted"), url_for(request.endpoint, **request.view_args, **args))
    else:
        sql = sql.where(users.c.deleted == False)
        buttons["info"] = (_("Show Deleted"), url_for(request.endpoint, show="True", **request.view_args, **args))
    
    last_user_id = None
    body = []
    with engine.connect() as conn:
        for row in conn.execute(sql):
            if row[users.c.id] == last_user_id:
                body[-1][0][2] += ", "+row[groups.c.name]
            else:
                last_user_id = row[users.c.id]
                body.append(([surname_forename(row[users.c.surname], row[users.c.forename]),
                              row[users.c.email],
                              row[groups.c.name]],
                             {"id": row[users.c.id],
                              "deleted": row[users.c.deleted]}))
    
    head = (_("Name"), _("Email"), _("Groups"))
    actions = ({"name": _("Edit"), "href": url_for(".edit_user", user_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_user", user_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_user", user_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Reset Password"), "href": url_for(".edit_user", user_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".user_log", user_id=0)})

    return render_page("table.html",
                       title="Users",
                       table={"head": head, "body": body, "actions": actions},
                       buttons=buttons)
