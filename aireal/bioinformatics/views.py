import os, pdb

from flask import redirect, url_for, current_app, request
from werkzeug import exceptions


from ..flask import Blueprint, abort, render_page, render_template
from ..utils import tablerow
from ..i18n import _
from ..aws import list_objects, cloudfront_sign_url
from .basespace import app as basespace


def bioinformatics_navbar():
    return [{"text": _("Runs"),
             "href":  url_for("Bioinformatics.runs")},
            {"text": _("Import"),
             "href":  url_for("Bioinformatics.import_menu"),
             "dropdown": True}]



app = Blueprint("Bioinformatics", __name__, navbar=bioinformatics_navbar)
app.register_blueprint(basespace)



@app.route("/importmenu")
def import_menu():
    menu = [{"text": _("BaseSpace"), "href": url_for(".Basespace.accounts")},
            #{"text": _("Nanopre"), "href": url_for("nanopore.runs")}
           ]
    return render_template("dropdown.html", items=menu)



@app.route("/runs")
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
             "actions": actions,
             "title": run}
    return render_page("table.html", table=table, buttons={"back": (_("Back"), url_for(".runs"))})



@app.route("/files/<path:run_sample>")
def files(run_sample):
    prefix = f"projects/EBVL/analyses4/{run_sample}/"
    
    body = []
    for key, val in sorted(list_objects("omdc-data", prefix).items()):
        filename = key[len(prefix):]
        viewable = filename.endswith(".bam")
        body += [tablerow(filename,
                          "{:.2f}".format(val["Size"] / 1000 / 1000),
                          _class="igv-viewable" if viewable else "",
                          id=f"{run_sample}/{filename}")]
    
    actions = ({"name": _("Download"), "href": url_for(".downloads", run_sample_filename="0")},
               {"name": _("View with IGV"), "href": url_for(".igv_view", run_sample_filename="0"), "class": "igv-viewable"})
    table = {"head": (_("File"), _("Size (MB)")),
             "body": body,
             "actions": actions,
             "title": run_sample.replace("/", " - ")}
    run = run_sample.split("/")[0]
    return render_page("table.html", table=table, buttons={"back": (_("Back"), url_for(".samples", run=run))})



@app.route("/downloads/<path:run_sample_filename>")
def downloads(run_sample_filename):
    config = current_app.config
    url = f'https://{config.get("BIOINFORMATICS_DOWNLOAD_DOMAIN")}/{run_sample_filename}'
    signed_url = cloudfront_sign_url(url, config.get("BIOINFORMATICS_PRIVATE_KEY"))
    return redirect(signed_url)



@app.route("/igv/<path:run_sample_filename>")
def igv_view(run_sample_filename):
    download_domain = current_app.config.get("BIOINFORMATICS_DOWNLOAD_DOMAIN")
    private_key = current_app.config.get("BIOINFORMATICS_PRIVATE_KEY")
    name = run_sample_filename.split("/")[1] if "/" in run_sample_filename else "Sample"
    
    base_url = os.path.splitext(f'https://{download_domain}/{run_sample_filename}')[0]
    bam_url = cloudfront_sign_url(base_url+".bam", private_key)
    bambai_url = cloudfront_sign_url(base_url+".bam.bai", private_key)
    #vcf_url = cloudfront_sign_url(base_url+".vcf", private_key)
    #vcftbi_url = cloudfront_sign_url(base_url+".vcf.tbi", private_key)
    back_url = url_for(".files", run_sample="/".join(run_sample_filename.split("/")[:-1]))
    return render_template("igv.html", name=name, bam_url=bam_url, bambai_url=bambai_url, back_url=request.referrer)# vcf_url=vcf_url, vcftbi_url=vcftbi_url)
















