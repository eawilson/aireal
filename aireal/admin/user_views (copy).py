from flask import session, redirect, url_for, request
from werkzeug import exceptions

from psycopg2.errors import UniqueViolation
from psycopg2.extras import execute_batch

from ..utils import Cursor, Transaction, dict_from_select, unique_key, tablerow, audit_log, keyvals_from_form
from ..flask import render_page, valid_roles, abort
from ..wrappers import AnnotatedTupple
from ..logic import perform_edit, perform_delete, perform_restore
from ..auth import send_setpassword_email
from ..i18n import _, __, Date
from ..view_helpers import log_table
from ..forms import ActionForm

from .views import app
from .forms import UserForm
from ..generic_views import audit_view



@app.route("/users/<int:users_id>/log")
def user_log(users_id):
    return audit_view("users", users_id, url_for(".list_users"), title=_("User Log"))



@app.route("/users/<int:users_id>/edit", methods=["GET", "POST"])
def edit_user(users_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT id, forename, surname, email, deleted
                     FROM users
                     WHERE id = %(users_id)s;"""
            old = dict_from_select(cur, sql, {"users_id": users_id})
            
            form = ActionForm(request.form)
            if request.method == "POST" and form.validate():
                audit_action = None
                form_action = form.action.data
                if form_action == _("Delete"):
                    sql = f"UPDATE users SET deleted = true WHERE deleted = false AND id = %(row_id)s;"
                    audit_action = "Deleted"
                elif form_action == _("Restore"):
                    sql = f"UPDATE users SET deleted = false WHERE deleted = true AND id = %(row_id)s;"
                    audit_action = "Restored"
                elif form_action == _("Reset Password"):
                    send_setpassword_email(cur, old["email"])
                
                if audit_action:
                    cur.execute(sql, {"row_id": users_id})
                    if cur.rowcount:
                        audit_log(cur, audit_action, "User", old["name"], {}, "", ("users", users_id))
                return redirect(url_for(".list_users"))
            
            old_roles = []
            role_choices = []
            my_role = None
            sql = """SELECT role.name, role_users.users_id
                     FROM role
                     LEFT OUTER JOIN role_users ON role.name = role_users.name AND role_users.users_id = %(users_id)s
                     WHERE role.name IN %(valid_roles)s
                     ORDER BY role.name;"""
            cur.execute(sql, {"users_id": users_id, "valid_roles": valid_roles()})
            for role, selected in cur:
                role_choices.append((role, __(role)))
                if selected:
                    old_roles.append(role)
                    if users_id == session["id"] and role == session["role"]:
                        role_choices[-1] = AnnotatedTupple(role_choices[-1])
                        role_choices[-1].disabled = "disabled"
                        my_role = role
            old["role"] = old_roles

            old_projects = []
            project_id_choices = []
            sql = """SELECT project.id, project.name, project_users.users_id
                     FROM project
                     LEFT OUTER JOIN project_users ON project.id = project_users.project_id AND project_users.users_id = %(users_id)s
                     WHERE project.deleted = False
                     ORDER BY project.name;"""
            cur.execute(sql, {"users_id": users_id})
            for project_id, project_name, selected in cur:
                project_id_choices.append((project_id, project_name))
                if selected:
                    old_projects.append(project_id)
            old["project"] = old_projects
            
            form = UserForm(request.form if request.method=="POST" else old)
            form.role.choices = role_choices
            form.project.choices = project_id_choices
            
            # Disabled control data will not be returned, therefore add it back in
            if my_role is not None and my_role not in form.role.data:
                form.role.data.append(my_role)
            
            if request.method == "POST" and form.validate():
                new = form.data
                try:
                    row_id = perform_edit(cur, "users", new, old, form)
                except UniqueViolation as e:
                    trans.rollback()
                    form[unique_key(e)].errors = _("Must be unique.")
                else:
                    if users_id is None:
                        send_setpassword_email(cur, form.email.data)
                    return redirect(url_for(".list_users"))

                new = form.data
                new_roles = new.pop("role")
                new_projets = new.pop("project")
                sql = """UPDATE users
                         SET name = %(name)s, fastq_s3_path = %(fastq_s3_path)s, fastq_command_line = %(fastq_command_line)s
                         WHERE id = %(users_id)s;"""
                try:
                    cur.execute(sql, {"project_id": project_id, **form.data})
                except UniqueViolation as e:
                    trans.rollback()
                    form.email.errors = _("Must be unique.")
                else:
                    audit_log(cur, "Edited", "Project", form.name.data, keyvals_from_form(form, old), "", ("project", project_id))
                    return redirect(url_for(".list_projects"))


            
    title = _("Edit User") if users_id is not None else _("New User")
    buttons={"submit": (_("Save"), url_for(".edit_user", users_id=users_id)),
             "back": (_("Cancel"), url_for(".list_users"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/users/new", methods=["GET", "POST"])
def new_user():
    form = UserForm(request.form)    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT role.name
                     FROM role
                     WHERE role.name IN %(valid_roles)s;"""
            cur.execute(sql, { "valid_roles": valid_roles()})
            form.role.choices = sorted(((role[0], _(role[0])) for role in cur), key=lambda x:x[1])

            sql = """SELECT project.id, project.name
                     FROM project
                     WHERE project.deleted = false;"""
            cur.execute(sql)
            projects = dict(cur)
            form.project.choices = sorted(projects.items(), key=lambda x:x[1])
            
            if request.method == "POST" and form.validate():
                new = form.data
                new_roles = new.pop("role")
                new_projets = new.pop("project")
                sql = """INSERT INTO users (surname, forename, email)
                         VALUES (%(surname)s, %(forename)s, %(email)s)
                         RETURNING id, name;"""
                try:
                    cur.execute(sql, new)
                except UniqueViolation as e:
                    trans.rollback()
                    form.email.errors = _("Must be unique.")
                else:
                    users_id, name = cur.fetchone()
                    sql = """INSERT INTO role_users (name, users_id)
                             VALUES (%(name)s, %(users_id)s)
                             ON CONFLICT DO NOTHING;"""
                    values = [{"name": role, "users_id": users_id} for role in new_roles]
                    execute_batch(cur, sql, values)
                    
                    sql = """INSERT INTO project_users (project_id, users_id)
                             VALUES (%(project_id)s, %(users_id)s)
                             ON CONFLICT DO NOTHING;"""
                    values = [{"project_id": project_id, "users_id": users_id} for project_id in new_projets]
                    execute_batch(cur, sql, values)
                    
                    send_setpassword_email(cur, form.email.data)
                    keyvals = keyvals_from_form(form)
                    print(keyvals)
                    keyvals["Projects"] = [projects[project_id] for project_id in keyvals["Projects"]]
                    audit_log(cur, "Created", "User", name, keyvals, "", ("users", users_id))
                    return redirect(url_for(".list_users"))
    
    buttons={"submit": (_("Save"), url_for(".new_user")),
             "back": (_("Cancel"), url_for(".list_users"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("New User"))



@app.route("/users")
def list_users():
    with Cursor() as cur:
        last_users_id = None
        body = []
        sql = """SELECT users.id, users.fullname, users.email, users.last_login_datetime, users.deleted, role_users.name
                 FROM users
                 LEFT OUTER JOIN role_users ON users.id = role_users.users_id AND role_users.name IN %(valid_roles)s
                 ORDER BY users.surname, users.forename, role_users.name;"""    
        cur.execute(sql, {"valid_roles": valid_roles()})
        for users_id, fullname, email, last_login_datetime, deleted, role in cur:
            if users_id == last_users_id:
                body[-1][0][2] += ", {}".format(_(role))
            else:
                last_users_id = users_id
                body.append(([fullname,
                            email,
                            _(role),
                            Date(last_login_datetime)],
                            {"id": users_id,
                            "deleted": deleted}))

    head = (_("Name"), _("Email"), _("Roles"), _("Last Login"))
    actions = ({"name": _("Edit"), "href": url_for(".edit_user", users_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_user", users_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_user", users_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Reset Password"), "href": url_for(".edit_user", users_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".user_log", users_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_user"), "title": _("Users")},
                       buttons=())
