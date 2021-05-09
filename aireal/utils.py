import pdb
from datetime import datetime, timezone
import time
from functools import wraps
from collections import defaultdict
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse, urlunparse, parse_qs, unquote_plus, urlencode

from dateutil import parser
import pytz

from flask import session, request, url_for, current_app, redirect
from flask.sessions import SecureCookieSessionInterface
import flask
from werkzeug import exceptions

from itsdangerous.exc import BadSignature
from itsdangerous import URLSafeTimedSerializer

from psycopg2 import IntegrityError

from .i18n import _
from .forms import ActionForm

__all__ = ["Blueprint",
           "utcnow",
           "build_url"
           "local_subnet",
           "sign_token",
           "abort",
           "tablerow",
           "render_template",
           "render_page",
           "navbar",
           "sign_cookie",
           "unique_key",
           "iso8601_to_utc"]



_navbars = {}
    #import inspect
    #for frame in inspect.stack():
        #print(frame[0].f_locals.get("allowed", "."))



def sign_token(data, salt):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=salt)
    return serializer.dumps(data)



def build_url(*path, **params):
    url = "/".join(path)
    if params:
        url_parts = list(urlparse(url))
        url_parts[4] = urlencode(params)
        url = urlunparse(url_parts)
    return url



def absolute_url_for(*args, **kwargs):
    return request.host_url[:-1] + url_for(*args, **kwargs)



class _ReturnEndpoint(object):
    # Match call signiture used for route registration to extract
    # endpoints from the lambda functions that they are stored in.
    @staticmethod
    def add_url_rule(rule, endpoint, view_func, **options):
        return endpoint



class Blueprint(flask.Blueprint):
    valid_roles = ()
    
    def __init__(self, name, import_name, *roles, **kwargs):
        """ Wrapper around Bluprint __init__ method with the 
            additional positional argument *roles. This lists
            all the roles that are allowed to access the routes
            of this Blueprint. If no roles are provided then all
            logged in users can access the route.
        """
        for role in roles:
            if role not in self.valid_roles:
                type(self).valid_roles += (role,)
        
        self.roles = roles
        return super().__init__(name, import_name, **kwargs)
        
        
        
    def route(self, rule, *roles, **options):
        """ Wrapper arounf Blueprint route with the additional positional
            argument *roles. This overides *roles in the __init__ method
            and lists all the roles allowed to access this route. Returns
            the wrapped view function that performs the following action:
            
            1) Check that the user is logged in.
            
            2) Check that the user has assumed the correct role to access
               this view. WARNING If a view is decorated with multiple routes
               then the roles from the innermost decorator will be used for
               all routes.
            
            3) Catch IntegrityErrors caused by simultaneous attemps to
               write the same rows in the databse.
        """
        
        def decorator(function):
            """ Check if the function has already been registered and therefore
                already wrapped. If so then just return it unmodified. WARNING
                This depends on private internals of the Blueprint which could
                potentialy change in future versions.
            """
            
            endpoint = options.pop("endpoint", None) or function.__name__
            already_wrapped = False
            for registration_function in self.deferred_functions:
                try:
                    if registration_function(_ReturnEndpoint) == endpoint:
                        already_wrapped = True
                        break
                except Exception:
                    pass
            
            if already_wrapped:
                wrapper = function
            
            else:
                for role in roles:
                    if role not in self.valid_roles:
                        type(self).valid_roles += (role,)
                
                allowed = roles or self.roles
                
                @wraps(function)
                def wrapper(*args, **kwargs):
                    if "id" not in session:
                        return redirect(url_for("auth.login"))
                    
                    if allowed and session["role"] not in allowed:
                        if request.method == "POST":
                            abort(exceptions.Forbidden)
                        else:
                            return redirect(url_for("auth.root"))
                    
                    try:
                        return function(*args, **kwargs)
                    except IntegrityError:
                        abort(exceptions.Conflict)
        
            self.add_url_rule(rule, endpoint, wrapper, **options)
            return wrapper
        return decorator
    
    
    def signed_route(self, rule, max_age, salt=None, **options):
        """ Wrapper arounf Blueprint route with the additional keyword
            argument max_age. This is the maximum allowed age of the signature
            in seconds. Access to the route is alowed if the user is logged in
            ("id" in session) or has a valid signiture that is not too old. If 
            this fails then either:
            
            Redirect to root url if accessed by an interactive user as determined
            by the presence of a User-agent header.
            
            or
            
            Return a json response detailing the error if accessed programmatically
            as determined by the absence of a User-agent header.
            
        """
        
        def decorator(function):
            """ Check if the function has already been registered and therefore
                already wrapped. If so then just return it unmodified. WARNING
                This depends on private internals of the Blueprint which could
                potentialy change in future versions.
            """
            
            endpoint = options.pop("endpoint", None) or function.__name__
            already_wrapped = False
            for registration_function in self.deferred_functions:
                try:
                    if registration_function(_ReturnEndpoint) == endpoint:
                        already_wrapped = True
                        break
                except Exception:
                    pass
            
            if already_wrapped:
                wrapper = function
            
            else:
                @wraps(function)
                def wrapper(*args, **kwargs):
                    token = _validate_token(request.args.get("token"),
                                            max_age=max_age,
                                            salt=salt or endpoint)
                    if token or "id" in session:
                        return function(token, *args, **kwargs)
                    else:
                        if "User-agent" in request.headers:
                            return redirect(url_for("auth.root"))
                        else:
                            return {}, 401
            
            self.add_url_rule(rule, endpoint, wrapper, **options)
            return wrapper
        return decorator
    
    
    def insecure_route(self, *args, **kwargs):
        return super().route(*args, **kwargs)



def _validate_token(token, max_age, salt):
    if token:
        secret = current_app.config["SECRET_KEY"]
        s = URLSafeTimedSerializer(secret, salt=salt)
        try:
            return s.loads(token, max_age=max_age)
        except BadSignature:
            pass
    return {}



def dict_from_select(cur, sql, params={}):
    cur.execute(sql, params)
    row = cur.fetchone() or abort(exceptions.BadRequest)
    return {col.name: val for col, val in zip(cur.description, row)}



class Transaction(object):
    def __init__(self):
        self._conn = current_app.extensions["connction_pool"].getconn()
        
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



def original_referrer():
    referrer = request.referrer
    qs = parse_qs(urlparse(referrer)[4])
    try:
        return unquote_plus(qs["referrer"][0])
    except KeyError:
        return referrer


def original_referrer():
    qs = parse_qs(urlparse(request.url)[4])
    try:
        return unquote_plus(qs["referrer"][0])
    except KeyError:
        return request.referrer


def iso8601_to_utc(dt_string):
    """ Convert a string in iso8601 format to a datetime with the timezone set
        to UTC.
    """
    dt = parser.isoparse(dt_string)
    return dt.astimezone(pytz.utc)



def render_template(template_name, style=None, **kwargs):
    """ Adds correct prefix to template supplied to flask.render_template.
        Enables swapping of css styles on the fly.
    """
    if style is None:
        style = current_app.config.get("STYLE", None)
    if style is not None:
        template_name = f"{style}/{template_name}"
    return flask.render_template(template_name, **kwargs)



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
        role = session.get("role", "")

        right = [{"text": session.get("project", ""),
                  "href": url_for("auth.project_menu"),
                  "dropdown": True},
                 {"text": "",
                  "href": url_for("auth.logout_menu"),
                  "dropdown": True}]
        navbar = {"app": application,
                  "name": _(role),
                  "active": active,
                  "left": _navbars.get(role, lambda:())(),
                  "right": right}
    return render_template(name, navbar=navbar, action_form=ActionForm(id="action-form"), **context)



def navbar(role):
    """ Decorator to register a new navbar menu.
    """
    def decorator(function):
        _navbars[role] = function
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



def abort(exc):
    raise exc



def tablerow(*args, **kwargs):
    return (args, kwargs)



def sign_cookie(data):
    session_serializer = SecureCookieSessionInterface() \
                         .get_signing_serializer(current_app)
    return session_serializer.dumps(dict(session))



def unique_key(e):
    return str(e).split("\nDETAIL:  Key (")[1].split(")")[0]


