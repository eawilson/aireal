import pdb
from html import escape

from jinja2 import Markup
from flask import session

from .flask import render_page
from .utils import Cursor
from .i18n import _, Date, format_decimal, format_unit, format_percent



def format_val(val):
    if isinstance(val, list):
        # Probably reasonable to assume this will always be a list of items rather than numbers
        val = ", ".join(sorted(_(v) for v in val))
    if isinstance(val, dict):
        if val.get("units"):
            val = format_unit(val["val"], val["units"], locale=session["locale"])
        else:
            val = format_decimal(val["val"], locale=session["locale"])
    else:
        val = _(val)
    return val



def audit_view(tablename, row_id, url_back, title=""):
    sql = """SELECT audittrail.action, audittrail.name, audittrail.keyvals, audittrail.format_string, audittrail.datetime, users.name
             FROM audittrail
             JOIN users ON audittrail.users_id = users.id
             JOIN auditlink ON auditlink.audittrail_id = audittrail.id
             WHERE auditlink.tablename = %(tablename)s AND auditlink.row_id = %(row_id)s
             ORDER BY audittrail.datetime;"""
    body = []
    with Cursor() as cur:
        cur.execute(sql, {"tablename": tablename, "row_id": row_id})
        for action, name, keyvals, format_string, when, user in cur:
            if format_string:
                translated = {k: format_val(v) for k, v in keyvals.items()}
                details = format_string.format(**translated)
            else:
                translated = {_(k): format_val(v) for k, v in keyvals.items()}
                details = Markup("<br>".join(escape(" = ".join(kv)) for kv in sorted(translated.items())))
            body.append(((name,
                          _(action),
                          details,
                          user,
                          Date(when)), {}))
    table = {"head": (_("Name"), _("Action"), _("Details"), _("User"), _("Date")), 
             "body": body}
    buttons={"back": (_("Back"), url_back)}
    return render_page("table.html", table=table, buttons=buttons, title=title)
