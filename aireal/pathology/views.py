from datetime import datetime, timezone
from itertools import count
import re
import time
import json
from urllib.parse import urlparse, urlunparse, urlencode
import pdb

from psycopg2.errors import UniqueViolation

from flask import session, redirect, url_for, request, current_app, Blueprint
from werkzeug import exceptions

from ..utils import Cursor, Transaction, login_required, navbar, abort, tablerow, render_page, utcnow, render_template, unique_key, dict_from_select
from ..wrappers import Local
from ..logic import crud
from ..view_helpers import log_table
from ..i18n import _
from ..aws import list_objects, s3_sign_url, run_task, cloudfront_sign_cookies, cloudfront_sign_url
from ..forms import ActionForm

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
    sql = """SELECT slides.id, slides.name, users.name, pathology_sites.name, slides.created_datetime, slides.status, slides.deleted
             FROM slides
             INNER JOIN users ON users.id = slides.user_id
             LEFT OUTER JOIN pathology_sites ON pathology_sites.id = slides.pathology_site_id
             ORDER BY slides.name;"""

    head=(_("Slide"), _("Site"), _("Uploaded By"), _("Date Uploaded"), _("Status"))
    body = []
    with Cursor() as cur:
        cur.execute(sql, {"project_id": session.get("project_id")})
        for slide_id, slide, user, pathology_site, created_datetime, status, deleted in cur:
            body.append(tablerow(slide,
                                 pathology_site,
                                 user,
                                 Local(created_datetime),
                                 status,
                                 deleted=deleted,
                                 id=slide_id))
    
    actions = ({"name": _("View"), "href": url_for(".view_slide", slide_id=0)},
               {"name": _("Edit"), "href": url_for(".edit_slide", slide_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_slide", slide_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_slide", slide_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".view_log", slide_id=0)})
    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_slide"), "title": _("Slides")},
                       buttons=())


 
@app.route("/slides/<int:slide_id>")
@login_required("Pathology")
def view_slide(slide_id):
    config = current_app.config
    tiles_cdn_base_url = config.get("TILES_CDN_BASE_URL") or abort(exceptions.NotImplemented)
    if not tiles_cdn_base_url.endswith("/"):
        tiles_cdn_base_url= f"{tiles_cdn_base_url}/"
    url_stem = f"{tiles_cdn_base_url}{slide_id}/"
    
    sql = """SELECT slides.name, slides.directory_name, slides.status
             FROM slides
             INNER JOIN users_projects ON slides.project_id = users_projects.project_id
             WHERE slides.id = %(slide_id)s AND slides.deleted = FALSE AND users_projects.user_id = %(user_id)s;"""
    with Cursor() as cur:
        cur.execute(sql, {"user_id": session["id"], "slide_id": slide_id})
        name, directory_name, status = cur.fetchone() or abort(exceptions.NotFound)
    
    if False:#status != "Ready":
        return redirect(request.referrer)####################################################################
    url_stem = f"{tiles_cdn_base_url}KCMC010/"
    directory_name = "KCMC010"
    
    if not request.args.get("authorised"):
        # Authentication cookies not yet set
        private_key = config.get("TILES_CDN_PRIVATE_KEY") or abort(exceptions.NotImplemented)
        cookies = cloudfront_sign_cookies(f"{url_stem}*", private_key)
        
        set_cookies_url = f"{tiles_cdn_base_url}set_cookie1.html"
        url_parts = list(urlparse(set_cookies_url))
        url_parts[4] = urlencode({"cookies": json.dumps(cookies), "referrer": request.url+"?authorised=y"})
        set_cookies_url = urlunparse(url_parts)
        
        set_cookies_url = cloudfront_sign_url(set_cookies_url, private_key)
        return redirect(set_cookies_url)
    
    dzi_url = f"{url_stem}{directory_name}.dzi"
    return render_template("viewer.html", dzi_url=dzi_url, name=name, url_back=url_for(".list_slides"))



@app.route("/slides/<int:slide_id>/edit", methods=["GET", "POST"])
@login_required("Pathology")
def edit_slide(slide_id):
    with Cursor() as cur:
        sql = """SELECT slides.id, slides.name, slides.pathology_site_id, slides.project_id, slides.deleted
                 FROM slides
                 INNER JOIN users_projects ON slides.project_id = users_projects.project_id
                 WHERE slides.id = %(slide_id)s AND users_projects.user_id = %(user_id)s;"""
        old = dict_from_select(cur, sql, {"user_id": session["id"], "slide_id": slide_id}) or abort(exceptions.NotFound)
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                crud(cur, "slides", {"deleted": True}, old)
            elif action == _("Restore"):
                crud(cur, "slides", {"deleted": False}, old)
            return redirect(url_for(".list_slides"))

        sql = """SELECT pathology_sites.id, pathology_sites.name
                 FROM pathology_sites
                 WHERE pathology_sites.deleted = FALSE OR id = %(pathology_site_id)s
                 ORDER BY pathology_sites.name;"""
        cur.execute(sql, {"pathology_site_id": old["pathology_site_id"]})
        pathology_site_id_choices = list(cur)
        
        sql = """SELECT projects.id, projects.name
                 FROM projects
                 INNER JOIN users_projects ON users_projects.project_id = projects.id AND users_projects.user_id = %(user_id)s
                 WHERE projects.deleted = FALSE OR projects.id = %(project_id)s
                 ORDER BY projects.name;"""
        cur.execute(sql, {"project_id": old["project_id"], "user_id": session["id"]})
        project_id_choices = list(cur)
        
        form = SlideForm(request.form if request.method=="POST" else old)
        form.pathology_site_id.choices = pathology_site_id_choices
        form.project_id.choices = project_id_choices

        if request.method == "POST" and form.validate():
            try:
                crud(cur, "slides", form.data, old, pathology_site_id=pathology_site_id_choices, project_id=project_id_choices)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                return redirect(url_for(".list_slides"))
                
    buttons={"submit": (_("Save"), url_for(".edit_slide", slide_id=slide_id)),
             "back": (_("Cancel"), url_for(".list_slides"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("Edit Slide"))



@app.route("/slides/<int:slide_id>/log")
@login_required("Pathology")
def view_log(slide_id):
    with Cursor() as cur:
        sql = """SELECT id
                 FROM slides
                 INNER JOIN users_projects ON slides.project_id = users_projects.project_id
                 WHERE slides.id = %(slide_id)s AND users_projects.user_id = %(user_id)s;"""
        cur.execute(sql, {"user_id": session["id"], "slide_id": slide_id})
        cur.fetchone() or abort(exceptions.NotFound)
        
        table = log_table(cur, "slides", slide_id)
        table["title"] = _("Change Log")
    return render_page("table.html", table=table, buttons={"back": (_("Back"), url_for(".list_slides"))})



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

    
    #with Transaction() as trans:
        #with trans.cursor() as cur:
            #sql = """SELECT pathology_sites.id, pathology_sites.name
                        #FROM pathology_sites
                        #WHERE pathology_sites.deleted = FALSE
                        #ORDER BY pathology_sites.name;"""
            #cur.execute(sql)
            #pathology_site_id_choices = list(cur)
            
            #sql = """SELECT projects.id, projects.name
                        #FROM projects
                        #INNER JOIN users_projects ON users_projects.project_id = projects.id AND users_projects.user_id = %(user_id)s
                        #WHERE projects.deleted = FALSE
                        #ORDER BY projects.name;"""
            #cur.execute(sql, {"user_id": session["id"]})
            #project_id_choices = list(cur)
            
            #form = CompletionForm(request.form) if request.method == "POST" else DirectoryUploadForm(id="directory-upload-form")
            #form.project_id.choices = project_id_choices
            #form.pathology_site_id.choices = pathology_site_id_choices
            
        form = CompletionForm(request.form)
        if form.validate():
            tiles_base_url = config.get("TILES_BASE_URL", "")
            if not tiles_base_url[:5].lower() == "s3://":
                abort(exceptions.NotImplemented)
            if not tiles_base_url.endswith("/"):
                tiles_base_url= f"{tiles_base_url}/"
            
            directory = form.directory.data
            timestamp = form.timestamp.data
            
            pdb.set_trace()
            new = {"name": directory,
                #"project_id": form.project_id.data,
                "directory_name": directory,
                "user_directory_timestamp": f"{session['id']}/{directory}/{timestamp}",
                "created_datetime": utcnow(),
                #"pathology_site_id": form.pathology_site_id.data,
                "user_id": session["id"],
                "status": "Uploaded"}
            #project_id_choices = ((form.project_id.data, form.project_id.data),)
            #pathology_site_id_choices = ((form.pathology_site_id.data, form.pathology_site_id.data),)
            with Transaction() as trans:
                with trans.cursor() as cur:
                    for suffix in count():
                        new["name"] = f"{directory} ({suffix})" if count else directory
                        try:
                            slide_id = crud(cur, "slides", new, {})
                                            #project_id=project_id_choices,
                                            #pathology_site_id=pathology_site_id_choices)
                        except UniqueViolation: #
                            trans.rollback()
                            continue
                        trans.commit()
                        break
                
            upload_url = f"s{slide_upload_base_url}{session['id']}/{directory}/{timestamp}"
            deepzoom_url = f"{tiles_base_url}{slide_id}"
            run_task("deepzoom", ["--input", upload_url,
                                "--output", deepzoom_url,
                                "--name", directory])
            return {}
    
    form = DirectoryUploadForm(id="directory-upload-form")
    buttons={"submit": (_("Upload"), url_for(".new_slide")),
             "back": (_("Cancel"), url_for(".list_slides"))}
    return render_page("uploadform.html", form=form, buttons=buttons, title="Slides")


