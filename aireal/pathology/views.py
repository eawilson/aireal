from datetime import datetime, timezone
from itertools import count
import re
import time
import json
import pdb

from psycopg2.errors import UniqueViolation

from flask import session, redirect, url_for, request, current_app
from werkzeug import exceptions

from urllib.parse import quote

from ..utils import Cursor, Transaction, navbar, abort, tablerow, render_page, render_template, unique_key, dict_from_select, Blueprint, sign_token, absolute_url_for, build_url
from ..wrappers import Local
from ..logic import perform_edit, perform_delete, perform_restore
from ..view_helpers import log_table
from ..i18n import _
from ..aws import list_objects, s3_sign_url, run_task, cloudfront_sign_cookies, cloudfront_sign_url
from ..forms import ActionForm

from .forms import DirectoryUploadForm, AjaxForm, Form, CompletionForm, SlideForm


app = Blueprint("pathology", __name__, "Pathology", template_folder="templates")



@navbar("Pathology")
def pathology_navbar():
    return [{"text": _("Slides"),
             "href":  url_for("pathology.slide_list")}]
    


@app.route("/slides")
def slide_list():
    sql = """SELECT slide.id, slide.name, users.fullname, pathologysite.name, slide.created_datetime, slide.status, slide.deleted, slide.clinical_details
             FROM slide
             INNER JOIN users ON users.id = slide.users_id
             LEFT OUTER JOIN pathologysite ON pathologysite.id = slide.pathologysite_id
             ORDER BY slide.name;"""

    head=(_("Slide"), _("Site"), _("Uploaded By"), _("Date Uploaded"), _("Clinical Details"), _("Status"))
    body = []
    with Cursor() as cur:
        cur.execute(sql, {"project_id": session.get("project_id")})
        for slide_id, slide, user, pathologysite, created_datetime, status, deleted, clinical_details in cur:
            body.append(tablerow(slide,
                                 pathologysite,
                                 user,
                                 Local(created_datetime),
                                 clinical_details,
                                 status,
                                 deleted=deleted,
                                 id=slide_id))
    
    actions = ({"name": _("View"), "href": url_for(".auth_slide", slide_id=0)},
               {"name": _("Edit"), "href": url_for(".edit_slide", slide_id=0)},
               {"name": _("Delete"), "href": url_for(".edit_slide", slide_id=0), "class": "!deleted", "method": "POST"},
               {"name": _("Restore"), "href": url_for(".edit_slide", slide_id=0), "class": "deleted", "method": "POST"},
               {"name": _("Log"), "href": url_for(".view_log", slide_id=0)})
    return render_page("table.html",
                       table={"head": head, "body": body, "actions": actions, "new": url_for(".new_slide"), "title": _("Slides")},
                       buttons=())


 
@app.route("/slides/<int:slide_id>/auth")
def auth_slide(slide_id):
    sql = """SELECT slide.name, slide.directory_name, slide.status
             FROM slide
             WHERE slide.id = %(slide_id)s AND slide.deleted = FALSE AND slide.status = 'Ready';"""
    with Cursor() as cur:
        cur.execute(sql, {"users_id": session["id"], "slide_id": slide_id})
        row = cur.fetchone()
        if not row:
            return redirect(url_for(".slide_list"))
        name, directory_name, status = row
    
        sql = """INSERT INTO editrecord (tablename, row_id, action, users_id, ip_address)
                 VALUES ('slide', %(row_id)s, 'Viewed', %(users_id)s, %(ip_address)s);"""
        cur.execute(sql, {"row_id": slide_id, "users_id": session["id"], "ip_address": request.remote_addr})
    
    config = current_app.config
    private_key = config.get("TILES_CDN_PRIVATE_KEY") or abort(exceptions.NotImplemented)
    tiles_cdn_base_url = config.get("TILES_CDN_BASE_URL") or abort(exceptions.NotImplemented)
    if tiles_cdn_base_url.endswith("/"):
        tiles_cdn_base_url = tiles_cdn_base_url[:-1]
    
    wildcard_url = build_url(tiles_cdn_base_url, "*")
    cookies = cloudfront_sign_cookies(wildcard_url, private_key)
    destination = absolute_url_for(".view_slide", slide_id=slide_id)
    
    set_cookies_url = build_url(tiles_cdn_base_url, "set_cookies.html", cookies=cookies, destination=destination)
    return redirect(cloudfront_sign_url(set_cookies_url, private_key))


    
@app.route("/slides/<int:slide_id>")
def view_slide(slide_id):
    sql = """SELECT slide.name, slide.directory_name, slide.status
             FROM slide
             WHERE slide.id = %(slide_id)s AND slide.deleted = FALSE;"""#AND slide.status = 'Ready'
    with Cursor() as cur:
        cur.execute(sql, {"users_id": session["id"], "slide_id": slide_id})
        name, directory_name, status = cur.fetchone() or abort(exceptions.NotFound)
    
    config = current_app.config
    private_key = config.get("TILES_CDN_PRIVATE_KEY") or abort(exceptions.NotImplemented)
    tiles_cdn_base_url = config.get("TILES_CDN_BASE_URL") or abort(exceptions.NotImplemented)
    if tiles_cdn_base_url.endswith("/"):
        tiles_cdn_base_url= tiles_cdn_base_url[:-1]
    
    dzi_url = build_url(tiles_cdn_base_url, str(slide_id), quote(f"{directory_name}.dzi"))
    viewer_url = build_url(tiles_cdn_base_url, "staticviewer.html", dzi_url=dzi_url, back_url=absolute_url_for(".slide_list"))
    print(viewer_url)
    return redirect(viewer_url)#cloudfront_sign_url(viewer_url, private_key))
    return render_template("viewer.html", dzi_url=dzi_url, name=name)



@app.route("/slides/<int:slide_id>/edit", methods=["GET", "POST"])
def edit_slide(slide_id):
    with Cursor() as cur:
        sql = """SELECT slide.id, slide.name, slide.clinical_details, slide.pathologysite_id, slide.deleted
                 FROM slide
                 WHERE slide.id = %(slide_id)s;"""
        old = dict_from_select(cur, sql, {"users_id": session["id"], "slide_id": slide_id}) or abort(exceptions.NotFound)
        
        form = ActionForm(request.form)
        if request.method == "POST" and form.validate():
            action = form.action.data
            if action == _("Delete"):
                perform_delete(cur, "slide", slide_id)
            elif action == _("Restore"):
                perform_restore(cur, "slide", slide_id)
            return redirect(url_for(".slide_list"))

        sql = """SELECT pathologysite.id, pathologysite.name
                 FROM pathologysite
                 WHERE pathologysite.deleted = FALSE OR id = %(pathologysite_id)s
                 ORDER BY pathologysite.name;"""
        cur.execute(sql, {"pathologysite_id": old["pathologysite_id"]})
        pathologysite_id_choices = list(cur)
        
        form = SlideForm(request.form if request.method=="POST" else old)
        form.pathologysite_id.choices = pathologysite_id_choices

        if request.method == "POST" and form.validate():
            try:
                perform_edit(cur, "slide", form.data, old, form)
            except UniqueViolation as e:
                form[unique_key(e)].errors = _("Must be unique.")
            else:
                return redirect(url_for(".slide_list"))
                
    buttons={"submit": (_("Save"), url_for(".edit_slide", slide_id=slide_id)),
             "back": (_("Cancel"), url_for(".slide_list"))}
    return render_page("form.html", form=form, buttons=buttons, title=_("Edit Slide"))



@app.route("/slides/<int:slide_id>/log")
def view_log(slide_id):
    with Cursor() as cur:
        sql = """SELECT id
                 FROM slide
                 WHERE slide.id = %(slide_id)s;"""
        cur.execute(sql, {"users_id": session["id"], "slide_id": slide_id})
        cur.fetchone() or abort(exceptions.NotFound)
        
        table = log_table(cur, "slide", slide_id)
        table["title"] = _("Change Log")
    return render_page("table.html", table=table, buttons={"back": (_("Back"), url_for(".slide_list"))})



@app.route("/slides/new", methods=["GET", "POST"])
def new_slide():
    if request.method == "POST":
        config = current_app.config

        slide_upload_base_url = config.get("SLIDE_UPLOAD_BASE_URL", "")
        if not slide_upload_base_url[:5].lower() == "s3://":
            abort(exceptions.NotImplemented)
        if slide_upload_base_url.endswith("/"):
            slide_upload_base_url= slide_upload_base_url[:-1]
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
            prefix = f"{prefix}/{session['id']}/{directory}/"
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
            if tiles_base_url.endswith("/"):
                tiles_base_url= tiles_base_url[:-1]
            
            directory = form.directory.data
            timestamp = form.timestamp.data
            sql = """INSERT INTO slide (name, directory_name, user_directory_timestamp, users_id, status)
                      VALUES (%(name)s, %(directory_name)s, %(user_directory_timestamp)s, %(users_id)s, 'Uploaded')
                      RETURNING id;"""
            
            new = {"name": directory,
                   "directory_name": directory,
                   "user_directory_timestamp": f"{session['id']}/{directory}/{timestamp}",
                   "users_id": session["id"]}
            
            slide_id = None
            with Transaction() as trans:
                with trans.cursor() as cur:
                    for suffix in count():
                        new["name"] = f"{directory} ({suffix})" if suffix else directory
                        try:
                            cur.execute(sql, new)
                            slide_id = cur.fetchone()[0]
                            
                            sql = """INSERT INTO editrecord (tablename, row_id, action, details, users_id, ip_address)
                                     VALUES ('slide', %(row_id)s, 'Uploaded', %(details)s, %(users_id)s, %(ip_address)s);"""
                            cur.execute(sql, {"row_id": slide_id, "details": {"Name": directory},"users_id": session["id"], "ip_address": request.remote_addr})

                        except UniqueViolation as e: #
                            trans.rollback()
                            if "user_directory_timestamp" in str(e):
                                break
                            continue
                        trans.commit()
                        break

                    if slide_id is None:
                        sql = "SELECT id FROM slide WHERE user_directory_timestamp = %(user_directory_timestamp)s;"
                        cur.execute(sql, {"user_directory_timestamp": new["user_directory_timestamp"]})
                        slide_id = cur.fetchone()[0]
                
            upload_url = build_url(slide_upload_base_url, str(session['id']), directory, timestamp)
            deepzoom_url = build_url(tiles_base_url, str(slide_id))
            
            token = sign_token({"slide_id": slide_id, "old_status": "Uploaded", "new_status": "Ready"}, salt="deepzoom_callback")
            callback_url = absolute_url_for(".deepzoom_callback", token=token)
            run_task("deepzoom", ["--input", upload_url,
                                  "--output", deepzoom_url,
                                  "--name", directory,
                                  "--callback", callback_url])
            return {}
    
    form = DirectoryUploadForm(id="directory-upload-form")
    buttons={"submit": (_("Upload"), url_for(".new_slide")),
             "back": (_("Cancel"), url_for(".slide_list"))}
    return render_page("uploadform.html", form=form, buttons=buttons, title="Slides")
    _("Uploaded")
    _("Ready")



@app.signed_route("/slides/callback", max_age=60*60)
def deepzoom_callback(data):
    with Cursor() as cur:
        quality = data.pop("quality", "Default")
        sql = """UPDATE slide SET status = %(new_status)s
                 WHERE id = %(slide_id)s AND status = %(old_status)s;"""
        cur.execute(sql, data)
        
        sql = """INSERT INTO editrecord (tablename, row_id, action, details)
                 VALUES ('slide', %(row_id)s, 'Processed', %(details)s);"""
        cur.execute(sql, {"row_id": data["slide_id"], "details": {"Quality": quality}})
    
    return {}


