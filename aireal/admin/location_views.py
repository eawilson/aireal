from collections import Counter
import pdb

from psycopg2.errors import UniqueViolation
from psycopg2.extras import execute_batch

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import Cursor, Transaction, dict_from_select, keyvals_from_form, audit_log, right_click_action
from ..flask import abort, render_page, render_template
from ..forms import ActionForm
from .views import app
from ..logic import perform_edit, perform_delete, perform_restore
from ..i18n import __ as _
from ..view_helpers import log_table
from .forms import LocationForm, NameBarcodeForm
from ..generic_views import audit_view



@app.route("/locations/<int:location_id>/log")
def location_log(location_id):
    return audit_view("location", location_id, request.referrer, title=_("LocationModel Log"))



@app.route("/locations/<int:location_id>/edit", methods=["GET", "POST"])
def edit_location(location_id):
    referrer = request.args.get("referrer") or request.referrer
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = "SELECT id, name, barcode deleted FROM location WHERE id = %(location_id)s;"
            old = dict_from_select(cur, sql, {"location_id": location_id})
            name = old["name"]
            
            if right_click_action("location", location_id, "Location", name):
                return redirect(referrer)
            
            form = NameBarcodeForm(request.form if request.method=="POST" else old)
            if request.method == "POST" and form.validate():
                try:
                    sql = """UPDATE location SET name = %(name)s, barcode = %(barcode)s WHERE id = %(location_id)s;"""
                    cur.execute(sql, {"location_id": location_id, "name": form["name"].data, "barcode": form["barcode"].data})
                except UniqueViolation as e:
                    trans.rollback()
                    if e.diag.constraint_name == "ix_location_name":
                        form["name"].errors = _("Must be unique.")
                    elif e.diag.constraint_name == "uq_location_barcode":
                        form["barcode"].errors = _("Must be unique.")
                else:
                    audit_log(cur, "Edited", "Location", name, keyvals_from_form(form), "", ("location", location_id))
                    return redirect(referrer)

    buttons={"submit": (_("Save"), url_for(".edit_location", location_id=location_id, referrer=referrer)),
             "back": (_("Cancel"), referrer)}
    return render_page("form.html", form=form, buttons=buttons, title=_("Edit Location"))



@app.route("/locations/<int:location_id>/new", methods=["GET", "POST"])
def new_location(location_id):
    referrer = request.args.get("referrer") or request.referrer
    
    selected_locationtype = request.form.get("locationtype") or request.args.get("locationtype")
    try:
        selected_locationmodel_id = int(request.form.get("locationmodel_id"))
    except (ValueError, TypeError):
        selected_locationmodel_id = None
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT name, locationtype FROM location WHERE id = %(location_id)s AND NOT deleted AND movable <> 'movable';"""
            cur.execute(sql, {"location_id": location_id})
            row = cur.fetchone()
            if not row:
                return redirect(referrer)
            title, locationtype = row
            
            sql = """SELECT lm.locationtype, lm.id, lm.name, lm.childtype, lm.row_count, lm.column_count, lm.temperature, lm.volume, lm.id = %(selected_locationmodel_id)s AS sort_order
                     FROM locationtype_locationtype
                     JOIN locationmodel AS lm ON lm.locationtype = locationtype_locationtype.child
                     WHERE locationtype_locationtype.parent = %(locationtype)s
                     UNION ALL
                     SELECT lt.name, NULL AS lm_id, NULL, NULL, NULL, NULL, NULL, NULL, false AS sort_order
                     FROM locationtype_locationtype
                     JOIN locationtype AS lt ON lt.name = locationtype_locationtype.child
                     WHERE locationtype_locationtype.parent = %(locationtype)s AND NOT lt.has_models
                     ORDER BY sort_order;"""
            cur.execute(sql, {"locationtype": locationtype, "selected_locationmodel_id": selected_locationmodel_id})
            locationtype_choices = set()
            locationmodel_id_choices = {}
            for locationtype, locationmodel_id, locationmodel, childtype, row_count, column_count, temperature, volume, sort_oder in cur:
                locationtype_choices.add(locationtype)
                if locationtype == selected_locationtype and locationmodel_id is not None:
                    locationmodel_id_choices[locationmodel_id] = locationmodel
            
            form = LocationForm(request.form)
            form.locationtype.choices = sorted(((locationtype, _(locationtype)) for locationtype in locationtype_choices), key=lambda x:x[1])
            form.locationmodel_id.choices = sorted((locationmodel_id_choices.items()), key=lambda x:x[1])
            
            print(locationtype_choices, locationmodel_id_choices)
            if not locationmodel_id_choices:
                del form["locationmodel_id"]
            
            if request.args.get("locationtype"):
                del form["name"]
                del form["barcode"]
                del form["locationtype"]
                return render_template("formfields.html", form=form)
            
            if request.method == "POST" and form.validate():
                data = form.data
                
                sql = """INSERT INTO location (name, barcode, locationtype, locationmodel_id, movable, temperature, parent_id)
                         VALUES (%(name)s, %(barcode)s, %(locationtype)s, %(locationmodel_id)s, %(movable)s, %(temperature)s, %(parent_id)s)
                         RETURNING id;"""
                try:
                    cur.execute(sql, {"name": data["name"],
                                      "barcode": data["barcode"],
                                      "locationtype": data["locationtype"],
                                      "locationmodel_id": data.get("locationmodel_id"),
                                      "movable": "fixed",
                                      "temperature": temperature,
                                      "volume": volume,
                                      "parent_id": location_id})
                except UniqueViolation:
                    trans.rollback()
                    form.name.errors = _("Must be unique.")
                else:
                    new_id = cur.fetchone()[0]
                    keyvals = keyvals_from_form(form, {"barcode": None})
                    if "Model" in keyvals:
                        keyvals["Model"] = locationmodel_id_choices[keyvals["Model"]]
                    audit_log(cur, "Created", "Location", data["name"], keyvals, "", ("location", new_id))
                    
                    if childtype is not None:
                        children = []
                        for col in range(1, column_count + 1):
                            for row in range(row_count or 1):
                                name = "{}{i:02}".format(chr(row + 65), col) if row_count else str(col)
                                children.append({"name": name, "locationtype": childtype, "parent_id": new_id})
                        sql = """INSERT INTO location (name, locationtype, movable, parent_id)
                                 VALUES (%(name)s, %(locationtype)s, 'inbuilt', %(parent_id)s);"""
                        execute_batch(cur, sql, children)
                    return redirect(referrer)
    
    buttons={"submit": (_("Save"), url_for(".new_location", location_id=location_id, referrer=referrer)),
             "back": (_("Cancel"), referrer)}
    return render_page("form.html", form=form, buttons=buttons, title=_("New Location"))



@app.route("/locations", defaults={"location_id": None})
@app.route("/locations/<int:location_id>")
def location_list(location_id):
    with Cursor() as cur:
        sql = """WITH RECURSIVE child (id, parent_id, name, depth) AS (
                     SELECT id, parent_id, name, 1
                     FROM location
                     WHERE (id = %(location_id)s) OR (%(location_id)s IS NULL AND name = 'Home')
                 UNION ALL
                     SELECT location.id, location.parent_id, location.name, child.depth + 1
                     FROM child, location
                     WHERE child.parent_id = location.id
                 )
                 SELECT id, name
                 FROM child
                 ORDER BY depth DESC;"""
        
        breadcrumbs = []
        cur.execute(sql, {"location_id": location_id})
        for row_id, name in cur:
            breadcrumbs.append((name, url_for(".location_list", location_id=row_id), row_id == location_id))
            location_id = row_id
        
        sql = """SELECT location.id, location.name, location.locationtype, location.deleted, coalesce(locationmodel.name, '')
                 FROM location
                 LEFT OUTER JOIN locationmodel ON location.locationmodel_id = locationmodel.id
                 WHERE location.parent_id = %(location_id)s AND location.movable = 'fixed';"""
        body = []
        cur.execute(sql, {"location_id": location_id})
        for row_id, name, locationtype, deleted, model in cur:
            body.append(((_(locationtype),
                          name,
                          model),
                         {"id": row_id, "deleted": deleted}))
    
    head = (_("Type"), _("Name"), _("Model"))
    actions = ({"name": _("View"), "href": url_for(".location_list", location_id=0)},
               {"name": _("Edit"), "href": url_for(".edit_location", location_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_location", location_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_location", location_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".location_log", location_id=0)})
    
    return render_page("table.html",
                       table={"head": head, "body": sorted(body), "actions": actions, "new": url_for(".new_location", location_id=location_id)},
                       breadcrumbs=breadcrumbs,
                       buttons={"back": (_("Back"), url_for(".editmenu"))})
