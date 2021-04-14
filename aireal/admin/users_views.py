from flask import session, redirect, url_for, request
from werkzeug import exceptions

from psycopg2.errors import UniqueViolation

from ..utils import (Cursor,
                     dict_from_select,
                     render_page,
                    tablerow,
                    initial_surname,
                    surname_forename,
                    navbar,
                    login_required,
                    valid_groups,
                    abort,
                    unique_key)
from ..wrappers import Local, Attr
from ..logic import crud
from ..auth import send_setpassword_email
from ..i18n import _
from ..view_helpers import log_table
from ..forms import ActionForm

from .views import app
from .forms import UserForm



class AnnotatedTupple(tuple):
    pass



@app.route("/users/<int:user_id>/log")
@login_required("Admin")
def user_log(user_id):
    with Cursor() as cur:
        table = log_table(cur, "users", user_id)
    table["title"] = _("User Log")
    return render_page("table.html", table=table, buttons={"back": (_("Back"),  url_for(".list_users"))})
        
        

@app.route("/users/new", defaults={"user_id": None}, methods=["GET", "POST"])
@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required("Admin")
def edit_user(user_id):
    with Cursor() as cur:
        if user_id is not None:
            sql = """SELECT id, forename, surname, email, restricted, deleted
                        FROM users
                        WHERE id = %(user_id)s;"""
            old = dict_from_select(cur, sql, {"user_id": user_id})
        else:
            old = {}
        
        if user_id is not None:
            form = ActionForm(request.form)
            if request.method == "POST" and form.validate():
                action = form.action.data
                if action == _("Delete") and user_id != session["id"]:
                    crud(cur, "users", {"deleted": True}, old)
                elif action == _("Restore"):
                    crud(cur, "users", {"deleted": False}, old)
                elif action == _("Reset Password"):
                    send_setpassword_email(cur, old["email"])
                return redirect(url_for(".list_users"))
        
        old_groups = []
        group_id_choices = []
        my_group_id = None
        sql = """SELECT groups.id, groups.name, users_groups.user_id
                    FROM groups
                    LEFT OUTER JOIN users_groups ON groups.id = users_groups.group_id AND users_groups.user_id = %(user_id)s
                    WHERE groups.name IN %(valid_groups)s
                    ORDER BY groups.name;"""
        cur.execute(sql, {"user_id": user_id, "valid_groups": tuple(valid_groups)})
        for group_id, group_name, selected in cur:
            group_id_choices.append((group_id, group_name))
            if selected:
                old_groups.append(group_id)
                if user_id == session["id"] and group_name == session["group"]:
                    group_id_choices[-1] = AnnotatedTupple(group_id_choices[-1])
                    group_id_choices[-1].disabled = "disabled"
                    my_group_id = group_id
        old["groups"] = old_groups

        old_projects = []
        project_id_choices = []
        sql = """SELECT projects.id, projects.name, users_projects.user_id
                    FROM projects
                    LEFT OUTER JOIN users_projects ON projects.id = users_projects.project_id AND users_projects.user_id = %(user_id)s
                    WHERE projects.deleted = False
                    ORDER BY projects.name;"""
        cur.execute(sql, {"user_id": user_id})
        for project_id, project_name, selected in cur:
            project_id_choices.append((project_id, project_name))
            if selected:
                old_projects.append(project_id)
        old["projects"] = old_projects
        
        form = UserForm(request.form if request.method=="POST" else old)
        form.groups.choices = group_id_choices
        form.projects.choices = project_id_choices
        
        # Disabled control data will not be returned, therefore add it back in
        if my_group_id is not None and my_group_id not in form.groups.data:
            form.groups.data.append(my_group_id)

        if request.method == "POST" and form.validate():
            new = form.data
            new["name"] = initial_surname(new["forename"], new["surname"])
            try:
                row_id = crud(cur, "users", new, old, groups=group_id_choices, projects=project_id_choices)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                if user_id is None:
                    send_setpassword_email(cur, form.email.data)
                return redirect(url_for(".list_users"))
            
    title = _("Edit User") if user_id is not None else _("New User")
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
                       table={"head": head, "body": body, "title": _("Groups")},
                       buttons={})



@app.route("/users")
@login_required("Admin")
def list_users():
    with Cursor() as cur:
        last_user_id = None
        body = []
        sql = """SELECT users.id, users.surname, users.forename, users.email, users.deleted, groups.name
                FROM users
                LEFT OUTER JOIN users_groups ON users.id = users_groups.user_id
                LEFT OUTER JOIN groups ON users_groups.group_id = groups.id AND groups.name IN %(valid_groups)s
                ORDER BY users.surname, users.forename, groups.name;"""    
        cur.execute(sql, {"valid_groups": tuple(valid_groups)})
        for user_id, surname, forename, email, deleted, group in cur:
            if user_id == last_user_id and group:
                body[-1][0][2] += f", {group}"
            else:
                last_user_id = user_id
                body.append(([surname_forename(surname, forename),
                            email,
                            group],
                            {"id": user_id,
                            "deleted": deleted}))

    head = (_("Name"), _("Email"), _("Groups"))
    actions = ({"name": _("Edit"), "href": url_for(".edit_user", user_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_user", user_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_user", user_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Reset Password"), "href": url_for(".edit_user", user_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".user_log", user_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".edit_user"), "title": _("Users")},
                       buttons=())
