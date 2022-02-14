import os
import sys
from datetime import date
import pdb

from flask import Flask
from flask.json.tag import JSONTag
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import BaseConverter

import psycopg2
from psycopg2.extras import Json
from psycopg2.pool import ThreadedConnectionPool

from .i18n import i18n_init
from .aws import ec2_metadata
from .version import __version__
from .flask import config_file, load_config



def create_app(instance_path="."):
    instance_path=os.path.abspath(instance_path)
    
    # See https://flask.palletsprojects.com/en/1.1.x/api/ Application Object for rationale.
    app = Flask(__name__.split(".")[0], instance_path=instance_path)

    config_path = config_file(instance_path)
    config = load_config(config_path)
    if "SECRET_KEY" not in config:
        with open(config_path, "a") as f:
            secret_key = os.urandom(16)
            f.write(f"\nSECRET_KEY = {secret_key}\n")
    
    if not hasattr(app, "extensions"):
        app.extensions = {}
    app.config.from_pyfile(config_path)
    
    app.config.update(ec2_metadata())
    if "AWS_REGION" in app.config:
        os.environ["AWS_DEFAULT_REGION"] = app.config["AWS_REGION"]
    
    
    with psycopg2.connect(config["DB_URI"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM version ORDER BY datetime DESC LIMIT 1;")
            db_version = cur.fetchone()
            if not db_version or db_version[0] != __version__:
                sys.exit(f"Database version does not match application version")
    
    psycopg2.extensions.register_adapter(dict, Json)
    app.extensions["connction_pool"] = ThreadedConnectionPool(1, 10, dsn=config["DB_URI"])
    
    class TagDate(JSONTag):
        __slots__ = ('serializer',)
        key = ' de'
        
        def check(self, value):
            return isinstance(value, date)

        def to_json(self, value):
            return value.toordinal()

        def to_python(self, value):
            return date.fromordinal(value)

    try: # exception will only occur with reloading in development server
        app.session_interface.serializer.register(TagDate)
    except KeyError:
        pass
    
    class CSVMatch(BaseConverter):
        regex = r".+,.*"

    app.url_map.converters["csv"] = CSVMatch
    
    if not app.debug:
        app.config.update(SESSION_COOKIE_SECURE=True,
                          SESSION_COOKIE_HTTPONLY=True,
                          SESSION_COOKIE_SAMESITE='Lax')
        
        @app.after_request
        def security_headers(response):
            #response.headers['Strict-Transport-Security'] = \
            #    'max-age=31536000; includeSubDomains'
            #response.headers['Content-Security-Policy'] = "default-src 'self'"
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            return response
    
    if "PROXY_FIX" in app.config:
        app.wsgi_app = ProxyFix(app.wsgi_app, **app.config["PROXY_FIX"])
    
    i18n_init(app)

    from .auth import app as auth
    from .admin import app as admin
    from .bioinformatics import app as bioinformatics
    from .pathology import app as pathology
    from .reception import app as reception
    
    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(bioinformatics)
    app.register_blueprint(pathology)
    app.register_blueprint(reception)
    
    return app







