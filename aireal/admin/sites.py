from sqlalchemy import select, join, or_, and_
from sqlalchemy.exc import IntegrityError

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import engine, login_required, abort, tablerow, render_page
from ..forms import ActionForm
from .views import app
from ..logic import crud
from ..i18n import _
from ..models import sites
from ..view_helpers import log_table
from .forms import SiteForm




@app.route("/sites/<int:site_id>/log")
@login_required("Admin")
def site_log(site_id):
    return render_page("table.html",
                       table=log_table("sites", site_id),
                       buttons={"back": (_("Back"), url_for(".sites_list"))},
                       title=_("Site Log"))
        
        

@app.route("/sites/new", defaults={"site_id": None}, methods=["GET", "POST"])
@app.route("/sites/<int:site_id>/edit", methods=["GET", "POST"])
@login_required("Admin")
def edit_site(site_id):
    with engine.begin() as conn:
        if site_id is not None:
            sql = select([sites.c.id, sites.c.name, sites.c.deleted]). \
                    where(sites.c.id == site_id)
            old = dict(conn.execute(sql).first() or abort(exceptions.BadRequest))
        else:
            old = {}
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                crud(conn, sites, {"deleted": True}, old)
            elif action == _("Restore"):
                crud(conn, sites, {"deleted": False}, old)
            return redirect(refquest.referrer)
        
        form = SiteForm(request.form if request.method=="POST" else old)

        if request.method == "POST" and form.validate():
            new = form.data
            try:
                crud(conn, sites, new, old)
            except IntegrityError as e:
                form[unique_violation_or_reraise(e)].errors = _("Must be unique.")
            else:
                return redirect(form.back)
    
    title = _("Edit Site") if site_id is not None else _("New Site")
    buttons={"submit": (_("Save"), url_for(".edit_site", site_id=site_id)),
             "back": (_("Cancel"), url_for(".sites_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/sites")
@login_required("Admin")
def sites_list():
    sql = select([sites.c.id, sites.c.name, sites.c.deleted]). \
            order_by(sites.c.name)
    
    buttons = {"new": ("", url_for(".edit_site")),
               "back": (_("Back"), url_for(".editmenu"))}
    args = dict(request.args)
    show = args.pop("show", False)
    if show:
        buttons["info"] = (_("Hide Deleted"), url_for(request.endpoint, **request.view_args, **args))
    else:
        sql = sql.where(sites.c.deleted == False)
        buttons["info"] = (_("Show Deleted"), url_for(request.endpoint, show="True", **request.view_args, **args))
    
    body = []
    with engine.connect() as conn:
        for row in conn.execute(sql):
            body.append(((row[sites.c.name],), 
                         {"id": row[sites.c.id],
                          "deleted": row[sites.c.deleted]}))
    
    head = (_("Name"),)
    actions = ({"name": _("Edit"), "href": url_for(".edit_site", site_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_site", site_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_site", site_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".site_log", site_id=0)})

    return render_page("table.html",
                       title="Sites",
                       table={"head": head, "body": body, "actions": actions},
                       buttons=buttons)



