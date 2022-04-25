import pdb

from flask import session, redirect, url_for, request
from werkzeug import exceptions

from psycopg2.errors import UniqueViolation
from psycopg2.extras import execute_batch

from ..utils import Cursor, Transaction, dict_from_select, audit_log, keyvals_from_form
from ..flask import render_page, valid_roles, abort
from ..auth import send_setpassword_email
from ..i18n import _, Date
from ..forms import ActionForm

from .views import app
from .forms import UserForm, UserRoleForm, UserProjectForm
from ..generic_views import audit_view



class AnnotatedTuple(tuple):
    pass



@app.route("/users/<int:users_id>/log")
def user_log(users_id):
    return audit_view("users", users_id, url_for(".list_users"), title=_("User Log"))



@app.route("/users/<int:users_id>/action", methods=["POST"])
def action_user(users_id):
    form = ActionForm(request.form)
    if form.validate():
        audit_action = None
        form_action = form.action.data
        if form_action == _("Delete"):
            sql = f"UPDATE users SET deleted = true WHERE deleted = false AND id = %(users_id)s;"
            audit_action = "Deleted"
        elif form_action == _("Restore"):
            sql = f"UPDATE users SET deleted = false WHERE deleted = true AND id = %(users_id)s;"
            audit_action = "Restored"
        elif form_action == _("Reset Password"):
            send_setpassword_email(cur, old["email"])
        
        if audit_action:
            with Transaction() as trans:
                with trans.cursor() as cur:
                    cur.execute(sql, {"users_id": users_id})
                    if cur.rowcount:
                        sql = """SELECT name FROM users WHERE users.id = %(users_id)s;"""
                        cur.execute(sql, {"users_id": users_id})
                        name = cur.fetchone()[0]
                        audit_log(cur, audit_action, "User", name, {}, "", ("users", users_id))
    return redirect(url_for(".list_users"))



@app.route("/users/<int:users_id>/projects", methods=["GET", "POST"])
def edit_userprojects(users_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            old_projects = set()
            projects = {}
            sql = """SELECT project.id, project.name, project_users.users_id
                     FROM project
                     LEFT OUTER JOIN project_users ON project.id = project_users.project_id AND project_users.users_id = %(users_id)s
                     ORDER BY project.name;"""
            cur.execute(sql, {"users_id": users_id})
            for project_id, project_name, selected in cur:
                projects[project_id] = project_name
                if selected:
                    old_projects.add(project_id)
            
            form = UserProjectForm(request.form if request.method=="POST" else {"project": list(old_projects)})
            form.project.choices = sorted(projects.items(), key=lambda x:x[1])
            
            if request.method == "POST" and form.validate():
                sql = """SELECT name FROM users WHERE users.id = %(users_id)s;"""
                cur.execute(sql, {"users_id": users_id})
                name = cur.fetchone()[0]
                new_projets = set(form.project.data)
                
                inserted_projects = list(new_projets - old_projects)
                if inserted_projects:
                    sql = """INSERT INTO project_users (project_id, users_id)
                             VALUES (%(project_id)s, %(users_id)s)
                             ON CONFLICT DO NOTHING;"""
                    values = [{"project_id": project_id, "users_id": users_id} for project_id in inserted_projects]
                    execute_batch(cur, sql, values)
                    keyvals = {form.project._label: [projects[project_id] for project_id in inserted_projects]}
                    audit_log(cur, "Added", "User", name, keyvals, "", ("users", users_id))
                    
                deleted_projects = list(old_projects - new_projets)
                if deleted_projects:
                    sql = """DELETE FROM project_users
                             WHERE project_id = %(project_id)s AND users_id = %(users_id)s;"""
                    values = [{"project_id": project_id, "users_id": users_id} for project_id in deleted_projects]
                    execute_batch(cur, sql, values)
                    keyvals = {form.project._label: [projects[project_id] for project_id in deleted_projects]}
                    audit_log(cur, "Removed", "User", name, keyvals, "", ("users", users_id))
    
    buttons={"submit": (_("Save"), url_for(".edit_userprojects", users_id=users_id)),
             "back": (_("Cancel"), url_for(".list_users"))}
    tabs = ({"text": _("Main"), "href": url_for(".edit_user", users_id=users_id)},
            {"text": _("Roles"), "href": url_for(".edit_userroles", users_id=users_id)},
            {"text": _("Projects"), "href": "#"})
    return render_page("form.html", form=form, buttons=buttons, tabs=tabs, title=_("Edit User"))



@app.route("/users/<int:users_id>/roles", methods=["GET", "POST"])
def edit_userroles(users_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            old_roles = set()
            role_choices = []
            my_role = None
            sql = """SELECT role.name, role_users.users_id
                     FROM role
                     LEFT OUTER JOIN role_users ON role.name = role_users.name AND role_users.users_id = %(users_id)s
                     WHERE role.name IN %(valid_roles)s
                     ORDER BY role.name;"""
            cur.execute(sql, {"users_id": users_id, "valid_roles": valid_roles()})
            for role, selected in cur:
                role_choices.append((role, _(role)))
                if selected:
                    old_roles.add(role)
                    if users_id == session["id"] and role == session["role"]:
                        role_choices[-1] = AnnotatedTuple(role_choices[-1])
                        role_choices[-1].disabled = "disabled"
                        my_role = role
            
            form = UserRoleForm(request.form if request.method=="POST" else {"role": list(old_roles)})    
            form.role.choices = sorted(role_choices, key=lambda x:x[1])
            # Disabled control data will not be returned to the server, therefore add it back in
            if my_role is not None and my_role not in form.role.data:
                form.role.data.append(my_role)
            
            if request.method == "POST" and form.validate():
                sql = """SELECT name FROM users WHERE users.id = %(users_id)s;"""
                cur.execute(sql, {"users_id": users_id})
                name = cur.fetchone()[0]
                new_roles = set(form.role.data)
                
                inserted_roles = list(new_roles - old_roles)
                if inserted_roles:
                    sql = """INSERT INTO role_users (name, users_id)
                             VALUES (%(name)s, %(users_id)s)
                             ON CONFLICT DO NOTHING;"""
                    values = [{"name": role, "users_id": users_id} for role in inserted_roles]
                    execute_batch(cur, sql, values)
                    keyvals = {form.role._label: inserted_roles}
                    audit_log(cur, "Added", "User", name, keyvals, "", ("users", users_id))
                    
                deleted_roles = list(old_roles - new_roles)
                if deleted_roles:
                    sql = """DELETE FROM role_users
                             WHERE name = %(name)s AND users_id = %(users_id)s;"""
                    values = [{"name": role, "users_id": users_id} for role in deleted_roles]
                    execute_batch(cur, sql, values)
                    keyvals = {form.role._label: deleted_roles}
                    audit_log(cur, "Removed", "User", name, keyvals, "", ("users", users_id))
    
    buttons={"submit": (_("Save"), url_for(".edit_userroles", users_id=users_id)),
             "back": (_("Cancel"), url_for(".list_users"))}
    tabs = ({"text": _("Main"), "href": url_for(".edit_user", users_id=users_id)},
            {"text": _("Roles"), "href": "#"},
            {"text": _("Projects"), "href": url_for(".edit_userprojects", users_id=users_id)})
    return render_page("form.html", form=form, buttons=buttons, tabs=tabs, title=_("Edit User"))
                
                    
                
@app.route("/users/<int:users_id>/edit", methods=["GET", "POST"])
def edit_user(users_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT id, forename, surname, email
                     FROM users
                     WHERE id = %(users_id)s;"""
            old = dict_from_select(cur, sql, {"users_id": users_id})
            form = UserForm(request.form if request.method=="POST" else old)
            if request.method == "POST" and form.validate():
                keyvals = keyvals_from_form(form, old)
                if keyvals:
                    sql = """UPDATE users
                             SET forename = %(forename)s, surname = %(surname)s, email = %(email)s
                             WHERE id = %(users_id)s
                             RETURNING name;"""
                    try:
                        cur.execute(sql, {"users_id": users_id, **form.data})
                    except UniqueViolation as e:
                        trans.rollback()
                        form.email.errors = _("Must be unique.")
                    else:
                        name = cur.fetchone()[0]
                        audit_log(cur, "Edited", "User", name, keyvals, "", ("users", users_id))
                        return redirect(url_for(".edit_user", users_id=users_id))
    
    buttons={"submit": (_("Save"), url_for(".edit_user", users_id=users_id)),
             "back": (_("Cancel"), url_for(".list_users"))}
    tabs = ({"text": _("Main"), "href": "#"},
            {"text": _("Roles"), "href": url_for(".edit_userroles", users_id=users_id)},
            {"text": _("Projects"), "href": url_for(".edit_userprojects", users_id=users_id)})
    return render_page("form.html", form=form, buttons=buttons, tabs=tabs, title=_("Edit User"))



@app.route("/users/new", methods=["GET", "POST"])
def new_user():
    form = UserForm(request.form)    
    if request.method == "POST" and form.validate():
        with Transaction() as trans:
            with trans.cursor() as cur:
                sql = """INSERT INTO users (surname, forename, email)
                         VALUES (%(surname)s, %(forename)s, %(email)s)
                         RETURNING id, name;"""
                try:
                    cur.execute(sql, form.data)
                except UniqueViolation as e:
                    trans.rollback()
                    form.email.errors = _("Must be unique.")
                else:
                    users_id, name = cur.fetchone()
                    send_setpassword_email(cur, form.email.data)
                    audit_log(cur, "Created", "User", name, keyvals_from_form(form), "", ("users", users_id))
                    return redirect(url_for(".edit_user", users_id=users_id))
    
    buttons={"submit": (_("Save"), url_for(".new_user")),
             "back": (_("Cancel"), url_for(".list_users"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("New User"))



@app.route("/users")
def list_users():
    with Cursor() as cur:
        body = []
        sql = """SELECT users.id, users.fullname, users.email, users.last_login_datetime, users.deleted, array_remove(array_agg(role_users.name), NULL)
                 FROM users
                 LEFT OUTER JOIN role_users ON users.id = role_users.users_id AND role_users.name IN %(valid_roles)s
                 GROUP BY users.id
                 ORDER BY users.surname, users.forename;"""    
        cur.execute(sql, {"valid_roles": valid_roles()})
        for users_id, fullname, email, last_login_datetime, deleted, roles in cur:
            body.append(([fullname,
                          email,
                          ", ".join(sorted(_(role) for role in roles)),
                          Date(last_login_datetime)],
                         {"id": users_id,
                          "deleted": deleted}))

    head = (_("Name"), _("Email"), _("Roles"), _("Last Login"))
    actions = ({"name": _("Edit"), "href": url_for(".edit_user", users_id=0)},
               {"name": _("Delete"), "href": url_for(".action_user", users_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".action_user", users_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Reset Password"), "href": url_for(".action_user", users_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".user_log", users_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_user")},
                       title=_("Users"),
                       buttons=())
