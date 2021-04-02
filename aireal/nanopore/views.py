import pdb

from collections import defaultdict
import socket

from sqlalchemy import select, join, or_, outerjoin, and_
from sqlalchemy.exc import IntegrityError

from flask import session, redirect, url_for, request, send_file, Blueprint, current_app, jsonify
from werkzeug.exceptions import Conflict, Forbidden, BadRequest, NotFound

from .models import nanoporeruns, nanoporesamples, nanoporefiles, nanoporechunks
from .forms import SelectSamplesForm, TextInput
from .utils import parse_run_files

from limscore import engine, login_required, url_back, url_fwrd, navbar, abort, tablerow, navbar, Local, render_page, render_template, iso8601_to_utc
from limscore.i18n import _


app = Blueprint("nanopore", __name__, url_prefix="/nanopore", template_folder="templates")



@app.route("/runs")
@login_required("Bioinformatics.")
def runs():
    with engine.connect() as conn:
        sql = select([nanoporeruns.c.id, nanoporeruns.c.attr, nanoporeruns.c.num_samples, nanoporeruns.c.num_uploaded, nanoporeruns.c.attr["Started"]]). \
                select_from(join(nanoporeruns, nanoporesamples, nanoporeruns.c.id == nanoporesamples.c.nanoporerun_id)). \
                where(and_(nanoporesamples.c.project_id == session.get("project_id", None))). \
                order_by(nanoporeruns.c.attr["Started"].desc()). \
                distinct()
    
        body = []
        for row in conn.execute(sql):
            attr = row["attr"]
            url = url_fwrd(".samples", nanoporerun_id=row[nanoporeruns.c.id])
            if row[nanoporeruns.c.num_samples] is not None:
                uploaded = "{} / {}".format(row[nanoporeruns.c.num_uploaded],
                                            row[nanoporeruns.c.num_samples])
            else:
                uploaded = ""
            body += [tablerow(attr["Experiment Name"],
                            attr["Platform"],
                            attr["Machine"],
                            attr["Status"],
                            Local(iso8601_to_utc(attr["Started"])),
                            uploaded,
                            href=url)]
        
    table = {"head": (_("Run"), _("Platform"), _("Machine"), _("Status"), _("Date"), _("Uploaded")),
             "body": body}
    buttons = {"new": ("", url_fwrd(".new_run"))}
    return render_page("table.html",
                       title=_("Nanopore"),
                       table=table,
                       buttons=buttons)



@app.route("/runs/new", methods=["GET", "POST"])
@login_required("Bioinformatics.")
def new_run():
    form = SelectSamplesForm(request.form, **{"data-href": url_for(".worksheet")})
    if request.method == "POST":
        pass
        
    buttons={"back": (_("Cancel"), url_back())}
    return render_page("uploadform.html", form=form, buttons=buttons, title="Nanopore")



@app.route("/worksheet", methods=["POST"])
@login_required("Bioinformatics.")
def worksheet():
    form = SelectSamplesForm(request.form)
    
    try:
        run_info, new_files = parse_run_files()
    except RuntimeError as e:
        return e.args[0]
    
    with engine.begin() as conn:
        sql = select([nanoporefiles.c.filename,
                      nanoporefiles.c.size,
                      nanoporefiles.c.completed,
                      nanoporesamples.c.nanoporeid,
                      nanoporesamples.c.name,
                      nanoporechunks.c.id,
                      nanoporeruns.c.id.label("run_id")]). \
                select_from(join(nanoporeruns, nanoporesamples, nanoporesamples.c.run_id == nanoporeruns.c.id, isouter=True). \
                            outerjoin(nanoporefiles, nanoporefiles.c.nanoporesample_id == nanoporesamples.c.id). \
                            outerjoin(nanoporechunks, nanoporechunks.c.nanoporefile_id == nanoporefiles.c.id)). \
                where(nanoporeruns.c.nanoporeid == run_info["Run ID"])
        rows = [dict(row) for row in conn.execute(sql)]
        old_files = {row["filename"]: row["size"] for row in rows}
        
        if rows:
            run_id = row[0]["run_id"]
        else:
            run_id = conn.execute(nanoporeruns.insert().values(nanoporeid=run_info["Run ID"], attr=run_info)).inserted_promary_key[0]
            
            
        for name, size in sorted(new_files.items()):
            inserts[()] += [] 
            if name.endswith(".fastq") or name.endswith(".fast5"):
                barcode = name.split("_")[2]
           
        
        
           
           
           
           
           
        #else:
            #run_id = 6
        
        #partial = set(row["id"] for row in rows if row["id"] is not None)#############????????????????????
        
        
        
        
        #inserts = defaultdict(list)
        #barcode = None
        #for name, size in sorted(new_files.items()):
            #inserts[()] += [] 
            #if name.endswith(".fastq") or name.endswith(".fast5"):
                #splitname = name.split()
        
        
        
        
        







        #body = []
        #trans = conn.begin_nested()
        #try:
            #sql = nanoporeruns.insert().values(nanoporeid=run_info["Run ID"],
                                               #num_samples=len(data_files),
                                               #num_uploaded=0,
                                               #attr=run_info)
            #run_id = conn.execute(sql)
            #trans.commit()
        #except IntegrityError:
            #trans.rollback()
            #sql = select([nanoporeruns.c.id]). \
                #where(nanoporeruns.c.nanoporeid == run_info["Run ID"])
            #run_id = conn.execute(sql).scalar()
            
            
            
            
            #sql = select([nanoporesamples.c.barcode,
                          #nanoporesamples.c.name,
                          #nanoporesamples.c.status]). \
                    #where(nanoporesamples.c.run_id == run_id)
            #for row in conn.execute(sql):
                #if row:
                    #pass



                                        
            #names = dict()
            #sql = nanoporesamples.delete().where(where_clause)
            
            
            
            
            
            
            
            
            #sql = select([nanoporesamples.c.]). \
                    #where(nanoporesamples.c.nanoporerun_id == run_id)
            #for row in conn.execute(sql):
                #body += [tablerow(row[nanoporesamples.c.barcode],
                                  #row[nanoporesamples.c.name],
                                  #row[nanoporesamples.c.contents],
                                  #row[nanoporesamples.c.size],
                    #)]
        
        #body = []
        #for index, item in enumerate(sorted(data_files.items())):
            #barcode, files = item
            #numbers = ["{} x {}".format(k, len(v)) for k, v in files.items()]
            #bytes = sum(sum(v) for v in files.values())
            #body += [tablerow(barcode,
                              #TextInput("", name=f"sample_{index}"),
                              #", ".join(sorted(numbers)),
                              #"{} MB".format(bytes  // 1024 // 1024),
                              #"",
                              #"",
                              #"")]
            
            
            
    #if other_files:
        #body += [tablerow("",
                          #"",
                          #"other x {}".format(len(other_files)),
                          #"{} MB".format(sum(other_files)  // 1024 // 1024))]

    #table = {"head": ("Barcode", "Name", "Files", "Size", "Project", "Status", "Date"),
             #"body": body}
    #buttons={"submit": ("Upload", url_for(".new_run")),
             #"back": ("Cancel", url_back())}
    #body = render_template("uploadtable.html", form=form, buttons=buttons, table=table)
    #return jsonify({"title": run_info["Experiment Name"], "body": body})



@app.route("/upload", methods=["GET", "POST"])
@login_required("Bioinformatics.")
def upload():
    
    resumableTotalChunks = request.form.get('resumableTotalChunks', type=int)
    resumableChunkNumber = request.form.get('resumableChunkNumber', default=1, type=int)
    resumableFilename = request.form.get('resumableFilename', default='error', type=str)
    resumableIdentfier = request.form.get('resumableIdentifier', default='error', type=str)
    
    
    
    
    #if method == "POST":
        
        ## get the chunk data
        #chunk_data = request.files['file']

        ## make our temp directory
        #temp_dir = os.path.join(temp_base, resumableIdentfier)
        #if not os.path.isdir(temp_dir):
            #os.makedirs(temp_dir, 0777)

        ## save the chunk data
        #chunk_name = get_chunk_name(resumableFilename, resumableChunkNumber)
        #chunk_file = os.path.join(temp_dir, chunk_name)
        #chunk_data.save(chunk_file)
        #app.logger.debug('Saved chunk: %s', chunk_file)

        ## check if the upload is complete
        #chunk_paths = [os.path.join(temp_dir, get_chunk_name(resumableFilename, x)) for x in range(1, resumableTotalChunks+1)]
        #upload_complete = all([os.path.exists(p) for p in chunk_paths])

        ## combine all the chunks to create the final file
        #if upload_complete:
            #target_file_name = os.path.join(temp_base, resumableFilename)
            #with open(target_file_name, "ab") as target_file:
                #for p in chunk_paths:
                    #stored_chunk_file_name = p
                    #stored_chunk_file = open(stored_chunk_file_name, 'rb')
                    #target_file.write(stored_chunk_file.read())
                    #stored_chunk_file.close()
                    #os.unlink(stored_chunk_file_name)
            #target_file.close()
            #os.rmdir(temp_dir)
            #app.logger.debug('File saved to: %s', target_file_name)

        #return 'OK'
    
    
    
    #form = SelectSamplesForm(request.form, **{"data-href": url_for(".worksheet")})
    #if request.method == "POST":
        #pass













































@app.route("/runs/<string:bsrun_bsid>/samples", methods=["GET", "POST"])
@login_required("Bioinformatics.")
def samples(bsrun_bsid):
    with engine.begin() as conn:
        sql = select([bsaccounts.c.token,
                      bsruns.c.id.label("bsrun_id"),
                      bsruns.c.attr.label("bsrun_attr"),
                      bssamples.c.id,
                      bssamples.c.attr,
                      bssamples.c.status,
                      bssamples.c.upload_datetime,
                      projects.c.name.label("project")]). \
                select_from(join(bsaccounts, users_bsaccounts, bsaccounts.c.id == users_bsaccounts.c.bsaccount_id). \
                            join(bsruns, bsruns.c.bsaccount_id == bsaccounts.c.id). \
                            outerjoin(bssamples, bssamples.c.bsrun_id == bsruns.c.id). \
                            outerjoin(projects, projects.c.id == bssamples.c.project_id)). \
                where(and_(bsruns.c.bsid == bsrun_bsid, 
                           users_bsaccounts.c.user_id == session["id"])). \
                order_by(bssamples.c.attr["DateCreated"].desc())
        old_rows = list(dict(row) for row in conn.execute(sql)) or abort(BadRequest)
        row = old_rows[0]
        bsrun_id = row["bsrun_id"]
        experimentname = row["bsrun_attr"]["ExperimentName"]
        last_created = row["attr"]["DateCreated"] if row["attr"] is not None else None
        bs = basespace.Session(row["token"])
        if row["id"] is None:
            old_rows = []
        else:
            appsession_id = row["attr"]["AppSession"]["Id"]
        
        new_rows = []
        if request.method != "POST":
            for attr in bs.search("samples", query='(experimentname="{}")'.format(experimentname), SortBy="DateCreated", SortDir="Desc"):
                #pdb.set_trace()
                if last_created and attr["DateCreated"] <= last_created:
                    break
                print(attr["Name"])
                # I know we searched on it but elastic search gives us inexact matches
                if attr["ExperimentName"] == experimentname:
                    attr = bs.get_single("samples/{}".format(attr["Id"]))
                    new_rows += [{"bsid": int(attr["Id"]), "bsrun_id": bsrun_id, "attr": attr}]
            
            if new_rows:
                appsession_id = new_rows[0]["attr"]["AppSession"]["Id"]
                with conn.begin() as trans:
                    conn.execute(bssamples.insert(), new_rows)

        form = SelectSamplesForm(request.form)
        invalid_bsids = set()
        body = []
        for row in chain(new_rows, old_rows):
            attr = row["attr"]
            utcdate = basespace.strptime(attr["DateCreated"])
            obsolete = attr["AppSession"]["Id"] != appsession_id
            choice = [int(attr["Id"]), ""]
            if obsolete or row.get("status", "") != "":
                choice += ["disabled"]
                invalid_bsids.add(choice[0])
            checkbox = form.bssample_bsid.checkbox(choice)
            body += [tablerow(attr["Name"],
                            attr["NumReadsPF"],
                            attr["AppSession"]["Application"]["Name"],
                            Local(utcdate),
                            row.get("project", "") or "",
                            row.get("status", ""),
                            Local(row.get("upload_datetime", None)),
                            deleted=obsolete,
                            checkbox=checkbox)]
        
        if request.method == "POST" and form.validate():
            selected_bsids = set(form.bssample_bsid.data) - invalid_bsids
            sql = bssamples.update(). \
                    where(and_(bssamples.c.bsid.in_(selected_bsids), bssamples.c.status == "")). \
                    values(project_id=session["project_id"], status="Queued")
            conn.execute(sql)
            
            # Update uploaded obsolete files.
            # Wake daemon.
                
            print(selected_bsids)
            return redirect(url_for(".samples", bsrun_bsid=bsrun_bsid))
    
    table = {"head": ("Sample", "Reads PF", "Application", "Date", "Project", "Status", "Date"),
             "body": body}
    modal = {"submit": ("Import", url_for(".samples", bsrun_bsid=bsrun_bsid)), 
             "back": ("Back", url_back()),
             "text": "Are you sure you want to upload these samples?"}
    buttons = {"submit": ("Import", "#"), "back": ("Cancel", url_back())}
    return render_page("formtable.html",
                       form=form,
                       title=experimentname,
                       table=table,
                       buttons=buttons,
                       modal=modal)



        
 
