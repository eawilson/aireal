import os
import sys
import glob
from datetime import date
import pdb
from flask import Flask
from flask.json.tag import JSONTag

from .models import create_engine
from .i18n import i18n_init
from .aws import ec2_metadata



def create_app(instance_path="."):
    instance_path=os.path.abspath(instance_path)
    
    # See https://flask.palletsprojects.com/en/1.1.x/api/ Application Object for rationale.
    app = Flask(__name__.split(".")[0], instance_path=instance_path)

    config_files = glob.glob(os.path.join(instance_path, "*.cfg"))
    if len(config_files) == 0:
        sys.exit(f"No configuration file found in {instance_path}.")
    elif len(config_files) > 1:
        sys.exit(f"Multiple configuration files found in {instance_path}.")
    else:
        config_file = config_files[0]

    config = {}
    with open(config_file, "rt") as f:
        exec(f.read(), config)

    if "SECRET_KEY" not in config:
        with open(config_file, "a") as f:
            secret_key = os.urandom(16)
            f.write(f"\nSECRET_KEY = {secret_key}\n")
    
    if not hasattr(app, "extensions"):
        app.extensions = {}
    app.config.from_pyfile(config_file)
    
    app.config.update(ec2_metadata())
    if "REGION" in app.config:
        os.environ["AWS_DEFAULT_REGION"] = app.config["AWS_REGION"]
    
    db_url = config["DB_URL"]
    if db_url.startswith("sqlite:///") and db_url[10] != "/":
        cwd = os.getcwd()
        os.chdir(instance_path)
        db_path = os.path.abspath(db_url[10:])
        db_url = f"sqlite:///{db_path}"
        app.config["DB_URL"] = db_url
        os.chdir(cwd)
    
    #with app.app_context():
        #logger.initialise()
    
    app.extensions["engine"] = create_engine(db_url, isolation_level="SERIALIZABLE")
    
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

    i18n_init(app)

    from .auth import app as auth
    from .admin import app as admin
    #from .basespace import app as basespace
    #from .nanopore import app as nanopore
    from .bioinformatics import app as bioinformatics
    from .pathology import app as pathology
    from .reception import app as reception
    
    app.register_blueprint(auth)
    app.register_blueprint(admin)
    #app.register_blueprint(basespace)
    #app.register_blueprint(nanopore)
    app.register_blueprint(bioinformatics)
    app.register_blueprint(pathology)
    app.register_blueprint(reception)

    return app







