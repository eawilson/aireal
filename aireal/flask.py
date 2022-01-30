import pdb
from functools import wraps, partial
from urllib.parse import urlparse, urlunparse, parse_qs, unquote_plus, urlencode
from collections import defaultdict, ChainMap, namedtuple

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



valid_roles = set()
_navbars = {}


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
    # Match call signature used for route registration to extract
    # endpoints from the lambda functions that they are stored in.
    @staticmethod
    def add_url_rule(rule, endpoint, view_func, **options):
        return endpoint



class Blueprint(flask.Blueprint):
    def __init__(self, name, import_name, role=None, navbar=None, **kwargs):
        """ Wrapper around Bluprint __init__ method with the 
            additional positional argument *roles. This lists
            all the roles that are allowed to access the routes
            of this Blueprint. If no roles are provided then all
            logged in users can access the route.
        """
        if navbar is not None:
            valid_roles.add(name)
            _navbars[name] = navbar
        self.signatures = {}
        self.role = role or name
        return super().__init__(name, import_name, **kwargs)
        
        
        
    def route(self, rule, signature=None, max_age=None, **options):
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
            if signature:
                self.signatures[rule] = partial(_validate_token,
                                                max_age=max_age,
                                                salt=signature)
            
            endpoint = options.pop("endpoint", None) or function.__name__
            for registration_function in self.deferred_functions:
                try:
                    if registration_function(_ReturnEndpoint) == endpoint:
                        wrapper = function
                        break
                except Exception:
                    pass
            
            else:
                @wraps(function)
                def wrapper(*args, **kwargs):
                    rule = request.url_rule.rule
                    if rule in self.signatures:
                        token = kwargs["token"]
                        deserialised = self.signatures[rule](token)
                        if not deserialised:
                            return redirect(url_for("Auth.login"))
                        kwargs["token"] = {"token": token, **deserialised}
                    
                    elif "id" not in session:
                        return redirect(url_for("Auth.login"))
                    
                    elif self.role in _navbars and session["role"] != self.role:
                        if request.method == "POST":
                            abort(exceptions.Forbidden)
                        else:
                            return redirect(url_for("Auth.root"))
                    
                    try:
                        return function(*args, **kwargs)
                    except IntegrityError:
                        abort(exceptions.Conflict)
            
            self.add_url_rule(rule, endpoint, wrapper, **options)
            return wrapper
        return decorator
    
    
    def insecure_route(self, *args, **kwargs):
        return super().route(*args, **kwargs)



def _validate_token(token, max_age=0, salt=None):
    if token:
        secret = current_app.config["SECRET_KEY"]
        s = URLSafeTimedSerializer(secret, salt=salt)
        try:
            return s.loads(token, max_age=max_age)
        except BadSignature:
            pass
    return {}



def original_referrer():
    qs = parse_qs(urlparse(request.url)[4])
    try:
        return unquote_plus(qs["referrer"][0])
    except KeyError:
        return request.referrer



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
        right = [{"text": session.get("project", ""),
                  "href": url_for("Auth.project_menu"),
                  "dropdown": True},
                 {"text": "",
                  "href": url_for("Auth.logout_menu"),
                  "dropdown": True}]
        navbar = {"app": application,
                  "name": _(session.get("role", "")),
                  "active": active,
                  "left": _navbars[session["role"]](),
                  "right": right}
    return render_template(name, navbar=navbar, table_form=ActionForm(id="table-form"), **context)



def abort(exc):
    raise exc



def flask_cookie(data):
    session_serializer = SecureCookieSessionInterface() \
                         .get_signing_serializer(current_app)
    return session_serializer.dumps(dict(data))
