import pdb
from datetime import datetime, timezone
import time
from functools import wraps
from collections import defaultdict
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse, urlunparse, parse_qs, unquote_plus, urlencode
import shlex
import subprocess

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
           "abort",
           "tablerow",
           "render_template",
           "render_page",
           "sign_cookie",
           "unique_key",
           "iso8601_to_utc",
           "demonise"]



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
        self._conn.set_session(isolation_level=ISOLATION_LEVEL_SERIALIZABLE,
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
    """
    shell_cmd = " ".join(shlex.quote(arg) for arg in cmd)
    # Possibly cleaner to use subprocess redirection but I am certain this does what I want
    subprocess.run(f"setsid {shell_cmd} >/dev/null 2>&1 </dev/null &", shell=True)


