import pdb

from psycopg2.errors import UniqueViolation
from psycopg2.extras import execute_batch

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import Cursor, Transaction, dict_from_select, audit_log, keyvals_from_form, right_click_action
from ..flask import render_page, render_template, abort
from .views import app
from ..i18n import _, Number
from .forms import LocationModelForm, NameForm, ActionForm
from ..generic_views import audit_view



@app.route("/locationmodels/<int:locationmodel_id>/log")
def locationmodel_log(locationmodel_id):
    return audit_view("locationmodel", locationmodel_id, url_for(".locationmodel_list"), title=_("LocationModel Log"))



@app.route("/locationmodels/new", methods=["GET", "POST"])
def new_locationmodel():
    selected_locationtype = request.form.get("locationtype") or request.args.get("locationtype")
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """WITH child AS (
                        SELECT locationtype_locationtype.parent AS parent, locationtype.name AS name
                        FROM locationtype
                        JOIN locationtype_locationtype ON locationtype_locationtype.child = locationtype.name
                        WHERE locationtype.movable = 'inbuilt' AND locationtype.deleted = false
                        )
                     SELECT locationtype.name, locationtype.movable, locationtype.has_temperature, locationtype.has_volume, child.name
                     FROM locationtype
                     LEFT OUTER JOIN child ON child.parent = locationtype.name
                     WHERE locationtype.has_models AND locationtype.deleted = false
                     ORDER BY locationtype.name = %(selected_locationtype)s;"""
            cur.execute(sql, {"selected_locationtype": selected_locationtype})

            locationtype_choices = []
            for locationtype, movable, has_temperature, has_volume, contains in cur:
                locationtype_choices.append((locationtype, _(locationtype)))
            
            form = LocationModelForm(request.form)
            form.locationtype.choices = sorted(locationtype_choices, key=lambda x:x[1])
            
            if selected_locationtype is None or not has_temperature:
                del form["temperature"]
            if selected_locationtype is None or not has_volume:
                del form["volume"]
            if selected_locationtype is None or contains != "Shelf":
                del form["shelves"]
            if selected_locationtype is None or contains != "Tray":
                del form["trays"]
            if selected_locationtype is None or contains != "Position":
                del form["rows"]
                del form["columns"]
            
            if request.args.get("locationtype"):
                del form["locationtype"]
                del form["name"]
                return render_template("formfields.html", form=form)
            
            if request.method == "POST" and form.validate():
                data = form.data
                print(data)
                sql = """INSERT INTO locationmodel (name, locationtype, temperature, volume, movable, childtype, column_count, row_count)
                         VALUES (%(name)s, %(locationtype)s, %(temperature)s, %(volume)s, %(movable)s, %(childtype)s, %(column_count)s, %(row_count)s)
                         RETURNING id;"""
                try:
                    cur.execute(sql, {"name": data["name"],
                                      "locationtype": data["locationtype"],
                                      "temperature": data.get("temperature"),
                                      "volume": data.get("volume"),
                                      "movable": movable,
                                      "childtype": contains,
                                      "column_count": data.get("shelves", data.get("trays", data.get("columns"))),
                                      "row_count": data.get("rows")})
                except UniqueViolation:
                    trans.rollback()
                    form.name.errors = _("Must be unique.")
                else:
                    locationmodel_id = cur.fetchone()[0]
                    audit_log(cur, "Created", "Location Model", data["name"], keyvals_from_form(form), "", ("locationmodel", locationmodel_id))
                    return redirect(url_for(".locationmodel_list"))
    
    buttons={"submit": (_("Save"), url_for(".new_locationmodel")),
             "back": (_("Cancel"), url_for(".locationmodel_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("New Location Model"))



@app.route("/locationmodels/<int:locationmodel_id>/edit", methods=["GET", "POST"])
def edit_locationmodel(locationmodel_id):
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = "SELECT id, name, deleted FROM locationmodel WHERE id = %(locationmodel_id)s;"
            old = dict_from_select(cur, sql, {"locationmodel_id": locationmodel_id})
            name = old["name"]
            
            if right_click_action("locationmodel", locationmodel_id, "Location Model", name):
                return redirect(url_for(".locationmodel_list"))
            
            form = NameForm(request.form if request.method=="POST" else old)
            if request.method == "POST" and form.validate():
                try:
                    sql = """UPDATE locationmodel SET name = %(name)s WHERE id = %(locationmodel_id)s;"""
                    cur.execute(sql, {"locationmodel_id": locationmodel_id, "name": form["name"].data})
                except UniqueViolation as e:
                    trans.rollback()
                    form["name"].errors = _("Must be unique.")
                else:
                    audit_log(cur, "Edited", "Location Model", name, keyvals_from_form(form), "", ("locationmodel", locationmodel_id))
                    return redirect(url_for(".locationmodel_list"))
    
    buttons={"submit": (_("Save"), url_for(".edit_locationmodel", locationmodel_id=locationmodel_id)),
             "back": (_("Cancel"), url_for(".locationmodel_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("Edit Location Model"))



@app.route("/locationmodels")
def locationmodel_list():
    sql = """SELECT id, name, locationtype, temperature, volume, deleted, childtype, column_count, row_count FROM locationmodel;"""
    
    body = []
    with Cursor() as cur:
        cur.execute(sql)
        for locationmodel_id, name, locationtype, temperature, volume, deleted, childtype, column_count, row_count in cur:
            specs = []
            if temperature is not None:
                specs.append(_("Temperature = {}").format(Number(temperature, units="temperature-celsius")))
            if volume is not None:
                specs.append(_("Volume = {}").format(Number(volume, units="volume-milliliter")))
            if childtype == "Shelf":
                specs.append(_("Shelves = {}").format(Number(column_count)))
            elif childtype == "Tray":
                specs.append(_("Trays = {}").format(Number(column_count)))
            elif childtype == "Position":
                specs.append(_("Positions = {} x {}").format(Number(column_count), Number(row_count)))
            body.append(((_(locationtype),
                          name,
                          ", ".join(sorted(specs))),
                         {"id": locationmodel_id, "deleted": deleted}))
            
    head = (_("Type"), _("Name"), _("Specifications"))
    actions = ({"name": _("Edit"), "href": url_for(".edit_locationmodel", locationmodel_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_locationmodel", locationmodel_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_locationmodel", locationmodel_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".locationmodel_log", locationmodel_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": sorted(body), "actions": actions, "new": url_for(".new_locationmodel")}, 
                       title="Location Models",
                       buttons={"back": (_("Back"), url_for(".editmenu"))})



