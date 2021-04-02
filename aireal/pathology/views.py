from datetime import datetime, timezone
from itertools import count
import re
import time
from urllib.parse import urlparse, urlunparse, urlencode
import pdb

from sqlalchemy import select, join, or_, outerjoin, and_
from sqlalchemy.exc import IntegrityError

from flask import session, redirect, url_for, request, current_app, Blueprint
from werkzeug import exceptions

from ..utils import engine, login_required, navbar, abort, tablerow, render_page, utcnow, render_template, unique_violation_or_reraise
from ..wrappers import Local
from ..logic import crud
from ..view_helpers import log_table
from ..i18n import _
from ..aws import list_objects, s3_sign_url, run_task, cloudfront_sign_cookies
from ..forms import ActionForm

from .models import slides, users, sites, users_projects, projects
from .forms import DirectoryUploadForm, AjaxForm, Form, CompletionForm, SlideForm


app = Blueprint("pathology", __name__, template_folder="templates")



@navbar("Pathology")
def pathology_navbar():
    return [{"text": _("Slides"),
             "href":  url_for("pathology.list_slides")}]



@app.route("/pathology")
def pathology():
    return render_template("viewer.html")



@app.route("/slides")
@login_required("Pathology")
def list_slides():
    sql = select([slides.c.id, slides.c.name.label("slide"), users.c.name.label("user"), sites.c.name.label("site"), slides.c.created_datetime, slides.c.status, slides.c.deleted]). \
            select_from(join(slides, users, users.c.id == slides.c.user_id). \
                        join(sites, sites.c.id == slides.c.site_id)). \
            where(slides.c.project_id == session.get("project_id", None)). \
            order_by(slides.c.name)

    buttons = {"new": ("", url_for(".new_slide"))}
    if "show" in request.args:
        buttons["info"] = (_("Hide Deleted"), url_for(".list_slides"))
    else:
        sql = sql.where(slides.c.deleted == False)
        buttons["info"] = (_("Show Deleted"), url_for(".list_slides", show="True"))
    
    head=(_("Slide"), _("Site"), _("Uploaded By"), _("Date Uploaded"), _("Status"))
    body = []
    with engine.connect() as conn:
        for row in list(conn.execute(sql)):
            body += [tablerow(row["slide"],
                              row["site"],
                              row["user"],
                              Local(row["created_datetime"]),
                              row["status"],
                              deleted=row["deleted"],
                              id=row["id"]
                              )]
    actions = ({"name": _("View"), "href": url_for(".view_slide", slide_id=0)},
               {"name": _("Edit"), "href": url_for(".edit_slide", slide_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_slide", slide_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_slide", slide_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".view_log", slide_id=0)})
    return render_page("table.html",
                       title=_("Slides"),
                       table={"head": head, "body": body, "actions": actions},
                       buttons=buttons)


 
@app.route("/slides/<int:slide_id>")
@login_required("Pathology")
def view_slide(slide_id):
    config = current_app.config
    tiles_cdn_base_url = config.get("TILES_CDN_BASE_URL") or abort(exceptions.NotImplemented)
    if not tiles_cdn_base_url.endswith("/"):
        tiles_cdn_base_url= f"{tiles_cdn_base_url}/"
    url_stem = f"{tiles_cdn_base_url}{slide_id}/"
    
    with engine.connect() as conn:
        sql = select([slides.c.name, slides.c.directory_name, slides.c.status]). \
                select_from(join(slides, users_projects, slides.c.project_id == users_projects.c.project_id)). \
                where(and_(slides.c.id == slide_id, slides.c.deleted == False, users_projects.c.user_id == session["id"]))
        row = dict(conn.execute(sql).first() or abort(exceptions.NotFound))
    print(row)
    if row["status"] != "Ready":
        return redirect(request.referrer)####################################################################
    
    if urlparse(request.referrer)[1] != urlparse(tiles_cdn_base_url)[1]:
        # Authentication cookies not yet set
        private_key = config.get("TILES_CDN_PRIVATE_KEY") or abort(exceptions.NotImplemented)
        cookies = cloudfront_sign_cookies(f"{url_stem}*", private_key)
        
        set_cookies_url = f"{tiles_cdn_base_url}set_cookies.html"
        url_parts = list(urlparse(set_cookies_url))
        url_parts[4] = {"cookies": json.dumps(cookies)}
        set_cookies_url = urlunparse(url_parts)
        
        set_cookies_url = cloudfront_sign_url(set_cookies_url, private_key)
        return redirect(set_cookies_url)
    
    dzi_url = f"{url_stem}{row['directory_name']}.dzi"
    return render_template("viewer.html", dzi_url=dzi_url, name=row["name"], url_back=url_for(".list_slides"))



@app.route("/slides/<int:slide_id>/edit", methods=["GET", "POST"])
@login_required("Pathology")
def edit_slide(slide_id):
    with engine.begin() as conn:
        sql = select([slides.c.id, slides.c.name, slides.c.site_id, slides.c.project_id, slides.c.deleted]). \
                select_from(join(slides, users_projects, slides.c.project_id == users_projects.c.project_id)). \
                where(and_(slides.c.id == slide_id, users_projects.c.user_id == session["id"]))
        old = dict(conn.execute(sql).first() or abort(exceptions.NotFound))
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                crud(conn, slides, {"deleted": True}, old)
            elif action == _("Restore"):
                crud(conn, slides, {"deleted": False}, old)
            return redirect(url_for(".list_slides"))

        sql = select([sites.c.id, sites.c.name]). \
                select_from(join(sites, slides, and_(slides.c.id == slide_id, slides.c.site_id == sites.c.id), isouter=True)). \
                where(or_(sites.c.deleted == False, slides.c.id == slide_id)). \
                order_by(sites.c.name)
        site_id_choices = [row.values() for row in conn.execute(sql)]
        
        sql = select([projects.c.id, projects.c.name]). \
                select_from(join(projects, slides, and_(slides.c.id == slide_id, slides.c.project_id == projects.c.id), isouter=True)). \
                where(or_(projects.c.deleted == False, slides.c.id == slide_id)). \
                order_by(projects.c.name)
        project_id_choices = [row.values() for row in conn.execute(sql)]
        
        form = SlideForm(request.form if request.method=="POST" else old)
        form.site_id.choices = site_id_choices
        form.project_id.choices = project_id_choices

        if request.method == "POST" and form.validate():
            try:
                crud(conn, slides, form.data, old, sites=site_id_choices, projects=project_id_choices)
            except IntegrityError as e:
                form[unique_violation_or_reraise(e)].errors = _("Must be unique.")
            else:
                return redirect(url_for(".list_slides"))
                
    buttons={"submit": (_("Save"), url_for(".edit_slide", slide_id=slide_id)),
             "back": (_("Cancel"), url_for(".list_slides"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("Edit Slide"))



@app.route("/slides/<int:slide_id>/log")
@login_required("Pathology")
def view_log(slide_id):
    with engine.begin() as conn:
        sql = select([slides.c.id]). \
                select_from(join(slides, users_projects, slides.c.project_id == users_projects.c.project_id)). \
                where(and_(slides.c.id == slide_id, users_projects.c.user_id == session["id"]))
        conn.execute(sql).first() or abort(exceptions.NotFound)
    return render_page("table.html",
                       table=log_table("slides", slide_id),
                       buttons={"back": (_("Back"), url_for(".list_slides"))},
                       title=_("Change Log"))



@app.route("/slides/new", methods=["GET", "POST"])
@login_required("Pathology")
def new_slide():
    if request.method == "POST":
        config = current_app.config

        slide_upload_base_url = config.get("SLIDE_UPLOAD_BASE_URL", "")
        if not slide_upload_base_url[:5].lower() == "s3://":
            abort(exceptions.NotImplemented)
        if not slide_upload_base_url.endswith("/"):
            slide_upload_base_url= f"{slide_upload_base_url}/"
        upload_bucket, prefix = slide_upload_base_url[5:].split("/", maxsplit=1)

        form = AjaxForm(request.form)
        if form.validate():            
            path = form.path.data
            if "/" not in path: # windows path, / illegal in windows path names
                path = path.replace("\\", "/")
            
            if not re.search(r"/r[0-9]+c[0-9]+\.jpg$", path):
                # file not needed therefore skip
                return {"outcome": "skip"}
            
            try:
                directory, filename = path.split("/", maxsplit=1)
            except ValueError:
                return ({}, exceptions.BadRequest.code)
            prefix = f"{prefix}{session['id']}/{directory}/"
            timestamp = form.timestamp.data
            
            if not timestamp.isnumeric():
                existing = []
                for key, val in list_objects(upload_bucket, prefix).items():
                    key = key[len(prefix):]
                    if "/" in key:
                        ts, fn = key.split("/", maxsplit=1)
                        if filename == fn and form.md5.data == val["ETag"].strip('"'):
                            try:
                                dt = datetime.fromtimestamp(float(ts)/1000, tz=timezone.utc)
                            except OverflowError:
                                return ({}, exceptions.BadRequest.code)
                            existing.append({"timeStamp": ts, "text": str(Local(dt))})
                if existing:
                    return {"outcome": "select", "options": existing}
        
                timestamp = str(int(time.time() * 1000)) # milliseconds since epoch
            
            upload_key = f"{prefix}{timestamp}/{filename}"
            existing = [val for key, val in list_objects(upload_bucket, upload_key).items() if key == upload_key]
            if existing:
                if form.md5.data == existing[0]["ETag"].strip('"'):
                    # file exists and matches therefore skip
                    return {"outcome": "skip"}
                
                else:
                    return {"outcome": "mismatch", "path": path}
            
            signed_url = s3_sign_url(upload_bucket, upload_key, hours=1)
            return {"outcome": "required", "signedUrl": signed_url, "timeStamp": timestamp}

        form = CompletionForm(request.form)
        if form.validate():
            tiles_base_url = config.get("TILES_BASE_URL", "")
            if not tiles_base_url[:5].lower() == "s3://":
                abort(exceptions.NotImplemented)
            if not tiles_base_url.endswith("/"):
                tiles_base_url= f"{tiles_base_url}/"
            
            directory = form.directory.data
            timestamp = form.timestamp.data
            with engine.connect() as conn:
                for suffix in count():
                    new = {"name": directory if not suffix else f"{directory} ({suffix})",
                           "project_id": session["project_id"],
                           "directory_name": directory,
                           "user_directory_timestamp": f"{session['id']}/{directory}/{timestamp}",
                           "created_datetime": utcnow(),
                           "site_id": session["site_id"],
                           "user_id": session["id"],
                           "status": "Uploaded"}
                    try:
                        with conn.begin() as trans:
                            slide_id = crud(conn, slides, new, {},
                                        project_id=((session["project_id"], session["project"]),),
                                        site_id=((session["site_id"], session["site"]),))
                    except IntegrityError: # 
                        continue
                    break
                
            upload_url = f"s{slide_upload_base_url}{session['id']}/{directory}/{timestamp}"
            deepzoom_url = f"{tiles_base_url}{slide_id}"
            run_task("deepzoom", ["--input", upload_url,
                                  "--output", deepzoom_url,
                                  "--name", directory])
            return {}

    form = DirectoryUploadForm()
    buttons={"submit": (_("Upload"), url_for(".new_slide")),
             "back": (_("Cancel"), url_for(".list_slides"))}
    return render_page("uploadform.html", form=form, buttons=buttons, title="Slides")


