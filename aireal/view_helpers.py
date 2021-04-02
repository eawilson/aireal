import pdb
from html import escape

from sqlalchemy import (select,
                        join,
                        or_,
                        and_)
from jinja2 import Markup

from .models import (logs,
                     users)
from .utils import (engine,
                    tablerow,
                    initial_surname)
from .wrappers import Local
from .i18n import _



def log_table(tablename, row_id):
    with engine.connect() as conn:
        sql = select([users.c.forename,
                      users.c.surname,
                      logs.c.action,
                      logs.c.details,
                      logs.c.datetime]). \
                select_from(join(logs, users,
                                 logs.c.user_id == users.c.id)). \
                where(and_(logs.c.tablename == tablename,
                           logs.c.row_id == row_id)). \
                order_by(logs.c.datetime, logs.c.id)
            
        head = (_("Action"), _("Details"), _("User"), _("Date"))
        body = []
        for row in conn.execute(sql):
            name = initial_surname(row[users.c.forename], row[users.c.surname])
            details = escape(row[logs.c.details]).replace("\t", "<br>")
            body += [tablerow(_(row[logs.c.action]),
                              Markup(details),
                              name,
                              Local(row[logs.c.datetime]))]
    return {"head": head, "body": body}
