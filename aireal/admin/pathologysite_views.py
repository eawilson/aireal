from flask import redirect, url_for, request
from werkzeug import exceptions

from psycopg2.errors import UniqueViolation

from ..utils import Cursor, tablerow, dict_from_select, unique_key, Transaction
from ..flask import abort, render_page
from ..forms import ActionForm
from .views import app
from ..logic import perform_edit, perform_delete, perform_restore
from ..i18n import _
from ..view_helpers import log_table

from ..forms import NameForm



@app.route("/pathologysites/<int:pathologysite_id>/log")
def pathologysite_log(pathologysite_id):
    with Cursor() as cur:
        table = log_table(cur, "pathologysite", pathologysite_id)

    buttons={"back": (_("Back"), url_for(".pathologysite_list"))}
    return render_page("table.html", table=table, buttons=buttons, title=_("Pathology Sites Log"))

        

@app.route("/pathologysites/new", defaults={"pathologysite_id": None}, methods=["GET", "POST"])
@app.route("/pathologysites/<int:pathologysite_id>/edit", methods=["GET", "POST"])
def edit_pathologysite(pathologysite_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            if pathologysite_id is not None:
                sql = """SELECT id, name, deleted
                        FROM pathologysite
                        WHERE id = %(pathologysite_id)s;"""
                old = dict_from_select(cur, sql, {"pathologysite_id": pathologysite_id})
            else:
                old = {}
            
            form = ActionForm(request.form)
            if request.method == "POST" and form.validate():
                action = form.action.data
                if action == _("Delete"):
                    perform_delete(cur, "pathologysite", pathologysite_id)
                elif action == _("Restore"):
                    perform_restore(cur, "pathologysite", pathologysite_id)
                return redirect(request.referrer)
            
            form = NameForm(request.form if request.method=="POST" else old)

            if request.method == "POST" and form.validate():
                new = form.data
                try:
                    perform_edit(cur, "pathologysite", new, old, form)
                except UniqueViolation as e:
                    trans.rollback()
                    form[unique_key(e)].errors = _("Must be unique.")
                else:
                    return redirect(url_for(".pathologysite_list"))

    title = _("Edit Pathology Site") if pathologysite_id is not None else _("New Pathology Site")
    buttons={"submit": (_("Save"), url_for(".edit_pathologysite", pathologysite_id=pathologysite_id)),
             "back": (_("Cancel"), url_for(".pathologysite_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/pathologysites")
def pathologysite_list():
    body = []
    with Cursor() as cur:
        sql = """SELECT id, name, deleted
                 FROM pathologysite
                 ORDER BY name;"""
        cur.execute(sql)
        for pathologysite_id, name, deleted in cur:
            body.append(((name,), 
                        {"id": pathologysite_id,
                        "deleted": deleted}))
    
    head = (_("Name"),)
    actions = ({"name": _("Edit"), "href": url_for(".edit_pathologysite", pathologysite_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_pathologysite", pathologysite_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_pathologysite", pathologysite_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".pathologysite_log", pathologysite_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".edit_pathologysite")},
                       title=_("Pathology Sites"),
                       buttons={"back": (_("Back"), url_for(".editmenu"))})
