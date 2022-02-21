import os
import uuid
import shlex
import subprocess
import time
import requests
import re
from html import escape, unescape

import pdb

from flask import session, redirect, url_for, request, current_app
from werkzeug.exceptions import Conflict, Forbidden, BadRequest, NotFound, InternalServerError
from jinja2 import Markup

from psycopg2.extras import execute_batch

from ...flask import abort, render_page, render_template, Blueprint, sign_token, absolute_url_for, query_parameter
from ...utils import Cursor, Transaction, tablerow, iso8601_to_utc, demonise
from ...i18n import _
from ...wrappers import Local
from ...aws import run_task
from .forms import ServerForm


trim_lane_regex = re.compile("_L[0-9]{3}$")


app = Blueprint("Basespace", __name__, role="Bioinformatics", template_folder="templates")



def credentials(account_id):
    with Cursor() as cur:
        sql = """SELECT bsaccount.name, bsserver.url, bsaccount.token
                 FROM bsaccount
                 JOIN bsaccount_users ON bsaccount_users.bsaccount_id = bsaccount.id
                 JOIN bsserver ON bsserver.id = bsaccount.bsserver_id
                 WHERE bsaccount.id = %(account_id)s AND bsaccount_users.users_id = %(users_id)s;"""
        cur.execute(sql, {"account_id": account_id, "users_id": session["id"]})
        return cur.fetchone()



def bs_get(url, token, params={}):
    try:
        response = requests.get(url,
                                params=params, 
                                headers={"x-access-token": token},
                                stream=True)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        pass # need to add proper handling
    except requests.exceptions.JSONDecodeError:
        pass



@app.route("/accounts")
def accounts():
    with Cursor() as cur:
        sql = """SELECT bsaccount.id, bsaccount.name, bsserver.region, bsserver.country
                 FROM bsaccount
                 JOIN bsaccount_users ON bsaccount.id = bsaccount_users.bsaccount_id
                 JOIN bsserver ON bsserver.id = bsaccount.bsserver_id
                 WHERE bsaccount_users.users_id = %(users_id)s
                 ORDER BY bsaccount.name;"""
        body = []
        cur.execute(sql, {"users_id": session["id"]})
        for bsaccount_id, bsaccount_name, region, country in cur:
            body.append(((bsaccount_name,
                          "{} ({})".format(region, _(country))),
                          {"id": bsaccount_id}))
    
    actions = ({"name": _("Select"), "href": url_for(".bsruns", account_id=0)},)
    table = {"head": (_("Account"), _("Region")),
             "body": body,
             "showhide": False,
             "actions": actions,
             "new": url_for(".new_account")}
    return render_page("table.html", table=table, title=_("BaseSpace"), buttons=())
    _("USA")
    _("Canada")
    _("Europe")
    _("UK")
    _("China")
    _("Australia")



@app.route("/accounts/new", methods=["GET", "POST"])
def new_account():
    with Cursor() as cur:
        sql = """SELECT bsserver.id, bsserver.url, bsserver.region, bsserver.country
                 FROM bsserver
                 ORDER BY bsserver.region;"""
        cur.execute(sql)
        id_choices = []
        urls = {}
        for bsserver_id, bsserver_url, region, country in cur:
            id_choices.append((bsserver_id, "{} ({})".format(region, _(country))))
            urls[bsserver_id] = bsserver_url
    
    form = ServerForm(request.form if request.method == "POST" else {})
    form.bsserver_id.choices = id_choices
    
    buttons = {"back": (_("Back"), url_for(".accounts"))}

    if request.method == "POST" and form.validate():
        auth_file = os.path.join(current_app.instance_path, "bsauth-{}".format(uuid.uuid4()))
        token = sign_token({"users_id": session["id"], "bsserver_id": form.bsserver_id.data}, salt="authorisation_callback")
        callback = absolute_url_for(".authorisation_callback", token=token)
        
        cmd = ["bsauth", "--auth-file", auth_file,
                         "--callback", callback,
                         "--api-server", urls[form.bsserver_id.data],
                         "--scopes", "Read Global, Browse Global"]
        demonise(cmd)
        
        for i in range(50):
            try:
                with open(auth_file) as f_in:
                    auth_url = f_in.read()
                if auth_url.endswith("\n"):
                    if auth_url.startswith("Please go to this URL to authenticate:"):
                        auth_url = auth_url[38:].strip()
                        link = render_template("link.html", text=auth_url, url=auth_url, external=True)
                        text = [Markup("{} {}".format(_("Please go to this URL to authenticate:"), link)),
                                _("For BaseSpace Enterprise please ensure you are logged into the the correct workgroup before following link.")]
                    else:
                        text = ["{} {}".format(_("ERROR:"), auth_url.strip())]
                    break
            except FileNotFoundError:
                time.sleep(0.1)
        else:
            text = [_("ERROR: Unable to communicate with BaseSpace authentication process.")]
        
        return render_page("basespace_auth.html", text=text, buttons=buttons)
    
    else:
        title = _("Please select the region that the account is hosted in")
        buttons["submit"] = (_("Next"), url_for(".new_account"))
        return render_page("form.html", title=title, form=form, buttons=buttons)
    


@app.route("/callback/authorisation/<string:token>", signature="authorisation_callback", max_age=60*60, methods=["POST"])
def authorisation_callback(token):
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """INSERT INTO bsaccount (bsid, name, token, bsserver_id)
                     VALUES (%(bsid)s, %(name)s, %(token)s, %(bsserver_id)s)
                     ON CONFLICT ON CONSTRAINT uq_bsaccount_bsid_bsserver_id
                     DO UPDATE SET name = %(name)s, token = %(token)s
                     RETURNING id;"""
            cur.execute(sql, {"bsserver_id": token["bsserver_id"], **request.form})
            bsaccount_id = cur.fetchone()[0]
            
            sql = """INSERT INTO bsaccount_users (users_id, bsaccount_id)
                     VALUES (%(users_id)s, %(bsaccount_id)s)
                     ON CONFLICT DO NOTHING;"""
            cur.execute(sql, {"users_id": token["users_id"], "bsaccount_id": bsaccount_id})
    return {}



@app.route("/accounts/<int:account_id>/runs")
def bsruns(account_id):
    account, server, token = credentials(account_id) or abort(BadRequest)
    run_offset = query_parameter("run_offset", numeric=True)
    query = bs_get(f"{server}/v2/search", token, params={"scope": "runs",
                                                           "query": "(experimentname:*)",
                                                           "offset": run_offset,
                                                           "limit": 10,
                                                           "SortBy": "DateCreated",
                                                           "SortDir": "Desc"})
    
    body = []
    for item in query["Items"]:
        item = item["Run"]
        status = item["Status"]
        seqstats = item.get("SequencingStats", {}) # Not present if uploading
        experimentname = item["ExperimentName"]
        bsid = item["Id"]
        body.append(((experimentname,
                      item["InstrumentType"],
                      item["InstrumentName"],
                      "{:.2f}%".format(seqstats["PercentGtQ30"]) if seqstats else "",
                      "{:.2f}%".format(seqstats["PercentPf"] * 100) if seqstats else "",
                      (int(seqstats["ClusterDensity"] / 1000) or "") if seqstats else "",
                      status,
                      Local(iso8601_to_utc(item["DateCreated"]))),
                      {"id": f"{bsid}%2C{experimentname}"} if status == "Complete" else {}))
    
    actions = ({"name": _("Select"), "href": url_for(".bsappsessions", account_id=account_id, run=0, run_offset=run_offset)},)
    table = {"head": (_("Name"), _("Platform"), _("Machine"), _("Avg %Q30"), _("%PF"), _("Cluster Density"), _("Status"), _("Created")),
             "body": body,
             "showhide": False,
             "actions": actions,
             "breadcrumbs": ((_("Accounts"), url_for(".accounts"), False), (account, url_for(".bsruns", account_id=account_id, run_offset=run_offset), True))}
    
    paging = query["Paging"]
    total_count = paging["TotalCount"]
    if paging["DisplayedCount"] < total_count:
        pagination = []
        offset = paging["Offset"]
        for i in range(0, total_count, 10):
            pagination.append({"text": str((i // 10) + 1),
                               "href": url_for(".bsruns", account_id=account_id, run_offset=i),
                               "current": i <= offset < i + 10})
        table["pagination"] = pagination
    
    return render_page("table.html", table=table, buttons=())



@app.route("/accounts/<int:account_id>/runs/<csv:run>", methods=["GET", "POST"])
def bsappsessions(account_id, run):
    run_bsid, experimentname = run.split(",", maxsplit=1)
    account, server, token = credentials(account_id) or abort(BadRequest)
    run_offset = query_parameter("run_offset", numeric=True)
    query = bs_get(f"{server}/v2/appsessions", token, params={"input.runs": run_bsid,
                                                              "offset": 0,
                                                              "limit": 10,
                                                              "SortBy": "DateCreated",
                                                              "SortDir": "Desc"})
    paging = query["Paging"]
    displayed_count = paging["DisplayedCount"]
    total_count = paging["TotalCount"]
    offset = paging["Offset"]

    body = []
    for item in query["Items"]:
        bsid = item["Id"]
        status = item["ExecutionStatus"]
        body.append(((item["Application"]["Name"],
                      status,
                      "{:.2f}GB".format(item.get("TotalSize", 0) / 1000000000),
                      Local(iso8601_to_utc(item["DateCreated"]))),
                      {"id": item["Id"]} if status == "Complete" else {}))
    
    actions = ({"name": _("Select"), "href": url_for(".bsdatasets", account_id=account_id, run=run, appsession_bsid=0, run_offset=run_offset)},)
    table = {"head": (_("Application"), _("Status"), _("Size"), _("Created")),
             "body": body,
             "showhide": False,
             "actions": actions,
             "breadcrumbs": ((_("Accounts"), url_for(".accounts"), False), 
                             (account, url_for(".bsruns", account_id=account_id, run_offset=run_offset), False),
                             (experimentname, url_for(".bsappsessions", account_id=account_id, run=run, run_offset=run_offset), True))}
    return render_page("table.html", table=table, buttons=())



@app.route("/accounts/<int:account_id>/runs/<csv:run>/appsessions/<string:appsession_bsid>")
def bsdatasets(account_id, run, appsession_bsid):
    run_bsid, experimentname = run.split(",", maxsplit=1)
    account, server, token = credentials(account_id) or abort(BadRequest)
    run_offset = query_parameter("run_offset", numeric=True)
    
    statuses = bsdatasets_status(appsession_bsid)
    
    datasets = []
    query = bs_get(f"{server}/v2/appsessions/{appsession_bsid}", token)
    for prop in query["Properties"]["Items"]:
        if prop["Name"] == "Output.Datasets":
            if prop["ItemsDisplayedCount"] == prop["ItemsTotalCount"]:
                datasets = prop["DatasetItems"]
            else:
                # Does not specify sort direction in Output.Datasets therefore search from beginning again to be safe.
                total = prop["ItemsTotalCount"]
                url = f"{server}/v2/appsessions/{appsession_bsid}/properties/Output.Datasets/items"
                while len(datasets) < total:
                    response = bs_get(url, token, params={"offset": len(datasets), "SortBy": "DateCreated", "SortDir": "Desc"})
                    for item in response["Items"]:
                        datasets.append(item["Dataset"])
    
    body = []
    values = []
    datasets.sort(key=lambda p:p["Name"])
    for item in datasets:
        name = item["Name"]
        if not trim_lane_regex.search(name):
            # If name doe not have a lane suffix then assume it is a composite dataset containing the combined datasets
            # for each of the individual dataset from each lane. WARNING - This assumption may not be future proof but
            # I can see no other way of doing it other than for checking for unique names or etags within the files
            # and this would significantly increase the number of api calls and reduce responsivness.
            continue
        
        lane = int(name[-3:])
        name = name[:-5]
        
        if body and body[-1][0][1] == name:
            prev_row = body[-1][0]
            prev_row[2] = "{},{}".format(prev_row[2], lane)
            prev_row[3] += item["Attributes"].get("common_fastq", {}).get("TotalReadsPF", 0)
            prev_row[4] += item.get("TotalSize", 0)
        else:
            body.append(([Markup(render_template("checkbox.html", form="table-form", name=escape(name))),
                         name,
                         lane,
                         item["Attributes"].get("common_fastq", {}).get("TotalReadsPF", 0),
                         item.get("TotalSize", 0),
                         Local(iso8601_to_utc(item["DateCreated"])),
                         statuses.get(name, "")],{}))
    
    for row in body:
        row[0][4] = "{:.2f}GB".format(row[0][4] / 1000000000)
    
    here = url_for(".bsdatasets", account_id=account_id, run=run, appsession_bsid=appsession_bsid, run_offset=run_offset)
    back = url_for(".bsappsessions", account_id=account_id, run=run, run_offset=run_offset)
    buttons = {"submit": (_("Import"), url_for(".bsdatasets_import", account_id=account_id, run=run, appsession_bsid=appsession_bsid)), 
               "back": (_("Back"), back), 
               "cancel": (_("Cancel"), here)}
    table = {"head": (Markup(render_template("checkbox.html", master=True)), _("Name"), _("Lanes"), _("Reads PF"), _("Size"), _("Created"), _("Import Status")),
             "body": body,
             "showhide": False,
             "autoupdate": {"key": 1, "value": 6, "href": url_for(".bsdatasets_status", appsession_bsid=appsession_bsid), "miliseconds": 5000},
             "breadcrumbs": ((_("Accounts"), url_for(".accounts"), False), 
                             (account, url_for(".bsruns", account_id=account_id, run_offset=run_offset), False),
                             (experimentname, back, False),
                             (query["Application"]["Name"], here, True))}
    return render_page("table.html", table=table, buttons=buttons, warning="Are you sure you want to import these files?")

        #for prop in properties:
            #if prop["Name"] == "Logs.Tail":
                ## Illumina what the f**k are you doing! Nul bytes in a string!!! Really!!!!
                #prop["Content"] = prop["Content"].replace("\x00", "").replace("\x01", "")



@app.route("/appsessions/<string:appsession_bsid>/status")
def bsdatasets_status(appsession_bsid):
    sql = """SELECT users.name, project.name, bsimportedsample.name, bsimportedsample.datetime_modified, bsimportedsample.status, bsimportedsample.details
             FROM bsimportedsample
             INNER JOIN project ON project.id = bsimportedsample.project_id
             INNER JOIN users on users.id = bsimportedsample.users_id
             WHERE bsimportedsample.bsappsession_bsid = %(appsession_bsid)s;"""
    with Cursor() as cur:
        result = {}
        cur.execute(sql, {"appsession_bsid":appsession_bsid})
        for user, project, name, datetime_modified, status, details in cur:
            if status == "in-progress":
                text = _("Importing {}").format(details)
            elif ststus == "failed":
                text = _("Import Failed: {}").format(details)
            elif status == "complete":
                text = _("Imported to {}").format(project)
            else:
                # Should never happen, but just in case
                continue
            result[name] = text
    return result



@app.route("/accounts/<int:account_id>/runs/<csv:run>/appsessions/<string:appsession_bsid>/import", methods=["POST"])
def bsdatasets_import(account_id, run, appsession_bsid):
    run_bsid, experimentname = run.split(",", maxsplit=1)
    account, server, token = credentials(account_id) or abort(BadRequest)
    if request.form.get("csrf", "") != session["csrf"]:
        abort(BadRequest)
    
    sql = """SELECT fastq_s3_path FROM project WHERE project.id = %(project_id)s;"""
    with Cursor() as cur:
        cur.execute(sql, {"project_id": session["project_id"] or 0})
        fastq_s3_path = (cur.fetchone() or ("",))[0]
        if not fastq_s3_path.lower().startswith("s3://"):
            raise InternalServerError("Unable to import. No S3 path available.")
    
    callback_token = sign_token({"account_id": account_id,
                                 "appsession_bsid": appsession_bsid,
                                 "users_id": session["id"],
                                 "project_id": session["project_id"],
                                 "--output-dir": fastq_s3_path}, salt="import_callback")
    callback = absolute_url_for(".import_callback", token=callback_token)
    
    names = [k for k, v in request.form.items() if v == "on"]
    args = names + ["--server", server,
                    "--token", token,
                    "--appsession-bsid", appsession_bsid,
                    "--output-dir", fastq_s3_path,
                    "--callback", callback]
    print(" ".join(shlex.quote(arg) for arg in args))
    retval = run_task("bsimport", args)
    print(retval)
    return redirect(request.referrer)



@app.route("/callback/import/<string:token>", signature="import_callback", max_age=24*60*60, methods=["POST"])
def import_callback(token):
    status = request.form["status"]
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """INSERT INTO bsimportedsample (bsappsession_id, name, users_id, project_id, datetime_modified, status, details)
                     VALUES (%(bsappsession_id)s, %(name)s, %(users_id)s, %(project_id)s, current_timestamp, %(status)s, %(details)s)
                     ON CONFLICT ON CONSTRAINT uq_bsimportedsample_bsappsession_id_name
                     DO UPDATE SET users_id = %(users_id)s, project_id = %(project_id)s, datetime_modified = current_timestamp, status = %(status)s, details = %(details)s;"""
            cur.execute(sql, {"bsappsession_id": token["bsappsession_id"],
                              "name": request.form["name"],
                              "users_id": token["users_id"],
                              "project_id": token["project_id"],
                              "status": status,
                              "details": request.form["details"]})
            trans.commit()
            
            if status != "complete":
                return {}
            
            
            return {}
            account, server, token = credentials(token["account_id"]) or abort(BadRequest)

            
            
            
            sql = """INSERT INTO analysis ()
                     VALUES ()
                     RETURNING id;"""
            cur.execute(sql, {})
            analysis_id = cur.fetchone()[0]
            
            sql = """INSERT INTO audittrail (action, target, name, keyvals, users_id, ip_address)
                     VALUES ('Import', 'BaseSpace', %(runsample)s, %(keyvals)s, %(users_id)s, %(ip_address)s)
                     RETURNING id;"""
            cur.execute(sql, {"runsample": token["runsample"],
                              "keyvals": {"Status": request.form["status"], "Project": ""}, 
                              "users_id": token["users_id"], 
                              "ip_address": token["ip_address"]})
            audittrail_id = cur.fetchone()[0]
            
            sql = """INSERT INTO auditlink (audittrail_id, tablename, row_id)
                     VALUES (%(audittrail_id)s, %(tablename)s, %(row_id)s)
                     ON CONFLICT DO NOTHING;"""
            values = [{"audittrail_id": audittrail_id, "tablename": "appsession", "row_id": token["appsession_id"]},
                      {"audittrail_id": audittrail_id, "tablename": "analysis", "row_id": analysis_id}]
            execute_batch(cur, sql, values)
    return {}











