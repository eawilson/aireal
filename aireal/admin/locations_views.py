from collections import Counter
import pdb

from psycopg2.errors import UniqueViolation

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import Cursor, login_required, abort, tablerow, render_page, unique_key, original_referrer
from ..forms import ActionForm
from .views import app
from ..logic import crud
from ..i18n import _
from ..models import locations, locationmodels, locationtypes, locationtypes_locationtypes
from ..view_helpers import log_table
from .forms import LocationForm, NameBarcodeForm




@app.route("/locations/<int:location_id>/log")
@login_required("Admin")
def location_log(location_id):
    with Cursor as cur:
        table = log_table(cur, "locations", location_id)
    
    table["title"] = _("Location Log")
    buttons={"back": (_("Back"), request.referrer)}
    return render_page("table.html", table=table, buttons=buttons)
        
        

@app.route("/locations/<int:location_id>/edit", methods=["GET", "POST"])
@login_required("Admin")
def edit_location(location_id):
    referrer = original_referrer()
    
    with engine.begin() as conn:
        if location_id is not None:
            sql = select([locations.c.id, locations.c.name, locations.c.deleted]). \
                    where(locations.c.id == location_id)
            old = dict(conn.execute(sql).first() or abort(exceptions.BadRequest))
        else:
            old = {}
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                crud(conn, locations, {"deleted": True}, old)
            elif action == _("Restore"):
                crud(conn, locations, {"deleted": False}, old)
            return redirect(referrer)
        
        form = NameBarcodeForm(request.form if request.method=="POST" else old)

        if request.method == "POST" and form.validate():
            new = form.data
            try:
                crud(conn, locations, new, old)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                return redirect(referrer)
    
    title = _("Edit Site") if location_id is not None else _("Edit Location")
    buttons={"submit": (_("Save"), url_for(".edit_location", location_id=location_id, referrer=referrer)),
             "back": (_("Cancel"), referrer)}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/locations/<int:parent_id>/new", methods=["GET", "POST"])
@login_required("Admin")
def new_location(parent_id):
    referrer = original_referrer()

    parents = locations.alias("parents")
    parentmodels = locationmodels.alias("parentmodels")
    parenttypes = locationtypes.alias("parenttypes")
    sql = select([locationmodels.c.id, locationmodels.c.name, parents.c.site_id.label("parent_site_id")]). \
            select_from(join(parents, parentmodels, parents.c.locationmodel_id == parentmodels.c.id). \
                        join(parenttypes, parentmodels.c.locationtype == parenttypes.c.name). \
                        join(locationbasetypes_locationbasetypes, locationbasetypes_locationbasetypes.c.parent_id == parenttypes.c.locationbasetype_id). \
                        join(locationtypes, locationbasetypes_locationbasetypes.c.child_id == locationtypes.c.locationbasetype_id). \
                        join(locationmodels, locationmodels.c.locationtype == locationtypes.c.name). \
                        join(locationbasetypes, locationbasetypes.c.id == locationtypes.c.locationbasetype_id)). \
            where(and_(parents.c.id == parent_id, locationmodels.c.deleted == False, locationbasetypes.c.fixed == True)). \
            order_by(locationmodels.c.name)
    
    with engine.begin() as conn:
        locationmodel_id_choices = []
        for row in conn.execute(sql):
            locationmodel_id_choices.append(row[:2])
        
        form = LocationForm(request.form if request.method=="POST" else {})
        form.locationmodel_id.choices = locationmodel_id_choices
        if request.method == "POST" and form.validate():
            new = form.data
            new["parent_id"] = parent_id
            new["site_id"] = row["parent_site_id"]
            try:
                location_id = crud(conn, locations, new, locationmodel_id_choices=locationmodel_id_choices)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                if row["parent_site_id"] == 1:
                    conn.execute(locations.update().where(locations.c.id == location_id), {"site_id": location_id})
                return redirect(referrer)
    
    title = _("New Location")
    buttons={"submit": (_("Save"), url_for(".new_location", parent_id=parent_id, referrer=referrer)),
             "back": (_("Cancel"), url_for(".locations_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=title)



@app.route("/locations", defaults={"location_id": 1})
@app.route("/locations/<int:location_id>")
@login_required("Admin")
def locations_list(location_id):
    children = locations.alias("children")
    childmodels = locationmodels.alias("childmodels")
    grandchildren = locations.alias("grandchildren")
    grandchildmodels = locationmodels.alias("grandchildmodels")
    
    sql = select([children.c.id, children.c.name, children.c.deleted, childmodels.c.name.label("model"), grandchildmodels.c.name.label("childmodel"), locations.c.name.label("title"), locations.c.parent_id]). \
            select_from(join(locations, children, and_(children.c.parent_id == locations.c.id, children.c.id != 1), isouter=True). \
                        outerjoin(childmodels, children.c.locationmodel_id == childmodels.c.id). \
                        outerjoin(grandchildren, grandchildren.c.parent_id == children.c.id). \
                        outerjoin(grandchildmodels, grandchildren.c.locationmodel_id == grandchildmodels.c.id)). \
            where(locations.c.id == location_id). \
            order_by(childmodels.c.name, children.c.name)
    
    row = None
    body = []
    last_child_id = None
    with engine.connect() as conn:
        for row in conn.execute(sql):            
            if row["name"] is not None: 
                if row["id"] == last_child_id:
                    body[-1][0][2][row["childmodel"]] += 1
                else:
                    last_child_id = row["id"]
                    body.append(([row["name"],
                                row["model"],
                                Counter({row["childmodel"]: 1}) if row["childmodel"] else {}],
                                {"id": row["id"],
                                "deleted": row["deleted"]}))
        
        title = row["title"] or _("Sites")
        if location_id == 1:
            back_url = url_for(".editmenu")
        else:
            back_url = url_for(".locations_list", location_id=row["parent_id"])
    
    for row in body:
        items = []
        for k, v in sorted(row[0][2].items()):
            items.append(_("{} x {}").format(k, v))
        row[0][2] = ", ".join(items)
    
    head = (_("Name"), _("Type"), _("Contents"))
    actions = ({"name": _("View"), "href": url_for(".locations_list", location_id=0)},
               {"name": _("Edit"), "href": url_for(".edit_location", location_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_location", location_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_location", location_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".location_log", location_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_location", parent_id=location_id), "title": title},
                       buttons = {"back": (_("Back"), back_url)})
