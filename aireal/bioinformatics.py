from sqlalchemy import select, join, or_, outerjoin, and_
from sqlalchemy.exc import IntegrityError

from flask import redirect, url_for, Blueprint, current_app
from werkzeug import exceptions


from .utils import engine, login_required, navbar, abort, tablerow, render_page, render_template
from .i18n import _
from .aws import list_objects, cloudfront_sign_url



app = Blueprint("bioinformatics", __name__)


@navbar("Bioinformatics")
def admin_navbar():
    return [{"text": _("Runs"),
             "href":  url_for("bioinformatics.runs")},
            {"text": _("Import"),
             "href":  url_for("bioinformatics.import_menu"),
             "dropdown": True}]



@app.route("/importmenu")
@login_required("Bioinformatics")
def import_menu():
    menu = [{"text": _("BaseSpace"), "href": url_for("basespace.accounts")},
            {"text": _("Nanopre"), "href": url_for("nanopore.runs")}]
    return render_template("dropdown.html", items=menu)



@app.route("/runs")
@login_required("Bioinformatics")
def runs():
    prefix = "projects/EBVL/analyses4/"
    runs = set()
    for key in list_objects("omdc-data", prefix):
        runs.add(key[len(prefix):].split("/")[0])

    body = []
    for run in sorted(runs):
        body += [tablerow(run, id=run)]
    
    actions = ({"name": _("View"), "href": url_for(".samples", run="0")},)
    table = {"head": (_("Run"),),
             "body": body,
             "actions": actions}
    return render_page("table.html", table=table, buttons=())



@app.route("/samples/<string:run>")
@login_required("Bioinformatics")
def samples(run):
    prefix = f"projects/EBVL/analyses4/{run}/"
    samples = set()
    for key in list_objects("omdc-data", prefix):
        samples.add(key[len(prefix):].split("/")[0])

    body = []
    for sample in sorted(samples):
        body += [tablerow(sample, id=f"{run}/{sample}")]

    actions = ({"name": _("View"), "href": url_for(".files", run_sample="0")},)
    table = {"head": (_("Sample"),),
             "body": body,
             "actions": actions}
    return render_page("table.html", table=table, title=run, buttons={"back": (_("Back"), url_for(".runs"))})



@app.route("/files/<path:run_sample>")
@login_required("Bioinformatics")
def files(run_sample):
    prefix = f"projects/EBVL/analyses4/{run_sample}/"
    
    body = []
    for key, val in sorted(list_objects("omdc-data", prefix).items()):
        filename = key[len(prefix):]
        body += [tablerow(filename,
                          "{:.2f}".format(val["Size"] / 1000 / 1000),
                          id=f"{run_sample}/{filename}")]
    
    actions = ({"name": _("Download"), "href": url_for(".downloads", run_sample_filename="0")},)
    table = {"head": (_("File"), _("Size (MB)")),
             "body": body,
             "actions": actions}
    run = run_sample.split("/")[0]
    return render_page("table.html", table=table, title=run_sample.replace("/", " - "), buttons={"back": (_("Back"), url_for(".samples", run=run))})



@app.route("/downloads/<path:run_sample_filename>")
@login_required("Bioinformatics")
def downloads(run_sample_filename):
    config = current_app.config
    url = f'https://{config.get("BIOINFORMATICS_DOWNLOAD_DOMAIN")}/{run_sample_filename}'
    signed_url = cloudfront_sign_url(url, config.get("BIOINFORMATICS_PRIVATE_KEY"))
    print(signed_url)
    return redirect(signed_url)


