from datetime import datetime, timezone

from flask import url_for

from ..utils import Cursor, Transaction, tablerow, iso8601_to_utc
from flask import session, redirect, url_for, request, send_file, current_app
from ..flask import abort, render_page, render_template, Blueprint, sign_token
from ..i18n import _



def reception_navbar():
    return [{"text": _("Collections"), "href":  url_for("Reception.collection_list")}]



Blueprint.navbars["Reception"] = reception_navbar
app = Blueprint("Reception", __name__)



@app.route("/collections")
def collection_list():
    body = []
    head = (_("Name"), _("Project"), _("Samples"), _("Date"))
    actions = ({"name": _("Edit"), "href": url_for(".edit_locationmodel", locationmodel_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_locationmodel", locationmodel_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_locationmodel", locationmodel_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".locationmodel_log", locationmodel_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_collection")}, 
                       title="Location Models")
    _("Reception")
    _("Home")
    _("Site")
    _("Building")
    _("Room")
    _("Archive")
    _("Fridge")
    _("Freezer")
    _("Cupboard")
    _("Rack")
    _("Shelf")
    _("Tray")
    _("Box")
    _("Tube")



@app.route("/collections/new", methods=["GET", "POST"])
def new_collection():
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




@app.route("/collections/<int:collection_id>")
def view_collection(collection_id):
    pass

@app.route("/collections/<int:collection_id>/edit")
def edit_collection(collection_id):
    pass

@app.route("/collections/<int:collection_id>/edit")
def collection_log(collection_id):
    pass

