import pdb
from datetime import datetime, timezone
import time
from functools import wraps
from collections import defaultdict
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse, parse_qs, unquote_plus

from dateutil import parser
import pytz

from flask import session, request, url_for, current_app, redirect
from flask.sessions import SecureCookieSessionInterface
import flask
from werkzeug import exceptions

from sqlalchemy.exc import IntegrityError

from .i18n import _
from .forms import ActionForm

__all__ = ["Blueprint",
           "utcnow",
           "local_subnet",
           "login_required",
           "engine",
           "abort",
           "tablerow",
           "initial_surname",
           "surname_forename",
           "render_template",
           "render_page",
           "navbar",
           "sign_cookie",
           "unique_violation_or_reraise",
           "iso8601_to_utc"]



_navbars = {}
valid_groups = set()



def original_referrer():
    referrer = request.referrer
    qs = parse_qs(urlparse(referrer)[4])
    try:
        return unquote_plus(qs["referrer"][0])
    except KeyError:
        return referrer



def iso8601_to_utc(dt_string):
    """ Convert a string in iso8601 format to a datetime with the timezone set
        to UTC.
    """
    dt = parser.isoparse(dt_string)
    return dt.astimezone(pytz.utc)



def render_template(name, style=None, **kwargs):
    """ Adds correct prefix to template supplied to flask.render_template.
        Enables swapping of css styles on the fly.
    """
    if style is None:
        style = current_app.config.get("STYLE", None)
    if style is not None:
        name = f"{style}/{name}"
    return flask.render_template(name, **kwargs)



def render_page(name, active=None, **context):
    """ Wrapper around flask.render_template to add appropriate navbar context
        before calling flask.render_template itself. To be used instead of 
        flask.render_template when rendering a full page. Not to be used for
        ajax calls for dropdowns etc.
    """
    config = current_app.config
    application = config.get("NAME", "")
    if "id" not in session:
        navbar = {"app": application}
    else:
        group = session.get("group", "")

        right = [{"text": session.get("project", ""),
                  "href": url_for("auth.project_menu"),
                  "dropdown": True},
                 {"text": session.get("site", ""),
                  "href": url_for("auth.site_menu"),
                  "dropdown": True},
                 {"text": "",
                  "href": url_for("auth.logout_menu"),
                  "dropdown": True}]
        navbar = {"app": application,
                  "name": group,
                  "active": active,
                  "left": _navbars.get(group, lambda:())(),
                  "right": right}
    return render_template(name, navbar=navbar, action_form=ActionForm(id="action-form"), **context)



def utcnow():
    """ Returns current datetime with timezone set to UTC. Assumes that the
        server is running on UTC time which is the only sensible configuration
        anyway.
    """
    return datetime.now(tz=timezone.utc)



def navbar(group):
    """ Decorator to register a new navbar menu.
    """
    def decorator(function):
        _navbars[group] = function
        return function
    return decorator



def local_subnet(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        local = current_app.config.get("LOCAL_SUBNET")
        if local and ip_address(request.remote_addr) in ip_network(local):
            return function(*args, **kwargs)
        raise exceptions.Forbidden
    return wrapper



def signature_required():
    pass



def login_required(*authorised_groups):
    """Decorator to protect every view function (except login, set_password,
        etc that are called before user is logged in). Group names are in the
        format Section.Role. If no groups are provided then this endpoint can
        be viewed and written to by anyone although the actual records they
        can access can still be limited by filtering database queries on their
        current Section and/or Role within the view. If a Role is provided
        then the endpoint can be viewed by anyone but only written to by a
        user currently holding that Role. If a Section is provided then that
        endpoint can only be viewed by users currently holding that Section.
        Also provides navigation support by storing the url for use by the
        url_back function.
        
        All view functions MUST be protected with this decorator.
        
        *** WARNING Writable endpoints that have no groups specified MUST 
        protect against writes by users with the view function itself by 
        database filtering of choices supplied to forms as even though 
        these views will never be directly accessable from the navbar the
        url could be hand entered by a malicious user. ***

    Args:
        groups (list of str): Groups allowed to make a request to this 
            endpoint.
        ajax_or_new_tab (bool): If True then this request is outside of
            normal navigation and should not be added to the navigation 
            stack.
        
    Returns:
        None
        
    Raises:
        Forbidden if users group does not match the required permissions for
        this endpoint.
        Conflict if a database IntegrityError occurs during datbase access.
        All other exceptions are passed through unmodified.
        
     """
    def login_decorator(function):
        valid_groups.update(authorised_groups)

        @wraps(function)
        def wrapper(*args, **kwargs):
            if "id" not in session:
                return redirect(url_for("auth.login"))
            
            if authorised_groups and session["group"] not in authorised_groups:
                if request.method == "POST":
                    abort(exceptions.Forbidden)
                else:
                    return redirect(url_for("auth.root"))
            
            try:
                return function(*args, **kwargs)
            except IntegrityError:
                abort(exceptions.Conflict)
        return wrapper
    return login_decorator
    


class _ProxyEngine(object):
    def __getattr__(self, name):
        return getattr(current_app.extensions["engine"], name)
engine = _ProxyEngine()

    
    
def abort(exc):
    raise exc



def tablerow(*args, **kwargs):
    return (args, kwargs)
    
    

def initial_surname(forename, surname):
    if forename:
        return "{}.{}".format(forename[0], surname)
    return surname or ""
    


def surname_forename(surname, forename):
    if forename:
        return "{}, {}".format(surname, forename)
    return surname or ""



def sign_cookie(data):
    session_serializer = SecureCookieSessionInterface() \
                         .get_signing_serializer(current_app)
    return session_serializer.dumps(dict(session))



def unique_violation_or_reraise(e):
    db_url = current_app.config["DB_URL"]
    if db_url.startswith("postgresql"):
        msg = repr(e.orig)
        if msg.startswith("UniqueViolation"):
            return msg.split("DETAIL:  Key (")[1].split(")")[0]
        
    elif db_url.startswith("sqlite://"):
        # Need to confirm this works.
        msg = e._message()
        if " UNIQUE constraint failed: " in msg:
            return msg.split(" UNIQUE constraint failed: ")[1].split(".")[1]

    raise e
