import pdb
from datetime import datetime, timezone
import time
from functools import wraps
from collections import defaultdict
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse, urlunparse, parse_qs, unquote_plus, urlencode
import shlex
import subprocess
import numbers

from dateutil import parser
import pytz

from flask import session, request, url_for, current_app, redirect
from flask.sessions import SecureCookieSessionInterface
import flask
from werkzeug import exceptions

from itsdangerous.exc import BadSignature
from itsdangerous import URLSafeTimedSerializer

from psycopg2 import IntegrityError
from psycopg2.extensions import ISOLATION_LEVEL_READ_UNCOMMITTED, ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_REPEATABLE_READ, ISOLATION_LEVEL_SERIALIZABLE

from .i18n import _
from .forms import ActionForm


__all__ = ["utcnow",
           "build_url"
           "local_subnet",
           "sign_token",
           "tablerow",
           "render_template",
           "render_page",
           "sign_cookie",
           "unique_key",
           "iso8601_to_utc",
           "demonise",
           "audit_log",
           "keyvals_from_form"]



def abort(exc):
    raise exc



def dict_from_select(cur, sql, params={}):
    cur.execute(sql, params)
    row = cur.fetchone() or abort(exceptions.BadRequest)
    return {col.name: val for col, val in zip(cur.description, row)}



class Transaction(object):
    def __init__(self):
        self._conn = current_app.extensions["connction_pool"].getconn()
        self._conn.set_session(isolation_level=ISOLATION_LEVEL_SERIALIZABLE,
                               readonly=False)
        
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self._conn.commit()
        self.close()
    
    def close(self):
        self._conn.rollback()
        current_app.extensions["connction_pool"].putconn(self._conn)
    
    def __getattr__(self, attr):
        return getattr(self._conn, attr)



class Cursor(object):
    def __init__(self):
        self._conn = current_app.extensions["connction_pool"].getconn()
        self._conn.set_session(isolation_level=ISOLATION_LEVEL_REPEATABLE_READ,
                               readonly=True)
        self._cur = self._conn.cursor()
        
    def __enter__(self):
        return self._cur

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self._conn.commit()
        self.close()
    
    def close(self):
        self._cur.close()
        self._conn.rollback()
        current_app.extensions["connction_pool"].putconn(self._conn)
    
    def __getattr__(self, attr):
        return getattr(self._cur, attr)



def iso8601_to_utc(dt_string):
    """ Convert a string in iso8601 format to a datetime with the timezone set
        to UTC.
    """
    dt = parser.parse(dt_string)
    return dt.astimezone(pytz.utc)



def local_subnet(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        local = current_app.config.get("LOCAL_SUBNET")
        if local and ip_address(request.remote_addr) in ip_network(local):
            return function(*args, **kwargs)
        raise exceptions.Forbidden
    return wrapper



def tablerow(*args, **kwargs):
    return (args, kwargs)



def unique_key(e):
    return str(e).split("\nDETAIL:  Key (")[1].split(")")[0]



def demonise(cmd):
    """ Runs cmd in the background.
    
    Runs shell command in the background, detached from the controlling
    tty and unaffected by signals directed at the parent. Cmd must have
    an alternate method of communication eg filesystem, database or
    network connection.
    
    Args:
        cmd:
            Shell command as a list of tokens.
    
    Returns:
        None.
    """
    shell_cmd = " ".join(shlex.quote(arg) for arg in cmd)
    # Possibly cleaner to use subprocess redirection but I am certain this does what I want
    subprocess.run(f"setsid {shell_cmd} >/dev/null 2>&1 </dev/null &", shell=True)



def audit_log(cur, action, target, name, keyvals, format_string, *args, users_id=None, ip_address=None):
    """ Log an action into audittrail.
    
    Args:
        cur:
            Postgresql cursor object to perform insert with.
        action:
            Action performed, verb, past tense eg Created, Edited, Deleted, Restored, Imported.
        target:
            Affected object type, noun, eg User, Location, Sample.
        name:
            Identifies affected object at the time the action occured.
        keyvals:
            Dict containing key/value pairs of changes made to object.
        format_string:
            Python format string with named parameters as per contents of keyvals. Empty string if keyvals are just key/value pairs.
        *args:
            Variable number of tuples of (tablename, row_id) indicating the database rows affected by this action.
        users_id:
            id of user performing action. Only needed if action is not performed within request context.
        ip_address:
            ip address of user performing action. Only needed if action is not performed within request context.
    
    Returns:
        None.
    """
    sql = """INSERT INTO audittrail (action, target, name, keyvals, format_string, users_id, ip_address)
             VALUES (%(action)s, %(target)s, %(name)s, %(keyvals)s, %(format_string)s, %(users_id)s, %(ip_address)s)
             RETURNING id;"""
    values = {"action": action,
              "target": target,
              "name": name,
              "keyvals": keyvals,
              "format_string": format_string,
              "users_id": users_id or session["id"],
              "ip_address": ip_address or request.remote_addr}
    
    cur.execute(sql, values)
    audittrail_id = cur.fetchone()[0]
    
    sql = """INSERT INTO auditlink (audittrail_id, tablename, row_id)
             VALUES (%(audittrail_id)s, %(tablename)s, %(row_id)s);""" 
    for tablename, row_id in args:
        cur.execute(sql, {"audittrail_id": audittrail_id,
                          "tablename": tablename,
                          "row_id": row_id})



def keyvals_from_form(form, old={}):
    difference = {}
    for key, field in form.items():
        val = field.data
        if key not in old or val != old[key]:
            if isinstance(val, bool):
                val = str(val)
            elif isinstance(val, numbers.Number):
                val = {"type": "number", "val": val}
                if hasattr(field, "units"):
                    val["units"] = field.units
            difference[field._label] = val
    return difference



def right_click_action(tablename, row_id, target, name):
    form = ActionForm(request.form)
    if request.method == "POST" and form.validate():
        with Transaction() as trans:
            with trans.cursor() as cur:
                form_action = form.action.data
                if form_action == _("Delete"):
                    sql = f"UPDATE {tablename} SET deleted = true WHERE deleted = false AND id = %(row_id)s;"
                    action = "Deleted"
                elif form_action == _("Restore"):
                    sql = f"UPDATE {tablename} SET deleted = false WHERE deleted = true AND id = %(row_id)s;"
                    action = "Restored"
                else:
                    return True
                
                cur.execute(sql, {"row_id": row_id})
                if cur.rowcount:
                    audit_log(cur, action, target, name, {}, "", (tablename, row_id))
                return True
    return False



