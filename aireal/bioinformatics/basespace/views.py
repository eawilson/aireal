import os
import uuid
import shlex
import subprocess
import time
import requests
import re
from html import escape

from itertools import chain
from collections import defaultdict, OrderedDict
import pdb

from flask import session, redirect, url_for, request, send_file, current_app
from werkzeug.exceptions import Conflict, Forbidden, BadRequest, NotFound
from jinja2 import Markup

from psycopg2.extras import execute_batch

from .basespace import Session, Session2
from .forms import ServerForm#, SelectSamplesForm


from ...flask import abort, render_page, render_template, Blueprint, sign_token, absolute_url_for
from ...utils import Cursor, Transaction, tablerow, iso8601_to_utc
from ...i18n import _
from ...wrappers import Local


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
        token = sign_token({"users_id": session["id"], "bsserver_id": form.bsserver_id.data}, salt="basespace_callback")
        callback = absolute_url_for(".basespace_callback", token=token)
        
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
    


@app.route("/callback/<string:token>", signature="basespace_callback", max_age=60*60, methods=["POST"])
def basespace_callback(token):
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



@app.route("/accounts/<int:account_id>/runs/<int:bsrun_bsid>/appsessions/<int:bsappsession_bsid>", methods=["GET", "POST"])
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
    
    if datetime_modified is None or datetime_bsmodified > datetime_modified:
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
    
    body = []
    values = []
    for prop in properties:
        if prop["Name"] == "Output.Datasets":
            items = prop["DatasetItems"]
            items.sort(key=lambda p:p["Name"])
            for item in items:
                name = item["Name"]
                if trim_lane_regex.search(name):
                    lane = int(name[-3:])
                    name = name[:-5]
                else:
                    lane = None
                
                if body and body[-1][0][1] == name:
                    body[-1][0][2] += item["Attributes"].get("common_fastq", {}).get("TotalReadsPF", 0)
                else:
                    body.append(([Markup(render_template("checkbox.html", form="table-form", name=escape(name))),
                                  name,
                                  item["Attributes"].get("common_fastq", {}).get("TotalReadsPF", 0),
                                  "{:.2f}GB".format(item.get("TotalSize", 0) / 1000000000),
                                  Local(iso8601_to_utc(item["DateCreated"]))],{}))
                values.append({"bsserver_id": bsserver_id,
                               "bsappsession_id": bsappsession_id,
                               "bsid": str(item["Id"]), 
                               "name": name,
                               "attr": item,
                               "lane": lane,
                               "datetime_bsmodified": iso8601_to_utc(item["DateModified"])})
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """INSERT INTO bsdataset (bsserver_id, bsappsession_id, bsid, name, attr, lane, datetime_modified, datetime_bsmodified)
                     VALUES (%(bsserver_id)s, %(bsappsession_id)s, %(bsid)s, %(name)s, %(attr)s, %(lane)s, current_timestamp, %(datetime_bsmodified)s)
                     ON CONFLICT ON CONSTRAINT uq_bsdataset_bsid_bsserver_id
                     DO UPDATE SET datetime_bsmodified = %(datetime_bsmodified)s, attr = %(attr)s, datetime_modified = current_timestamp
                     WHERE bsdataset.datetime_modified < %(datetime_bsmodified)s;"""
            execute_batch(cur, sql, values)

    table = {"head": (Markup(render_template("checkbox.html", master=True)), _("Name"), _("Reads PF"), _("Size"), _("Created")),
             "body": body,
             "showhide": False,
             "breadcrumbs": ((_("Accounts"), url_for(".accounts"), False), 
                             (account, url_for(".bsruns", account_id=account_id), False),
                             (experimentname, url_for(".bsappsessions", account_id=account_id, bsrun_bsid=bsrun_bsid), False),
                             (query["Application"]["Name"], url_for(".bsdatasets", account_id=account_id, bsrun_bsid=bsrun_bsid, bsappsession_bsid=bsappsession_bsid), True))}
    return render_page("table.html", table=table, buttons=())

























 
        
            
            #if prop["Name"] == "Logs.Tail":
                ## Illumina what the f**k are you doing! Nul bytes in a string!!! Really!!!!
                #prop["Content"] = prop["Content"].replace("\x00", "").replace("\x01", "")
            
            #if prop["Name"] == "Output.Datasets":
                #for dataset_attr in prop["DatasetItems"]:
                    #print(dataset_attr["Name"])
                    #if "common_fastq" not in dataset_attr["Attributes"]:
                        ## log error
                        #continue
                    
                    #if  dataset_attr["Name"][-5:-3] != "_L":
                        ## log error
                        #continue
                        
                    #name = dataset_attr["Name"][:-5]
                    #sample_datasets[name] += [dataset_attr]
                    
            #new_appsessions[appsession_bsid] = [appsession_attr, sample_datasets]
                
            #if new_appsessions:
                #with conn.begin() as trans:
                    #num_total = 0
                    #for current_appsession_bsid, attr_samples in new_appsessions.items():
                        #num_total = len(attr_samples[1])
                        #break
                    #sql = bsruns.update().where(bsruns.c.id == bsrun_id).values(num_total=num_total, num_uploaded=0)
                    #conn.execute(sql)
                        
                    #for appsession_attr, datasets in new_appsessions.values():
                        #sql = bsappsessions.insert().values(bsid=appsession_attr["Id"],
                                                            #bsrun_id=bsrun_id,
                                                            #attr=appsession_attr)
                        #bsappsession_bsid = conn.execute(sql).inserted_primary_key[0]
                        
                        #for name, attrs in datasets.items():
                            #reads_pf = 0
                            #for attr in attrs:
                                #reads_pf += attr["Attributes"]["common_fastq"]["TotalReadsPF"]
                
                            #sql = bssamples.insert().values(bsappsession_bsid=bsappsession_bsid, name=name, reads_pf=reads_pf)
                            #bssample_id = conn.execute(sql).inserted_primary_key[0]
                            #values = [{"bsid": attr["Id"], "bssample_id": bssample_id, "attr": attr} for attr in attrs]
                            #conn.execute(bsdatasets.insert().values(values))

                            #new_rows += [{"appsession_attr": appsession_attr,
                                        #"bssample_id": bssample_id,
                                        #"name": name,
                                        #"reads_pf": reads_pf}]


        #form = SelectSamplesForm(request.form)
        #invalid_bssample_ids = set()
        #body = []
        #for row in chain(new_rows, old_rows):
            #appsession_attr = row["appsession_attr"]
            #utcdate = iso8601_to_utc(appsession_attr["DateCreated"])
            #obsolete = appsession_attr["Id"] != current_appsession_bsid
            #choice = [row["bssample_id"], ""]
            #if obsolete or row.get("status", "") != "":
                #choice += ["disabled"]
                #invalid_bssample_ids.add(choice[0])
            #checkbox = form.bssample_ids.checkbox(choice)
            #body += [tablerow(row["name"],
                              #row["reads_pf"],
                              #appsession_attr["Application"]["Name"],
                              #Local(utcdate),
                              #row.get("project", "") or "",
                              #row.get("status", "") or "",
                              #Local(row.get("upload_datetime", None)),
                              #deleted=obsolete,
                              #checkbox=checkbox)]
        
        #project = session.get("project", None)
        #if request.method == "POST" and form.validate():
            #if not project:
                #form.error = _("Project must be selected before uploading.")
            #else:
                #selected_bssample_ids = set(form.bssample_ids.data) - invalid_bssample_ids
                #sql = bssamples.update(). \
                        #where(and_(bssamples.c.id.in_(selected_bssample_ids), bssamples.c.status == "")). \
                        #values(project_id=session["project_id"],
                               #user_id=session["id"],
                               #status="Queued")
                ##conn.execute(sql)
                
                ## Update uploaded obsolete files.
                ## Wake daemon.
                    
                #print(selected_bssample_ids)
                #return redirect(url_for(".samples", account_id=account_id, bsrun_bsid=bsrun_bsid))
    
    #table = {"head": (_("Sample"), _("Reads PF"), _("Application"), _("Date"), _("Project"), _("Status"), _("Date")),
             #"body": body}
    #if project:
        #msg = _("Are you sure you want to upload these samples to {}?").format(project)
        #button = (_("Import"), url_for(".samples", account_id=account_id, bsrun_bsid=bsrun_bsid))
        #modal = {"back": (_("Back"), url_back()), "text": msg, "submit": button} 
    #else:
        #modal = None
    #buttons = {"submit": (_("Import"), "#"), "back": (_("Cancel"), url_back())}
    #return render_page("formtable.html",
                       #form=form,
                       #title=experimentname,
                       #table=table,
                       #buttons=buttons,
                       #modal=modal)



























#@app.route("/accounts/<int:account_id>/projects")
#def projectlist(account_id):
    #with engine.connect() as conn:
        #sql = select([bsaccounts.c.name, bsaccounts.c.token, bsprojects.c.bsid, bsprojects.c.attr, bsprojects.c.num_total, bsprojects.c.num_uploaded]). \
                #select_from(join(bsaccounts, bsaccount_userss, bsaccounts.c.id == bsaccount_userss.c.bsaccount_id). \
                            #outerjoin(bsaccounts_bsprojects, bsaccounts_bsprojects.c.bsaccount_id == bsaccounts.c.id). \
                            #outerjoin(bsprojects, bsaccounts_bsprojects.c.bsproject_id == bsprojects.c.id)). \
                #where(and_(bsaccounts.c.id == account_id, bsaccount_userss.c.user_id == session["id"])). \
                #order_by(bsprojects.c.attr["DateModified"].desc())
        #old_rows = list(dict(row) for row in conn.execute(sql)) or abort(BadRequest)
        #row = old_rows[0]
        #last_modified = row["attr"]["DateModified"] if row["attr"] is not None else None
        #account = row["name"]
        #bs = Session(row["token"])
        #if row["bsid"] is None:
            #old_rows = []

        ##pdb.set_trace()
        #new_rows = []
        ## Don't repeat the expensive search for new runs if going backwards
        #if request.args.get("dir", "0") != "-1":
            #for attr in bs.get_multiple("users/current/projects"):
                #pdb.set_trace()
                #if last_modified and attr["DateModified"] <= last_modified:
                    #break
                #bsproject_bsid = int(attr["Id"])
                #try:
                    #attr = bs.get_single(f"projects/{bsrun_bsid}")
                ## Insufficient permissions! Should not have been found in the first place!
                #except RuntimeError: 
                    #continue
                #new_rows += [{"attr": attr, "bsid": bsproject_bsid, "num_total": None, "num_uploaded": None}]

            #with conn.begin():
                #for row in new_rows:
                    #trans = conn.begin_nested()
                    #try:
                        #bsrun_id = conn.execute(bsprojects.insert().values(**row)).inserted_primary_key[0]
                        #conn.execute(bsaccounts_bsprojects.insert().values(bsrun_id=bsrun_id, bsaccount_id=account_id))
                        #trans.commit()
                    #except IntegrityError:
                        #trans.rollback()
                        
                        #bsrun_id = conn.execute(select([bsprojects.c.id]).where(bsprojects.c.bsid == row["bsid"])).scalar()
                        #conn.execute(bsprojects.update().where(bsprojects.c.id == bsrun_id).values(**row))
                        #trans = conn.begin_nested()
                        #try:
                            #conn.execute(bsaccounts_bsprojects.insert().values(bsrun_id=bsrun_id, bsaccount_id=account_id))
                            #trans.commit()
                        #except IntegrityError:
                            #trans.rollback()

    #body = []
    #for row in sorted(chain(new_rows, old_rows), key=lambda x:x["attr"]["DateModified"], reverse=True):
        #attr = row["attr"]
        #utcdate = iso8601_to_utc(attr["DateCreated"])
        #if row.get("num_total", None) is not None and row.get("num_uploaded", None) is not None:
            #uploaded = "{} / {}".format(row["num_uploaded"], row["num_total"])
        #else:
            #uploaded = ""
        #if attr["Status"] == "Complete":
            #url = url_fwrd(".samples", account_id=account_id, bsrun_bsid=attr["Id"])
        #else:
            #url = None
        #body += [tablerow(attr["ExperimentName"],
                        #attr["InstrumentType"],
                        #attr["InstrumentName"],
                        #attr["Status"],
                        #Local(utcdate),
                        #uploaded,
                        #href=url)]
    
    #tabs = ({"text": "Runs", "active": True}, {"text": "Projects", "href": url_for(".runs", account_id=account_id)})
    #table = {"head": (_("Name"), _("Platform"), _("Machine"), _("Status"), _("Date"), _("Uploaded")),
             #"body": body}
    #return render_page("table.html",
                       #title=account,
                       #table=table,
                       #buttons={"back": (_("Back"), url_back())},
                       #tabs=tabs)



