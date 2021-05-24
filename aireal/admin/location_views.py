from collections import Counter
import pdb

from psycopg2.errors import UniqueViolation

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import Cursor, Transaction, tablerow, unique_key, dict_from_select
from ..flask import original_referrer, abort, render_page, render_template
from ..forms import ActionForm
from .views import app
from ..logic import perform_edit, perform_delete, perform_restore
from ..i18n import __ as _
from ..view_helpers import log_table
from .forms import LocationForm, NameBarcodeForm




@app.route("/locations/<int:location_id>/log")
def location_log(location_id):
    with Cursor() as cur:
        table = log_table(cur, "location", location_id)
    
    table["title"] = _("Location Log")
    buttons={"back": (_("Back"), request.referrer)}
    return render_page("table.html", table=table, buttons=buttons)
        
        

@app.route("/locations/<int:location_id>/edit", methods=["GET", "POST"])
def edit_location(location_id):
    referrer = original_referrer()
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = "SELECT id, name, barcode deleted FROM location WHERE id = %(location_id)s;"
            old = dict_from_select(cur, sql, {"location_id": location_id})
            
            form = ActionForm(request.form)
            if request.method == "POST" and form.validate():
                action = form.action.data
                if action == _("Delete"):
                    perform_delete(cur, "location", row_id=location_id)
                elif action == _("Restore"):
                    perform_restore(cur, "location", row_id=location_id)
                return redirect(referrer)
            
            form = NameBarcodeForm(request.form if request.method=="POST" else old)
            if request.method == "POST" and form.validate():
                try:
                    perform_edit(cur, "location", form.data, old, form)
                except UniqueViolation as e:
                    form[unique_key(e)].errors = _("Must be unique.")
                else:
                    return redirect(referrer)
    
    buttons={"submit": (_("Save"), url_for(".edit_location", location_id=location_id, referrer=referrer)),
             "back": (_("Cancel"), referrer)}
    return render_page("form.html", form=form, buttons=buttons, title=_("Edit Location Model"))



@app.route("/locations/<int:location_id>/new", methods=["GET", "POST"])
def new_location(location_id):
    referrer = original_referrer()
    selected_type = request.form.get("locationtype") or request.args.get("locationtype")
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT name
                    FROM location
                    WHERE id = %(location_id)s AND deleted = false AND movable != 'mobile';"""
            cur.execute(sql, {"location_id": location_id})
            row = cur.fetchone()
            if not row:
                return redirect(url_for(".location_list"))
            title = row[0]
            
            sql = """SELECT childmodel.id, childmodel.name, childmodel.locationtype, childmodel.component_number, componentmodel.id AS comp_id, componentmodel.locationtype AS comp_type
                    FROM location AS parent
                    JOIN locationmodel AS parentmodel ON parent.locationmodel_id = parentmodel.id
                    JOIN locationtype_locationtype ON locationtype_locationtype.parent = parentmodel.locationtype
                    JOIN locationmodel AS childmodel ON childmodel.locationtype = locationtype_locationtype.child
                    LEFT OUTER JOIN locationmodel AS componentmodel ON childmodel.component_id = componentmodel.id
                    WHERE parent.id = %(location_id)s AND parent.deleted = false AND parent.movable != 'mobile' AND childmodel.movable = 'fixed' AND childmodel.deleted = false
                    ORDER BY childmodel.locationtype, childmodel.name;"""
            
            cur.execute(sql, {"location_id": location_id})
            type_choices = []
            model_choices = []
            components = {}
            for row_id, model, locationtype, component_number, component_id, componenttype in cur:
                if not type_choices or type_choices[-1][0] != locationtype:
                    type_choices.append((locationtype, _(locationtype)))
                if selected_type == locationtype:
                    model_choices.append((row_id, model))
                    if component_number:
                        components[row_id] = {"id": component_id, "number": component_number, "type": componenttype}
            
            form = LocationForm(request.form)
            form.locationtype.choices = type_choices
            form.locationmodel_id.choices = model_choices
            
            if request.args.get("locationtype"):
                del form["name"]
                del form["barcode"]
                del form["locationtype"]
                return render_template("formfields.html", form=form)
            
            if request.method == "POST" and form.validate():
                new = form.data
                new.pop("locationtype")
                new["parent_id"] = location_id
                new["movable"] = 'fixed'
                try:
                    new_id = perform_edit(cur, "location", new, form=form)
                except UniqueViolation as e:
                    form[unique_key(e)].errors = _("Must be unique.")
                else:
                    if new["locationmodel_id"] in components:
                        sql = """INSERT INTO location (name, movable, locationmodel_id, parent_id) 
                                VALUES (%(name)s, 'inbuilt', %(locationmodel_id)s, %(parent_id)s);"""
                        component = components[new["locationmodel_id"]]
                        for number in range(1, component["number"] + 1):
                            cur.execute(sql, {"name": "{} {}".format(component["type"], number),
                                            "locationmodel_id": component["id"],
                                            "parent_id": new_id})
                    return redirect(referrer)
    
    buttons={"submit": (_("Save"), url_for(".new_location", location_id=location_id, referrer=referrer)),
             "back": (_("Cancel"), referrer)}
    return render_page("form.html", form=form, buttons=buttons, title=_("New Location"))



@app.route("/locations", defaults={"location_id": 1})
@app.route("/locations/<int:location_id>")
def location_list(location_id):
    with Cursor() as cur:
        sql = """WITH RECURSIVE child (id, parent_id, name, depth) AS (
                     SELECT id, parent_id, name, 1
                     FROM location
                     WHERE id = %(location_id)s
                 UNION ALL
                     SELECT l.id, l.parent_id, l.name, child.depth + 1
                     FROM child, location l
                     WHERE child.parent_id = l.id
                 )
                 SELECT id, name
                 FROM child
                 ORDER BY depth DESC;"""
        
        breadcrumbs = []
        cur.execute(sql, {"location_id": location_id})
        for row_id, name in cur:
            breadcrumbs.append((name, url_for(".location_list", location_id=row_id), row_id == location_id))
        
        sql = """SELECT l.id, l.name, l.deleted, m.name AS model, m.locationtype, p.name AS position
                 FROM location AS l
                 JOIN locationmodel AS m ON l.locationmodel_id = m.id
                 LEFT OUTER JOIN position p ON l.position_id = p.id
                 WHERE l.parent_id = %(location_id)s AND l.id != l.parent_id AND l.movable = 'fixed'
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
