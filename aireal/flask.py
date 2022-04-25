import pdb
import os
import glob
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

__all__ = ["valid_roles",
           "sign_token",
           "build_url"
           "Blueprint",
           "abort",
           "render_template",
           "render_page",
           "sign_cookie",
           "unique_key",
           "iso8601_to_utc",
           "config_file",
           "load_config"]



def valid_roles():
    return tuple(set(role.split(".")[0] for role in current_app.blueprints.keys() if role != "Auth"))



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



class _ReturnEndpoint(object):
    # Match call signature used for route registration to extract
    # endpoints from the lambda functions that they are stored in.
    @staticmethod
    def add_url_rule(rule, endpoint, view_func, **options):
        return endpoint



class Blueprint(flask.Blueprint):
    navbars = {}
    
    def route(self, rule, signature=None, max_age=None, **options):
        """ Wrapper arounf Blueprint route with the additional positional
            argument *roles. This overides *roles in the __init__ method
            and lists all the roles allowed to access this route. Returns
            the wrapped view function that performs the following action:
            
            1) Check that the user is logged in.
            
            2) Check that the user has assumed the correct role to access
               this view.
            
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
                    if "/<string:token>" in request.url_rule.rule:
                        token = kwargs["token"]
                        deserialised = _validate_token(token, max_age=max_age, salt=signature or endpoint)
                        if not deserialised:
                            return redirect(url_for("Auth.login"))
                        kwargs["token"] = {"token": token, **deserialised}
                    
                    elif "id" not in session:
                        return redirect(url_for("Auth.login"))
                    
                    elif "Auth" != request.blueprint.split(".")[0] != session["role"]:
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
                  "left": Blueprint.navbars[session["role"]](),
                  "right": right}
    return render_template(name, navbar=navbar, table_form=ActionForm(id="table-form"), **context)



def abort(exc):
    raise exc



def flask_cookie(data):
    session_serializer = SecureCookieSessionInterface() \
                         .get_signing_serializer(current_app)
    return session_serializer.dumps(dict(data))



def query_parameter(key, numeric=False):
    param = request.args.get(key, "")
    if numeric:
        try:
            param = int(param)
        except ValueError:
            param = 0
    return param



def config_file(instance_path):
    config_files = glob.glob(os.path.join(instance_path, "*.cfg"))
    if len(config_files) == 0:
        sys.exit(f"No configuration file found in {instance_path}")
    elif len(config_files) > 1:
        sys.exit(f"Multiple configuration files found in {instance_path}")
    else:
        return config_files[0]




def load_config(config_path):
    config = {}
    with open(config_path, "rt") as f:
        exec(f.read(), config)
    return config


