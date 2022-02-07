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
from werkzeug.exceptions import Conflict, Forbidden, BadRequest, NotFound
from jinja2 import Markup

from psycopg2.extras import execute_batch

from ...flask import abort, render_page, render_template, Blueprint, sign_token, absolute_url_for
from ...utils import Cursor, Transaction, tablerow, iso8601_to_utc
from ...i18n import _
from ...wrappers import Local
from .forms import ServerForm


trim_lane_regex = re.compile("_L[0-9]{3}$")


app = Blueprint("Basespace", __name__, role="Bioinformatics", template_folder="templates")



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
        
        cmd = ["setsid", "bsauth", "--auth-file", auth_file,
                                   "--callback", callback,
                                   "--api-server", urls[form.bsserver_id.data],
                                   "--scopes", "Read Global, Browse Global"]
        # Probably cleaner to use subprocess redirection but I am certain this does what I want
        shell_cmd = " ".join(shlex.quote(arg) for arg in cmd) + " >/dev/null 2>&1 </dev/null &"
        subprocess.run(shell_cmd, shell=True)
        
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
    with Cursor() as cur:
        sql = """SELECT bsaccount.name, bsaccount.token, bsserver.url, bsserver.id
                 FROM bsaccount
                 JOIN bsaccount_users ON bsaccount_users.bsaccount_id = bsaccount.id
                 JOIN bsserver ON bsserver.id = bsaccount.bsserver_id
                 WHERE bsaccount.id = %(account_id)s AND bsaccount_users.users_id = %(users_id)s;"""
        cur.execute(sql, {"account_id": account_id, "users_id": session["id"]})
        account, token, bsserver, bsserver_id = cur.fetchone() or abort(BadRequest)
    
    query = bs_get(f"{bsserver}/v2/search", token, params={"scope": "runs",
                                                           "query": "(experimentname:*)",
                                                           "offset": 0,
                                                           "limit": 10,
                                                           "SortBy": "DateCreated",
                                                           "SortDir": "Desc"})
    paging = query["Paging"]
    displayed_count = paging["DisplayedCount"]
    total_count = paging["TotalCount"]
    offset = paging["Offset"]
    
    body = []
    values = []
    for item in query["Items"]:
        item = item["Run"]
        experimentname = item["ExperimentName"]
        bsid = item["Id"]
        status = item["Status"]
        seqstats = item["SequencingStats"]
        body.append(((experimentname,
                      item["InstrumentType"],
                      item["InstrumentName"],
                      "{:.2f}%".format(seqstats["PercentGtQ30"]),
                      "{:.2f}%".format(seqstats["PercentPf"] * 100),
                      #"{:.2f}%".format(seqstats["ClusterDensity"]),
                      status,
                      Local(iso8601_to_utc(item["DateCreated"]))),
                      {"id": bsid} if status == "Complete" else {}))
        values.append({"bsserver_id": bsserver_id,
                       "bsid": bsid, 
                       "name": experimentname,
                       "status": status,
                       "datetime_bsmodified": iso8601_to_utc(item["DateModified"])})
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """INSERT INTO bsrun (bsserver_id, bsid, name, status, datetime_bsmodified)
                     VALUES (%(bsserver_id)s, %(bsid)s, %(name)s, %(status)s, %(datetime_bsmodified)s)
                     ON CONFLICT ON CONSTRAINT uq_bsrun_bsid_bsserver_id
                     DO UPDATE SET datetime_bsmodified = %(datetime_bsmodified)s, status = %(status)s;"""
            execute_batch(cur, sql, values)
    
    actions = ({"name": _("Select"), "href": url_for(".bsappsessions", account_id=account_id, bsrun_bsid=0)},)
    table = {"head": (_("Name"), _("Platform"), _("Machine"), _("Avg %Q30"), _("%PF"), _("Status"), _("Created")),
             "body": body,
             "showhide": False,
             "actions": actions,
             "breadcrumbs": ((_("Accounts"), url_for(".accounts"), False), (account, url_for(".bsruns", account_id=account_id), True))}
    return render_page("table.html", table=table, buttons=())



@app.route("/accounts/<int:account_id>/runs/<int:bsrun_bsid>", methods=["GET", "POST"])
def bsappsessions(account_id, bsrun_bsid):
    with Cursor() as cur:
        sql = """SELECT bsaccount.name, bsaccount.token, bsserver.url, bsserver.id, bsrun.name, bsrun.datetime_bsmodified, bsrun.datetime_modified, bsrun.id
                 FROM bsaccount
                 JOIN bsaccount_users ON bsaccount_users.bsaccount_id = bsaccount.id
                 JOIN bsserver ON bsserver.id = bsaccount.bsserver_id
                 JOIN bsrun ON bsrun.bsserver_id = bsaccount.bsserver_id
                 WHERE bsaccount.id = %(account_id)s AND bsaccount_users.users_id = %(users_id)s AND bsrun.bsid = %(bsrun_bsid)s AND bsrun.status = 'Complete';"""
        cur.execute(sql, {"account_id": account_id, "users_id": session["id"], "bsrun_bsid": str(bsrun_bsid)})
        account, token, bsserver, bsserver_id, experimentname, datetime_bsmodified, datetime_modified, bsrun_id = cur.fetchone() or abort(BadRequest)
    
    if datetime_modified is None or datetime_bsmodified > datetime_modified:
        query = bs_get(f"{bsserver}/v2/runs/{bsrun_bsid}", token)
        with Transaction() as trans:
            with trans.cursor() as cur:
                sql = """UPDATE bsrun 
                         SET datetime_bsmodified = %(datetime_bsmodified)s, attr = %(attr)s, datetime_modified = current_timestamp
                         WHERE id = %(bsrun_id)s;"""
                cur.execute(sql, {"bsrun_id": bsrun_id, "datetime_bsmodified": query["DateModified"], "attr": query})    
    
    
    query = bs_get(f"{bsserver}/v2/appsessions", token, params={"input.runs": bsrun_bsid,
                                                                "offset": 0,
                                                                "limit": 10,
                                                                "SortBy": "DateCreated",
                                                                "SortDir": "Desc"})
    paging = query["Paging"]
    displayed_count = paging["DisplayedCount"]
    total_count = paging["TotalCount"]
    offset = paging["Offset"]
    body = []
    values = []
    for item in query["Items"]:
        bsid = item["Id"]
        status = item["ExecutionStatus"]
        name = item["Application"]["Name"]
        body.append(((name,
                      status,
                      "{:.2f}GB".format(item.get("TotalSize", 0) / 1000000000),
                      Local(iso8601_to_utc(item["DateCreated"]))),
                      {"id": item["Id"]} if status == "Complete" else {}))
        values.append({"bsserver_id": bsserver_id,
                       "bsrun_id": bsrun_id, 
                       "bsid": bsid, 
                       "name": name,
                       "status": status,
                       "datetime_bsmodified": iso8601_to_utc(item["DateModified"])})
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """INSERT INTO bsappsession (bsserver_id, bsrun_id, bsid, name, status, datetime_bsmodified)
                     VALUES (%(bsserver_id)s, %(bsrun_id)s, %(bsid)s, %(name)s, %(status)s, %(datetime_bsmodified)s)
                     ON CONFLICT ON CONSTRAINT uq_bsappsession_bsid_bsserver_id
                     DO UPDATE SET datetime_bsmodified = %(datetime_bsmodified)s, status = %(status)s;"""
            execute_batch(cur, sql, values)
    
    #if TotalCount == 1 and query["Items"][0]["ExecutionStatus"] == "Complete":
        #bsappsession_bsid = query["Items"][0]["Id"]
        #return redirect(url_for(".bsdatasets", account_id=account_id, bsrun_bsid=bsrun_bsid, bsappsession_bsid=bsappsession_bsid))

    actions = ({"name": _("Select"), "href": url_for(".bsdatasets", account_id=account_id, bsrun_bsid=bsrun_bsid, bsappsession_bsid=0)},)
    table = {"head": (_("Application"), _("Status"), _("Size"), _("Created")),
             "body": body,
             "showhide": False,
             "actions": actions,
             "breadcrumbs": ((_("Accounts"), url_for(".accounts"), False), 
                             (account, url_for(".bsruns", account_id=account_id), False),
                             (experimentname, url_for(".bsappsessions", account_id=account_id, bsrun_bsid=bsrun_bsid), True))}
    return render_page("table.html", table=table, buttons=())



@app.route("/accounts/<int:account_id>/runs/<int:bsrun_bsid>/appsessions/<int:bsappsession_bsid>")
def bsdatasets(account_id, bsrun_bsid, bsappsession_bsid):
    with Cursor() as cur:
        sql = """SELECT bsaccount.name, bsaccount.token, bsserver.url, bsserver.id, bsrun.name, bsappsession.id, bsappsession.datetime_bsmodified, bsappsession.datetime_modified
                 FROM bsaccount
                 JOIN bsaccount_users ON bsaccount_users.bsaccount_id = bsaccount.id
                 JOIN bsserver ON bsserver.id = bsaccount.bsserver_id
                 JOIN bsrun ON bsrun.bsserver_id = bsaccount.bsserver_id
                 JOIN bsappsession ON bsappsession.bsrun_id = bsrun.id
                 WHERE bsaccount.id = %(account_id)s AND bsaccount_users.users_id = %(users_id)s AND bsrun.bsid = %(bsrun_bsid)s
                 AND bsappsession.bsid = %(bsappsession_bsid)s AND bsappsession.status = 'Complete';"""
        cur.execute(sql, {"account_id": account_id, "users_id": session["id"], "bsrun_bsid": str(bsrun_bsid), "bsappsession_bsid": str(bsappsession_bsid)})
        account, token, bsserver, bsserver_id, experimentname, bsappsession_id, datetime_bsmodified, datetime_modified = cur.fetchone() or abort(BadRequest)

    query = bs_get(f"{bsserver}/v2/appsessions/{bsappsession_bsid}", token)
    properties = query["Properties"]["Items"]
    stale_bsappsession = datetime_modified is None or datetime_bsmodified > datetime_modified
    
    if stale_bsappsession:
        for prop in properties:
            if prop["Name"] == "Logs.Tail":
                # Illumina what the f**k are you doing! Nul bytes in a string!!! Really!!!!
                prop["Content"] = prop["Content"].replace("\x00", "").replace("\x01", "")
        
        with Transaction() as trans:
            with trans.cursor() as cur:
                sql = """UPDATE bsappsession 
                         SET datetime_bsmodified = %(datetime_bsmodified)s, attr = %(attr)s, datetime_modified = current_timestamp
                         WHERE id = %(bsappsession_id)s;"""
                cur.execute(sql, {"bsappsession_id": bsappsession_id, "datetime_bsmodified": query["DateModified"], "attr": query})    
    
    items = []
    for prop in properties:
        if prop["Name"] == "Output.Datasets":
            if prop["ItemsDisplayedCount"] == prop["ItemsTotalCount"]:
                items = prop["DatasetItems"]
            else:
                # Does not specify sort direction in Output.Datasets therefore search from beginning again to be safe.
                total = prop["ItemsTotalCount"]
                url = f"https://api.basespace.illumina.com/v2/appsessions/{bsappsession_bsid}/properties/Output.Datasets/items"
                while len(items) < total:
                    response = bs_get(url, token, params={"offset": len(items), "SortBy": "DateCreated", "SortDir": "Desc"})
                    for item in response["Items"]:
                        items.append(item["Dataset"])
    
    body = []
    values = []
    items.sort(key=lambda p:p["Name"])
    for item in items:
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
                         Local(iso8601_to_utc(item["DateCreated"]))],{}))
        if stale_bsappsession:
            values.append({"bsserver_id": bsserver_id,
                           "bsappsession_id": bsappsession_id,
                           "bsid": str(item["Id"]), 
                           "name": name,
                           "attr": item,
                           "lane": lane,
                           "datetime_bsmodified": iso8601_to_utc(item["DateModified"])})
    
    for row in body:
        row[0][4] = "{:.2f}GB".format(row[0][3] / 1000000000)
    
    if values:
        with Transaction() as trans:
            with trans.cursor() as cur:
                sql = """INSERT INTO bsdataset (bsserver_id, bsappsession_id, bsid, name, attr, lane, datetime_modified, datetime_bsmodified)
                         VALUES (%(bsserver_id)s, %(bsappsession_id)s, %(bsid)s, %(name)s, %(attr)s, %(lane)s, current_timestamp, %(datetime_bsmodified)s)
                         ON CONFLICT ON CONSTRAINT uq_bsdataset_bsid_bsserver_id
                         DO UPDATE SET datetime_bsmodified = %(datetime_bsmodified)s, attr = %(attr)s, datetime_modified = current_timestamp
                         WHERE bsdataset.datetime_modified < %(datetime_bsmodified)s;"""
                execute_batch(cur, sql, values)
    
    
    here = url_for(".bsdatasets", account_id=account_id, bsrun_bsid=bsrun_bsid, bsappsession_bsid=bsappsession_bsid)
    back = url_for(".bsappsessions", account_id=account_id, bsrun_bsid=bsrun_bsid)
    buttons = {"submit": (_("Import"), url_for(".bsdatasets_import", account_id=account_id, bsrun_bsid=bsrun_bsid, bsappsession_bsid=bsappsession_bsid)), 
               "back": (_("Back"), back), 
               "cancel": (_("Cancel"), here)}
    table = {"head": (Markup(render_template("checkbox.html", master=True)), _("Name"), _("Lanes"), _("Reads PF"), _("Size"), _("Created")),
             "body": body,
             "showhide": False,
             "breadcrumbs": ((_("Accounts"), url_for(".accounts"), False), 
                             (account, url_for(".bsruns", account_id=account_id), False),
                             (experimentname, back, False),
                             (query["Application"]["Name"], here, True))}
    return render_page("table.html", table=table, buttons=buttons, warning="Are you sure you want to import these files?")



@app.route("/accounts/<int:account_id>/runs/<int:bsrun_bsid>/appsessions/<int:bsappsession_bsid>/datasets", methods=["POST"])
def bsdatasets_import(account_id, bsrun_bsid, bsappsession_bsid):

    csrf_validated = False
    dataset_names = []
    for key, val in request.form.items():
        key = unescape(key)
        if key == "csrf" and val == session["csrf"]:
            csrf_validated = True
        else:
            dataset_names.append(key)

    if csrf_validated:
        with Cursor() as cur:
            sql = """SELECT bsaccount.token, bsserver.url, bsappsession.name, bsappsession.id, bsdataset.attr
                     FROM bsaccount
                     JOIN bsaccount_users ON bsaccount_users.bsaccount_id = bsaccount.id
                     JOIN bsserver ON bsserver.id = bsaccount.bsserver_id
                     JOIN bsrun ON bsrun.bsserver_id = bsaccount.bsserver_id
                     JOIN bsappsession ON bsappsession.bsrun_id = bsrun.id
                     JOIN bsdataset ON bsdataset.bsappsession_id = bsappsession.id
                     WHERE bsaccount.id = %(account_id)s AND bsaccount_users.users_id = %(users_id)s AND bsrun.bsid = %(bsrun_bsid)s
                     AND bsappsession.bsid = %(bsappsession_bsid)s AND bsappsession.status = 'Complete' AND bsdataset.name IN %(selected_names)s;"""
            cur.execute(sql, {"account_id": account_id,
                              "users_id": session["id"], 
                              "bsrun_bsid": str(bsrun_bsid), 
                              "bsappsession_bsid": str(bsappsession_bsid),
                              "selected_names": tuple(dataset_names)})
            
            files = {}
            for token, bsserver, name, appsession_id, attr in cur:
                # This function only receives data from a single appsession therefore name will always uniquely identify a sample
                if name in files:
                    files[name]["files_href"].append(attr["HrefFiles"])
                else:
                    callback_token = sign_token({"bsappsession_id": bsappsession_id,
                                                 "name": name,
                                                 "users_id": session["id"],
                                                 "project_id": session["project_id"]}, salt="import_callback")
                    callback = absolute_url_for(".import_callback", token=callback_token)
                    files[name] = {"files_href": [attr["HrefFiles"]],
                                   "bsserver": bsserver,
                                   "token": token,
                                   "import_url": "",
                                   "callback": callback}
                
    return redirect(url_for(".bsdatasets", account_id=account_id, bsrun_bsid=bsrun_bsid, bsappsession_bsid=bsappsession_bsid))
    


@app.route("/callback/import/<string:token>", signature="import_callback", max_age=60*60, methods=["POST"])
def import_callback(token):
    return {}
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """INSERT INTO bsimported_sample (bsappsession_id, name, users_id, project_id, datetime_modified, status)
                     VALUES (%(bsappsession_id)s, %(name)s, %(users_id)s, %(project_id)s, current_timestamp, %(status)s)
                     ON CONFLICT ON CONSTRAINT uq_bsimported_sample_bsappsession_id_name
                     DO UPDATE SET users_id = %(users_id)s, project_id = %(project_id)s, datetime_modified = current_timestamp, status = %(status)s;"""
            cur.execute(sql, {**token, **request.form})
            
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











