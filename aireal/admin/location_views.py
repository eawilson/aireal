from collections import Counter
import pdb

from psycopg2.errors import UniqueViolation

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import Cursor, abort, tablerow, render_page, unique_key, original_referrer
from ..forms import ActionForm
from .views import app
from .. import logic
from ..i18n import __ as _
from ..view_helpers import log_table
from .forms import LocationForm, NameBarcodeForm




@app.route("/locations/<int:location_id>/log")
def location_log(location_id):
    with Cursor as cur:
        table = log_table(cur, "location", location_id)
    
    table["title"] = _("Location Log")
    buttons={"back": (_("Back"), request.referrer)}
    return render_page("table.html", table=table, buttons=buttons)
        
        

@app.route("/locations/<int:location_id>/edit", methods=["GET", "POST"])
def edit_location(location_id):
    referrer = original_referrer()
    
    with engine.begin() as conn:
        if location_id is not None:
            sql = select([location.c.id, location.c.name, location.c.deleted]). \
                    where(location.c.id == location_id)
            old = dict(conn.execute(sql).first() or abort(exceptions.BadRequest))
        else:
            old = {}
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                logic.edit(conn, location, {"deleted": True}, old)
            elif action == _("Restore"):
                logic.edit(conn, location, {"deleted": False}, old)
            return redirect(referrer)
        
        form = NameBarcodeForm(request.form if request.method=="POST" else old)

        if request.method == "POST" and form.validate():
            new = form.data
            try:
                logic.edit(conn, location, new, old)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                return redirect(referrer)
    
    title = _("Edit Site") if location_id is not None else _("Edit Location")
    buttons={"submit": (_("Save"), url_for(".edit_location", location_id=location_id, referrer=referrer)),
             "back": (_("Cancel"), referrer)}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/locations/<int:location_id>/new", methods=["GET", "POST"])
def new_location(location_id):
    referrer = original_referrer()
    selected_type = request.form.get("locationtype") or request.args.get("locationtype")
    
    sql = """SELECT parent.name AS parent, childmodel.locationtype, childmodel.id as row_id, childmodel.name AS model
             FROM location AS parent
             JOIN locationmodel AS parentmodel ON parent.locationmodel_id = parentmodel.id
             LEFT OUTER JOIN locationtype_locationtype ON locationtype_locationtype.parent = parentmodel.locationtype
             LEFT OUTER JOIN locationmodel AS childmodel ON (childmodel.locationtype = locationtype_locationtype.child AND childmodel.movable = 'fixed')
             WHERE parent.id = %(location_id)s AND parent.deleted = false
             ORDER BY childmodel.locationtype, childmodel.name;"""
    
    with Cursor() as cur:
        cur.execute(sql, {"location_id": location_id})
        
        type_choices = []
        model_choices = []
        for title, locationtype, row_id, model in cur:
            if type_choices and type_choices[-1][0] != locationtype:
                type_choices.append((locationtype, _(locationtype)))
            if selected_type == locationtype:
                model_choices.append(row_id, model)

        form = LocationForm(request.form)
        form.locationrtype.choices = type_choices
        
        if selected_type:
            form.locationmodel_id.choices = model_choices
        #else:
            
        
        
        
        
        #if request.method == "POST" and form.validate():
            #new = form.data
            #new["parent_id"] = parent_id
            #new["site_id"] = row["parent_site_id"]
            #try:
                #location_id = logic.edit(conn, location, new, locationmodel_id_choices=locationmodel_id_choices)
            #except UniqueViolation as e:
                #form[unique_key(e)].errors = _("Must be unique.")
            #else:
                #if row["parent_site_id"] == 1:
                    #conn.execute(location.update().where(location.c.id == location_id), {"site_id": location_id})
                #return redirect(referrer)
    
    #title = _("New Location")
    #buttons={"submit": (_("Save"), url_for(".new_location", parent_id=parent_id, referrer=referrer)),
             #"back": (_("Cancel"), url_for(".location_list"))}
    #return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/locations", defaults={"location_id": 1})
@app.route("/locations/<int:location_id>")
def location_list(location_id):
    sql = """WITH RECURSIVE child (id, parent_id, name, depth) AS (
                 SELECT id, parent_id, name, 1
                 FROM location
                 WHERE id = %(location_id)s
             UNION ALL
                 SELECT l.id, l.parent_id, l.name, child.depth + 1
                 FROM child, location l
                 WHERE child.parent_id = l.id AND l.id != l.parent_id
             )
             SELECT id, name
             FROM child
             ORDER BY depth DESC;"""
             
    with Cursor() as cur:
        
        breadcrumbs = []
        cur.execute(sql, {"location_id": location_id})
        for row_id, name in cur:
            breadcrumbs.append((name, url_for(".location_list", location_id=row_id), row_id == location_id))
        
        sql = """SELECT l.id, l.name, l.deleted, m.name AS model, m.locationtype, p.name AS position
                 FROM location AS l
                 JOIN locationmodel AS m ON l.locationmodel_id = m.id
                 LEFT OUTER JOIN position p ON l.position_id = p.id
                 WHERE l.parent_id = %(location_id)s AND l.id != l.parent_id
                 ORDER BY p.id, l.name;"""
        body = []
        cur.execute(sql, {"location_id": location_id})
        for row_id, name, deleted, model, locationtype, position in cur:
            body.append(tablerow(name,
                                 model,
                                 locationtype,
                                 id=row_id,
                                 deleted=deleted))
    
    head = (_("Name"), _("Model"), _("Type"))
    actions = ({"name": _("View"), "href": url_for(".location_list", location_id=0)},
               {"name": _("Edit"), "href": url_for(".edit_location", location_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_location", location_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_location", location_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".location_log", location_id=0)})
    
    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_location", location_id=location_id), "breadcrumbs": breadcrumbs},
                       buttons = {"back": (_("Back"), url_for(".editmenu"))})
