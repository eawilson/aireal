import pdb

from psycopg2.errors import UniqueViolation

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import Cursor, Transaction, tablerow, unique_key, dict_from_select
from ..flask import render_page, render_template, abort
from ..forms import ActionForm
from .views import app
from ..logic import perform_edit, perform_delete, perform_restore
from ..i18n import _, __
from ..view_helpers import log_table, pretty
from .forms import LocationModelForm, NameForm, ActionForm



@app.route("/locationmodels/<int:locationmodel_id>/log")
def locationmodel_log(locationmodel_id):
    with Cursor() as cur:
        table = log_table(cur, "locationmodel", locationmodel_id)
    
    table["title"] = _("Location Type Log")
    buttons={"back": (_("Back"), request.referrer)}
    return render_page("table.html", table=table, buttons=buttons)
        


@app.route("/locationmodels/new", methods=["GET", "POST"])
def new_locationmodel():
    selected_locationtype = request.form.get("locationtype") or request.args.get("locationtype")
    locationtype_choices = []
    selected_attr = {}
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT name, movable, attr
                    FROM locationtype
                    WHERE attr != '{}' AND deleted = false AND movable != 'inbuilt'
                    ORDER BY name;"""
            cur.execute(sql)
            for locationtype, movable, attr in cur:
                locationtype_choices.append((locationtype, __(locationtype)))
                if locationtype == selected_locationtype:
                    attr["movable"] = movable
                    selected_attr = attr
            
            form = LocationModelForm()
            form.locationtype.choices = locationtype_choices
            
            for prop, fields in (("has-temperature", ("temperature",)),
                                ("has-shelves", ("shelves", "shelf_width", "shelf_depth")),
                                ("has-trays", ("trays", "boxes")),
                                ("has-positions", ("rows", "columns")),
                                ("has-size", ("width", "depth")),
                                ("contains-material", ("volume", "material"))):
                if prop not in selected_attr:
                    for field in (fields):
                        del form[field]
            
            if "contains-material" in selected_attr:
                sql = f"SELECT id, name FROM tubematerial WHERE deleted = false ORDER BY name;"
                cur.execute(sql)
                form.material.choices = list(cur)
                
            if request.args.get("locationtype"):
                del form["locationtype"]
                del form["name"]
                return render_template("formfields.html", form=form)
            
            component_sql = """INSERT INTO locationmodel (name, locationtype, movable, attr)
                               VALUES (%(name)s, %(locationtype)s, %(movable)s, %(attr)s) RETURNING id;"""
            position_sql = """INSERT INTO position (name, locationmodel_id)
                              VALUES (%(name)s, %(row_id)s);"""
            
            if request.method == "POST" and form.validate(request.form):
                data = form.data
                new = {"name": data["name"],
                    "locationtype": data["locationtype"],
                    "attr": {},
                    "movable": selected_attr["movable"]}
                
                if "temperature" in data:
                    new["temperature"] = data["temperature"]

                if "shelves" in data and "shelf_width" in data and "shelf_depth" in data:
                    new["component_number"] = data["shelves"]
                    cur.execute(component_sql, {"name": "{} Shelf".format(data["name"]),
                                                "locationtype": "Shelf",
                                                "movable": "inbuilt",
                                                "attr": {"internal-width": data["shelf_width"],
                                                         "internal-depth": data["shelf_depth"]}})
                    new["component_id"] = cur.fetchone()[0]
                
                if "trays" in data and "boxes" in data:
                    new["component_number"] = data["trays"]
                    cur.execute(component_sql, {"name": "{} Tray".format(data["name"]),
                                                "locationtype": "Tray",
                                                "movable": "inbuilt",
                                                "attr": {"first-dimension": data["boxes"]}})
                    new["component_id"] = row_id = cur.fetchone()[0]
                    for n in range(1, data["boxes"] + 1):
                        cur.execute(position_sql, {"name": str(n).rjust(2), "row_id": row_id})

                if "rows" in data and "columns" in data:
                    new["attr"]["first-dimension"] = data["columns"]
                
                if "width" in data and "depth" in data:
                    new["attr"]["width"] = data["width"]
                    new["attr"]["depth"] = data["depth"]
                            
                if "volume" in data:
                    new["volume"] = data["volume"]
                
                if "material" in data:
                    new["attr"]["material"] = data["material"]
                
                try:
                    row_id = perform_edit(cur, "locationmodel", new, form=form)
                except UniqueViolation as e:
                    trans.rollback()
                    form[unique_key(e)].errors = _("Must be unique.")
                else:
                    if "rows" in data and "columns" in data:
                        for n in range(0, data["rows"]):
                            for m in range(1, data["columns"] + 1):
                                cur.execute(position_sql, {"name": " {} {}".format(chr(n+65), str(m).rjust(2, "0")),
                                                           "row_id": row_id})
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
            
            form = ActionForm(request.form)
            if request.method == "POST" and form.validate():
                action = form.action.data
                if action == _("Delete"):
                    perform_delete(cur, "locationmodel", row_id=locationmodel_id)
                elif action == _("Restore"):
                    perform_restore(cur, "locationmodel", row_id=locationmodel_id)
                return redirect(url_for(".locationmodel_list"))
            
            form = NameForm(request.form if request.method=="POST" else old)
            if request.method == "POST" and form.validate():
                try:
                    perform_edit(cur, "locationmodel", form.data, old, form)
                except UniqueViolation as e:
                    form[unique_key(e)].errors = _("Must be unique.")
                else:
                    return redirect(url_for(".locationmodel_list"))
    
    buttons={"submit": (_("Save"), url_for(".edit_locationmodel", locationmodel_id=locationmodel_id)),
             "back": (_("Cancel"), url_for(".locationmodel_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("Edit Location Model"))



@app.route("/locationmodels")
def locationmodel_list():
    sql = """SELECT locationmodel.id, locationmodel.name, locationmodel.locationtype, locationmodel.deleted, editrecord.details
             FROM locationmodel
             JOIN editrecord ON editrecord.tablename = 'locationmodel' AND editrecord.action = 'Created' AND editrecord.row_id = locationmodel.id
             ORDER BY locationmodel.locationtype, locationmodel.name;"""
    
    body = []
    with Cursor() as cur:
        cur.execute(sql)
        for locationmodel_id, name, locationtype, deleted, details in cur:
            specs = []
            for item in sorted(details.items()):
                if item[0] not in ("Name", "Type"):
                    specs.append(pretty(item))
                    
            body.append(tablerow(name,
                                 _(locationtype),
                                 ", ".join(sorted(specs)),
                                 id=locationmodel_id,
                                 deleted=deleted))
            
    head = (_("Name"), _("Type"), _("Specifications"))
    actions = ({"name": _("Edit"), "href": url_for(".edit_locationmodel", locationmodel_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_locationmodel", locationmodel_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_locationmodel", locationmodel_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".locationmodel_log", locationmodel_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_locationmodel"), "title": "Location Models"},
                       buttons={"back": (_("Back"), url_for(".editmenu"))})



