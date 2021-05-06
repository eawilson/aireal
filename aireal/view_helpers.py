import pdb

from jinja2 import Markup

from .utils import tablerow
from .wrappers import Local
from .i18n import _



def pretty(keyval):
    k, v = keyval
    k = _(k)
    if isinstance(v, list):
        return "{}: {}".format(k, ", ".join(_(i) for i in sorted(v)))
    else:
        v = _(v)
        if "(" in k:
            k, units = k.split("(", maxsplit=1)
            v = "{}{}".format(v, units.split(")")[0].strip())
        return f"{k} = {v}"



def log_table(cur, table, row_id):
    sql = """SELECT users.name, editrecord.action, editrecord.details, editrecord.edit_datetime
             FROM editrecord
             LEFT OUTER JOIN users ON editrecord.users_id = users.id
             WHERE editrecord.tablename = %(table)s AND editrecord.row_id = %(row_id)s
             ORDER BY editrecord.edit_datetime, editrecord.id;"""
    cur.execute(sql, {"table": table, "row_id": row_id})
    
    head = (_("Action"), _("Details"), _("User"), _("Date"))
    body = []
    for name, action, details, dtime in cur:
        body.append(tablerow(_(action),
                             Markup("<br>".join(pretty(item) for item in sorted(details.items()))),
                             name,
                             Local(dtime)))
    return {"head": head, "body": body}
