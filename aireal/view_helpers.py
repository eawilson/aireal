import pdb
from html import escape

from jinja2 import Markup

from .utils import tablerow
from .wrappers import Local
from .i18n import _



def log_table(cur, table, row_id):
    sql = """SELECT users.name, logs.action, logs.details, logs.datetime
             FROM logs
             INNER JOIN users ON logs.user_id = users.id
             WHERE logs.tablename = %(table)s AND logs.row_id = %(row_id)s
             ORDER BY logs.datetime, logs.id;"""
    cur.execute(sql, {"table": table, "row_id": row_id})
    
    head = (_("Action"), _("Details"), _("User"), _("Date"))
    body = []
    for name, action, details, dtime in cur:
        body.append(tablerow(_(action),
                             Markup(escape(details).replace("\t", "<br>")),
                             name,
                             Local(dtime)))
    return {"head": head, "body": body}
