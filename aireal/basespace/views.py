import pdb, os
from datetime import datetime, timedelta, date
from itertools import count
from contextlib import closing
import socket
from itertools import chain
from collections import defaultdict, OrderedDict

from sqlalchemy import select, join, or_, outerjoin, and_
from sqlalchemy.exc import IntegrityError

from flask import session, redirect, url_for, request, send_file, Blueprint, current_app
from werkzeug.exceptions import Conflict, Forbidden, BadRequest, NotFound
from werkzeug.datastructures import MultiDict
from jinja2 import Markup

from .models import users, bsaccounts, users_bsaccounts, bsruns, bsappsessions, bssamples, bsdatasets, projects, bsaccounts_bsruns, bsprojects, bsaccounts_bsprojects
from .basespace import Session, Session2
from .forms import SelectSamplesForm

from limscore import engine, login_required, url_back, url_fwrd, navbar, abort, tablerow, navbar, Local, render_page, render_template, iso8601_to_utc
from limscore.i18n import _


app = Blueprint("basespace", __name__, url_prefix="/basespace", template_folder="templates")



@app.route("/accounts")
@login_required("Bioinformatics.")
def accounts():
    with engine.connect() as conn:
        sql = select([bsaccounts.c.id, bsaccounts.c.name]). \
                select_from(join(bsaccounts, users_bsaccounts, bsaccounts.c.id == users_bsaccounts.c.bsaccount_id)). \
                where(users_bsaccounts.c.user_id == session["id"]). \
                order_by(bsaccounts.c.name)
        body = []
        for row in conn.execute(sql):
            url_link = url_fwrd(".runs", account_id=row["id"])
            body += [tablerow(row["name"],
                              href=url_link)]
    
    table = {"head": (_("Account"),),
             "body": body}
    buttons = {"new": ("", url_fwrd(".new_account"))}
    return render_page("table.html", table=table, title=_("BaseSpace"), buttons=buttons)



@app.route("/accounts/new")
@login_required("Bioinformatics.")
def new_account():
    buttons = {"back": (_("Back"), url_back())}
    sock_path = os.path.join(current_app.instance_path, "auth_sock")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    
    packets = []
    try:
        with closing(sock):
            sock.settimeout(1)
            sock.connect(sock_path)
            sock.settimeout(2)
            sock.sendall("{}\n".format(session["id"]).encode())
            msg = b""
            while not msg.endswith(b"\n"):
                msg += sock.recv(1024)
        
        url = msg.decode().strip()
        text = [_("Please follow link to BaseSpace and authenticate."),
                _("For BaseSpace Enterprise please ensure you are logged into the the correct workgroup before clicking link.")]
        buttons["external"] = (_("BaseSpace"), url)
        
    except (socket.timeout, BlockingIOError):
        # This is approx the basespace cli timeout
        text = [_("Server busy, please try again in 2 minutes time.")]
    except ConnectionRefusedError:
        text = [_("Unable to connect to deamon.")]
    
    return render_page("basespace_auth.html", text=text, buttons=buttons)



@app.route("/accounts/<int:account_id>/runs")
@login_required("Bioinformatics.")
def runs(account_id):
    with engine.connect() as conn:
        sql = select([bsaccounts.c.name, bsaccounts.c.token, bsruns.c.bsid, bsruns.c.attr, bsruns.c.num_total, bsruns.c.num_uploaded]). \
                select_from(join(bsaccounts, users_bsaccounts, bsaccounts.c.id == users_bsaccounts.c.bsaccount_id). \
                            outerjoin(bsaccounts_bsruns, bsaccounts_bsruns.c.bsaccount_id == bsaccounts.c.id). \
                            outerjoin(bsruns, bsaccounts_bsruns.c.bsrun_id == bsruns.c.id)). \
                where(and_(bsaccounts.c.id == account_id, users_bsaccounts.c.user_id == session["id"])). \
                order_by(bsruns.c.attr["DateModified"].desc())
        old_rows = list(dict(row) for row in conn.execute(sql)) or abort(BadRequest)
        row = old_rows[0]
        last_modified = row["attr"]["DateModified"] if row["attr"] is not None else None
        account = row["name"]
        bs = Session(row["token"])
        if row["bsid"] is None:
            old_rows = []

        new_rows = []
        # Don't repeat the expensive search for new runs if going backwards
        if request.args.get("dir", "0") != "-1":
            for attr in bs.search("runs", query="(experimentname:*)", SortBy="DateModified", SortDir="Desc"):
                if last_modified and attr["DateModified"] <= last_modified:
                    break
                print(attr["ExperimentName"])
                bsrun_bsid = int(attr["Id"])
                try:
                    attr = bs.get_single(f"runs/{bsrun_bsid}")
                # Insufficient permissions! Should not have been found in the first place!
                except RuntimeError: 
                    continue
                new_rows += [{"attr": attr, "bsid": bsrun_bsid, "num_total": None, "num_uploaded": None}]

            with conn.begin():
                for row in new_rows:
                    trans = conn.begin_nested()
                    try:
                        bsrun_id = conn.execute(bsruns.insert().values(**row)).inserted_primary_key[0]
                        conn.execute(bsaccounts_bsruns.insert().values(bsrun_id=bsrun_id, bsaccount_id=account_id))
                        trans.commit()
                    except IntegrityError:
                        trans.rollback()
                        
                        bsrun_id = conn.execute(select([bsruns.c.id]).where(bsruns.c.bsid == row["bsid"])).scalar()
                        conn.execute(bsruns.update().where(bsruns.c.id == bsrun_id).values(**row))
                        trans = conn.begin_nested()
                        try:
                            conn.execute(bsaccounts_bsruns.insert().values(bsrun_id=bsrun_id, bsaccount_id=account_id))
                            trans.commit()
                        except IntegrityError:
                            trans.rollback()

    body = []
    for row in sorted(chain(new_rows, old_rows), key=lambda x:x["attr"]["DateModified"], reverse=True):
        attr = row["attr"]
        utcdate = iso8601_to_utc(attr["DateCreated"])
        if row.get("num_total", None) is not None and row.get("num_uploaded", None) is not None:
            uploaded = "{} / {}".format(row["num_uploaded"], row["num_total"])
        else:
            uploaded = ""
        if attr["Status"] == "Complete":
            url = url_fwrd(".samples", account_id=account_id, bsrun_bsid=attr["Id"])
        else:
            url = None
        body += [tablerow(attr["ExperimentName"],
                        attr["InstrumentType"],
                        attr["InstrumentName"],
                        attr["Status"],
                        Local(utcdate),
                        uploaded,
                        href=url)]
    
    tabs = ({"text": "Runs", "active": True}, {"text": "Projects", "href": url_for(".projectlist", account_id=account_id)})
    table = {"head": (_("Name"), _("Platform"), _("Machine"), _("Status"), _("Date"), _("Uploaded")),
             "body": body}
    return render_page("table.html",
                       title=account,
                       table=table,
                       buttons={"back": (_("Back"), url_back())},
                       tabs=tabs)



@app.route("/runs/<int:account_id>/<int:bsrun_bsid>/samples", methods=["GET", "POST"])
@login_required("Bioinformatics.")
def samples(account_id, bsrun_bsid):
    with engine.connect() as conn:
        sql = select([bsaccounts.c.token,
                      bsruns.c.id.label("bsrun_id"),
                      bsruns.c.attr.label("run_attr"),
                      bsruns.c.num_total,
                      bsappsessions.c.attr.label("appsession_attr"),
                      bssamples.c.id.label("bssample_id"),
                      bssamples.c.name,
                      bssamples.c.reads_pf,
                      bssamples.c.status,
                      bssamples.c.upload_datetime,
                      projects.c.name.label("project"),
                      users.c.name.label("user")]). \
                select_from(join(bsaccounts, users_bsaccounts, bsaccounts.c.id == users_bsaccounts.c.bsaccount_id). \
                            join(bsaccounts_bsruns, bsaccounts_bsruns.c.bsaccount_id == bsaccounts.c.id). \
                            join(bsruns, bsaccounts_bsruns.c.bsrun_id == bsruns.c.id). \
                            outerjoin(bsappsessions, bsappsessions.c.bsrun_id == bsruns.c.id). \
                            outerjoin(bssamples, bssamples.c.bsappsession_id == bsappsessions.c.id). \
                            outerjoin(projects, projects.c.id == bssamples.c.project_id). \
                            outerjoin(users, users.c.id == bssamples.c.user_id)). \
                where(and_(bsruns.c.bsid == bsrun_bsid,
                           bsaccounts_bsruns.c.bsaccount_id == account_id,
                           users_bsaccounts.c.user_id == session["id"])). \
                order_by(bsappsessions.c.attr["DateCreated"].desc())
        old_rows = list(dict(row) for row in conn.execute(sql)) or abort(BadRequest)
        row = old_rows[0]
        if not row["appsession_attr"]:
            old_rows = []
        
        bsrun_id = row["bsrun_id"]
        experimentname = row["run_attr"]["ExperimentName"]
        current_appsession_bsid = None
        if old_rows:
            current_appsession_bsid = row["appsession_attr"]["Id"]
        
        # Should alter to get 0 / 0 if no appsessions.
        new_rows = []
        if row["num_total"] is None:
            bs2 = Session2(row["token"])
            new_appsessions = OrderedDict()
            for appsession_attr in bs2.get_multiple("appsessions", params={"input.runs": bsrun_bsid, "sortby": "DateCreated", "sortdir": "Desc"}):
                print(appsession_attr["Name"])
                appsession_bsid = appsession_attr["Id"]
                if appsession_bsid == current_appsession_bsid:
                    break
                
                if appsession_attr["ExecutionStatus"] == "Complete":
                    sample_datasets = defaultdict(list)
                    appsession_attr = bs2.get_single(f"appsessions/{appsession_bsid}")
                    for prop in appsession_attr["Properties"]["Items"]:
                        
                        if prop["Name"] == "Logs.Tail":
                            # Illumina what the f**k are you doing! Nul bytes in a string!!! Really!!!!
                            prop["Content"] = prop["Content"].replace("\x00", "").replace("\x01", "")
                        
                        if prop["Name"] == "Output.Datasets":
                            for dataset_attr in prop["DatasetItems"]:
                                print(dataset_attr["Name"])
                                if "common_fastq" not in dataset_attr["Attributes"]:
                                    # log error
                                    continue
                                
                                if  dataset_attr["Name"][-5:-3] != "_L":
                                    # log error
                                    continue
                                    
                                name = dataset_attr["Name"][:-5]
                                sample_datasets[name] += [dataset_attr]
                            
                    new_appsessions[appsession_bsid] = [appsession_attr, sample_datasets]
                
            if new_appsessions:
                with conn.begin() as trans:
                    num_total = 0
                    for current_appsession_bsid, attr_samples in new_appsessions.items():
                        num_total = len(attr_samples[1])
                        break
                    sql = bsruns.update().where(bsruns.c.id == bsrun_id).values(num_total=num_total, num_uploaded=0)
                    conn.execute(sql)
                        
                    for appsession_attr, datasets in new_appsessions.values():
                        sql = bsappsessions.insert().values(bsid=appsession_attr["Id"],
                                                            bsrun_id=bsrun_id,
                                                            attr=appsession_attr)
                        bsappsession_id = conn.execute(sql).inserted_primary_key[0]
                        
                        for name, attrs in datasets.items():
                            reads_pf = 0
                            for attr in attrs:
                                reads_pf += attr["Attributes"]["common_fastq"]["TotalReadsPF"]
                
                            sql = bssamples.insert().values(bsappsession_id=bsappsession_id, name=name, reads_pf=reads_pf)
                            bssample_id = conn.execute(sql).inserted_primary_key[0]
                            values = [{"bsid": attr["Id"], "bssample_id": bssample_id, "attr": attr} for attr in attrs]
                            conn.execute(bsdatasets.insert().values(values))

                            new_rows += [{"appsession_attr": appsession_attr,
                                        "bssample_id": bssample_id,
                                        "name": name,
                                        "reads_pf": reads_pf}]


        form = SelectSamplesForm(request.form)
        invalid_bssample_ids = set()
        body = []
        for row in chain(new_rows, old_rows):
            appsession_attr = row["appsession_attr"]
            utcdate = iso8601_to_utc(appsession_attr["DateCreated"])
            obsolete = appsession_attr["Id"] != current_appsession_bsid
            choice = [row["bssample_id"], ""]
            if obsolete or row.get("status", "") != "":
                choice += ["disabled"]
                invalid_bssample_ids.add(choice[0])
            checkbox = form.bssample_ids.checkbox(choice)
            body += [tablerow(row["name"],
                              row["reads_pf"],
                              appsession_attr["Application"]["Name"],
                              Local(utcdate),
                              row.get("project", "") or "",
                              row.get("status", "") or "",
                              Local(row.get("upload_datetime", None)),
                              deleted=obsolete,
                              checkbox=checkbox)]
        
        project = session.get("project", None)
        if request.method == "POST" and form.validate():
            if not project:
                form.error = _("Project must be selected before uploading.")
            else:
                selected_bssample_ids = set(form.bssample_ids.data) - invalid_bssample_ids
                sql = bssamples.update(). \
                        where(and_(bssamples.c.id.in_(selected_bssample_ids), bssamples.c.status == "")). \
                        values(project_id=session["project_id"],
                               user_id=session["id"],
                               status="Queued")
                #conn.execute(sql)
                
                # Update uploaded obsolete files.
                # Wake daemon.
                    
                print(selected_bssample_ids)
                return redirect(url_for(".samples", account_id=account_id, bsrun_bsid=bsrun_bsid))
    
    table = {"head": (_("Sample"), _("Reads PF"), _("Application"), _("Date"), _("Project"), _("Status"), _("Date")),
             "body": body}
    if project:
        msg = _("Are you sure you want to upload these samples to {}?").format(project)
        button = (_("Import"), url_for(".samples", account_id=account_id, bsrun_bsid=bsrun_bsid))
        modal = {"back": (_("Back"), url_back()), "text": msg, "submit": button} 
    else:
        modal = None
    buttons = {"submit": (_("Import"), "#"), "back": (_("Cancel"), url_back())}
    return render_page("formtable.html",
                       form=form,
                       title=experimentname,
                       table=table,
                       buttons=buttons,
                       modal=modal)



























@app.route("/accounts/<int:account_id>/projects")
@login_required("Bioinformatics.")
def projectlist(account_id):
    with engine.connect() as conn:
        sql = select([bsaccounts.c.name, bsaccounts.c.token, bsprojects.c.bsid, bsprojects.c.attr, bsprojects.c.num_total, bsprojects.c.num_uploaded]). \
                select_from(join(bsaccounts, users_bsaccounts, bsaccounts.c.id == users_bsaccounts.c.bsaccount_id). \
                            outerjoin(bsaccounts_bsprojects, bsaccounts_bsprojects.c.bsaccount_id == bsaccounts.c.id). \
                            outerjoin(bsprojects, bsaccounts_bsprojects.c.bsproject_id == bsprojects.c.id)). \
                where(and_(bsaccounts.c.id == account_id, users_bsaccounts.c.user_id == session["id"])). \
                order_by(bsprojects.c.attr["DateModified"].desc())
        old_rows = list(dict(row) for row in conn.execute(sql)) or abort(BadRequest)
        row = old_rows[0]
        last_modified = row["attr"]["DateModified"] if row["attr"] is not None else None
        account = row["name"]
        bs = Session(row["token"])
        if row["bsid"] is None:
            old_rows = []

        #pdb.set_trace()
        new_rows = []
        # Don't repeat the expensive search for new runs if going backwards
        if request.args.get("dir", "0") != "-1":
            for attr in bs.get_multiple("users/current/projects"):
                pdb.set_trace()
                if last_modified and attr["DateModified"] <= last_modified:
                    break
                bsproject_bsid = int(attr["Id"])
                try:
                    attr = bs.get_single(f"projects/{bsrun_bsid}")
                # Insufficient permissions! Should not have been found in the first place!
                except RuntimeError: 
                    continue
                new_rows += [{"attr": attr, "bsid": bsproject_bsid, "num_total": None, "num_uploaded": None}]

            with conn.begin():
                for row in new_rows:
                    trans = conn.begin_nested()
                    try:
                        bsrun_id = conn.execute(bsprojects.insert().values(**row)).inserted_primary_key[0]
                        conn.execute(bsaccounts_bsprojects.insert().values(bsrun_id=bsrun_id, bsaccount_id=account_id))
                        trans.commit()
                    except IntegrityError:
                        trans.rollback()
                        
                        bsrun_id = conn.execute(select([bsprojects.c.id]).where(bsprojects.c.bsid == row["bsid"])).scalar()
                        conn.execute(bsprojects.update().where(bsprojects.c.id == bsrun_id).values(**row))
                        trans = conn.begin_nested()
                        try:
                            conn.execute(bsaccounts_bsprojects.insert().values(bsrun_id=bsrun_id, bsaccount_id=account_id))
                            trans.commit()
                        except IntegrityError:
                            trans.rollback()

    body = []
    for row in sorted(chain(new_rows, old_rows), key=lambda x:x["attr"]["DateModified"], reverse=True):
        attr = row["attr"]
        utcdate = iso8601_to_utc(attr["DateCreated"])
        if row.get("num_total", None) is not None and row.get("num_uploaded", None) is not None:
            uploaded = "{} / {}".format(row["num_uploaded"], row["num_total"])
        else:
            uploaded = ""
        if attr["Status"] == "Complete":
            url = url_fwrd(".samples", account_id=account_id, bsrun_bsid=attr["Id"])
        else:
            url = None
        body += [tablerow(attr["ExperimentName"],
                        attr["InstrumentType"],
                        attr["InstrumentName"],
                        attr["Status"],
                        Local(utcdate),
                        uploaded,
                        href=url)]
    
    tabs = ({"text": "Runs", "active": True}, {"text": "Projects", "href": url_for(".runs", account_id=account_id)})
    table = {"head": (_("Name"), _("Platform"), _("Machine"), _("Status"), _("Date"), _("Uploaded")),
             "body": body}
    return render_page("table.html",
                       title=account,
                       table=table,
                       buttons={"back": (_("Back"), url_back())},
                       tabs=tabs)



