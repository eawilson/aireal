import pdb

from psycopg2.errors import UniqueViolation

from flask import redirect, url_for, request
from werkzeug import exceptions

from ..utils import Cursor, login_required, abort, tablerow, render_page, unique_key
from ..forms import ActionForm
from .views import app
from ..logic import crud
from ..i18n import _
from ..models import locationmodels, locationtypes
from ..view_helpers import log_table
from .forms import LocationModelForm, NameForm, ActionForm




@app.route("/locationmodels/<int:locationmodel_id>/log")
@login_required("Admin")
def locationmodel_log(locationmodel_id):
    with Cursor as cur:
        table = log_table(cur, "locationmodels", locationmodel_id)
    
    table["title"] = _("Location Type Log")
    buttons={"back": (_("Back"), request.referrer)}
    return render_page("table.html", table=table, buttons=buttons)
        


@app.route("/locationmodels/new", methods=["GET", "POST"])
@login_required("Admin")
def new_locationmodel():
    sql = select([locationtypes.c.name, locationtypes.c.name]).where(locationtypes.c.deleted == False)
    with engine.begin() as conn:
        locationtype_choices = list(conn.execute(sql))
        
        form = LocationModelForm(request.form if request.method=="POST" else {})
        form.locationtype.choices = locationtype_choices
        if request.method == "POST" and form.validate():
            try:
                crud(conn, locationmodels, form.data, locationtype_choices=locationtype_choices)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                return redirect(url_for(".locationmodels_list"))
    
    buttons={"submit": (_("Save"), url_for(".new_locationmodel")),
             "back": (_("Cancel"), url_for(".locationmodels_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("New Location Type"))



@app.route("/locationmodels/<int:locationmodel_id>/edit", methods=["GET", "POST"])
@login_required("Admin")
def edit_locationmodel(locationmodel_id):
    sql = select([locationmodels.c.id, locationmodels.c.name, locationmodels.c.deleted]).where(locationmodels.c.id == locationmodel_id)
    with engine.begin() as conn:
        old = dict(conn.execute(sql).first() or abort(exceptions.BadRequest))
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                crud(conn, locationmodels, {"deleted": True}, old)
            elif action == _("Restore"):
                crud(conn, locationmodels, {"deleted": False}, old)
            return redirect(url_for(".locationmodels_list"))
        
        form = NameForm(request.form if request.method=="POST" else old)
        if request.method == "POST" and form.validate():
            new = form.data
            try:
                crud(conn, locationmodels, new, old)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                return redirect(url_for(".locationmodels_list"))
    
    buttons={"submit": (_("Save"), url_for(".edit_locationmodel", locationmodel_id=locationmodel_id)),
             "back": (_("Cancel"), url_for(".locationmodels_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("Edit Location Type"))



@app.route("/locationmodels")
@login_required("Admin")
def locationmodels_list():
    sql = select([locationmodels.c.id, locationmodels.c.name, locationmodels.c.locationtype, locationmodels.c.deleted, locationmodels.c.attr]). \
            order_by(locationmodels.c.locationtype, locationmodels.c.name)
    
    body = []
    with engine.connect() as conn:
        for row in conn.execute(sql):
            print(row)
            attr = row["attr"]
            
            specs = []
            if attr.get("shelves"):
                specs.append(_("Shelves {}".format(attr["shelves"])))
            
            if attr.get("trays"):
                specs.append(_("Trays {}".format(attr["trays"])))
            
            if attr.get("size"):
                specs.append(_("Size {} x {} cm".format(attr["size"]["width"], attr["size"]["length"])))
            
            if attr.get("capacity"):
                specs.append(_("Capacity {} x {} Samples").format(attr["capacity"]["rows"], attr["capacity"]["columns"]))
            
            if attr.get("temperature") is not None:
                specs.append(_("Temperature {}°C").format(attr["temperature"]))
            
            body.append(tablerow(row["name"],
                                 row["locationtype"],
                                 ", ".join(specs),
                                 id=row["id"],
                                 deleted=row["deleted"]))
        
    head = (_("Name"), _("Type"), _("Specifications"))
    actions = ({"name": _("Edit"), "href": url_for(".edit_locationmodel", locationmodel_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_locationmodel", locationmodel_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_locationmodel", locationmodel_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".locationmodel_log", locationmodel_id=0)})

    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_locationmodel"), "title": "Location Types"},
                       buttons={"back": (_("Back"), url_for(".editmenu"))})



