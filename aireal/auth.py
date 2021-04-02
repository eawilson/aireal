import time
import base64
import hashlib
import struct
import hmac
import os
import pdb
from io import BytesIO
from urllib.parse import quote
from functools import wraps

import pytz
import pyqrcode
from babel import Locale

from sqlalchemy import (select,
                        join,
                        or_,
                        and_)

from flask import (session,
                   redirect,
                   url_for,
                   request,
                   abort,
                   Blueprint,
                   current_app)

from werkzeug.exceptions import (Conflict,
                                 Forbidden,
                                 BadRequest,
                                 InternalServerError)

from passlib.hash import bcrypt_sha256
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadSignature

from .models import (users,
                     groups,
                     users_groups,
                     sites,
                     users_sites,
                     projects,
                     users_projects)
from .forms import (LoginForm,
                   ChangePasswordForm,
                   TwoFactorForm)
from .utils import (render_template,
                    render_page,
                    utcnow,
                    surname_forename,
                    engine,
                    login_required,
                    valid_groups,
                    abort,
                    _navbars,
                    original_referrer)
from .aws import sendmail
from . import logic
from .i18n import _, locale_from_headers



try:
    from secrets import token_urlsafe
except ImportError: # python < 3.6
    def token_urlsafe(nbytes=32):
        secret = base64.urlsafe_b64encode(os.urandom(nbytes))
        return secret.rstrip(b'=').decode('ascii')

__all__ = ("app",
           "send_setpassword_email")


app = Blueprint("auth", __name__)



def token_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        token = {**request.view_args, **request.args}.get("token")
        if token and validate_token(token):
            return function(*args, **kwargs)
        else:
            return login_required()(function)(*args, **kwargs)
    return wrapper



def validate_token(token):
    secret = current_app.config["SECRET_KEY"]
    s = URLSafeTimedSerializer(secret, salt="set_password")
    try:
        return s.loads(token, max_age=60*60*24*7)
    except BadSignature:
        return {}



def verify_password(password, hash):
    try:
        return bcrypt_sha256.verify(password, hash or "")
    except ValueError:
        # Malformed hash
        return False



def hotp(secret, counter, token_length=6):
    ### HMAC-based One-Time Password
    ###
    try:
        key = base64.b32decode(secret or "")
    except base64.binascii.Error:
        return -1 # This will never match a true token
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[19] & 15
    number = struct.unpack('>I', digest[offset:offset+4])[0] & 0x7fffffff
    token = number % (10 ** token_length)
    return token



@app.route("/")
def root():
    if "id" in session:
        try:
            return redirect(_navbars[session["group"]]()[0]["href"])
        except (KeyError, IndexError):
            return render_page("base.html")
    else:
        return redirect(url_for(".login"))



@app.route("/login", methods=["GET", "POST"])
def login():
    feedback = ""
    form = LoginForm(request.form)
    if request.method == "POST" and form.validate():
        with engine.connect() as conn:
            sql = select([users.c.id, users.c.password, users.c.totp_secret, users.c.last_session]). \
                    where(and_(users.c.email == form.email.data, users.c.deleted == False))
            row = dict(conn.execute(sql).first() or ())
        
        session.clear()
        one_time = hotp(row.get("totp_secret"), int(time.time()) // 30)
        password_matches = verify_password(form.password.data, row.get("password"))
        
        if password_matches and form.authenticator.data == one_time:
            session["id"] = row["id"]
            session["csrf"] = token_urlsafe(64)
            try:
                session["timezone"] = pytz.timezone(form.timezone.data).zone
            except pytz.exceptions.UnknownTimeZoneError:
                session["timezone"] = "UTC"
                
            last_session = row["last_session"]
            if "group_id" in last_session:
                setrole(last_session["group_id"])
            if "site_id" in last_session:
                setsite(last_session["site_id"])
            if "project_id" in last_session:
                setproject(last_session["project_id"])
            if "locale" in last_session:
                locale = last_session["locale"]
            else:
                locale = locale_from_headers()
            setlocale(locale)
            
            return redirect(url_for(".root"))
            
        feedback = _("Invalid credentials.")
        
    submit = ("Login", url_for(".login"))
    reset = ("Reset Password", url_for(".reset"))
    return render_page("login.html", form=form, submit=submit, reset=reset, feedback=feedback)



@app.route("/reset", methods=["GET", "POST"])
def reset():
    feedback = ""
    form = LoginForm(request.form)
    del form["password"]
    if request.method == "POST" and form.validate():
        with engine.connect() as conn:
            sql = select([users.c.totp_secret, users.c.email]). \
                    where(and_(users.c.email == form.email.data, users.c.deleted == False))
            row = dict(conn.execute(sql).first() or ())
            
            one_time = hotp(row.get("totp_secret"), int(time.time()) // 30)
            if form.authenticator.data == one_time:
                send_setpassword_email(row["email"], conn)
                feedback = _("Please check your inbox for password reset email.")
        
    submit = ("Reset", url_for(".reset"))
    back = ("Back", url_for(".login"))
    return render_page("login.html", form=form, submit=submit, back=back, feedback=feedback)



@app.route("/logoutmenu")
@login_required()
def logout_menu():
    menu = []
    with engine.connect() as conn:
        sql = select([groups.c.id, groups.c.name]). \
                select_from(join(groups, users_groups, 
                                    groups.c.id == users_groups.c.group_id)). \
                where(and_(users_groups.c.user_id == session["id"],
                            groups.c.name != session.get("group", None),
                            groups.c.name.in_(valid_groups))). \
                order_by(groups.c.name)
        rows = []
        for group_id, name in conn.execute(sql):
            rows.append({"text": name, "href": url_for(".setrole", group_id=group_id)})
    if rows:
        menu += [{"text": _("Change Role")}] + rows + [{"divider": True}]
    
    rows = []
    for locale in current_app.extensions["locales"]:
        if locale != session["locale"]:
            name = Locale.parse(locale).get_language_name(locale)
            rows.append({"text": name, "href": url_for(".setlocale", locale=locale)})
    if rows:
        rows.sort(key=lambda x:x["text"])
        menu += [{"text": _("Change Language")}] + rows + [{"divider": True}]
    
    referrer = original_referrer()
    menu += [{"text": _("Account")},
             {"text": _("Change Password"), "href": url_for(".change_password", referrer=referrer)},
             {"text": _("Two Factor Auth"), "href": url_for(".twofactor", referrer=referrer)},
             {"text": _("Logout"), "href": url_for(".logout")}]
    return render_template("dropdown.html", items=menu)



@app.route("/setrole/<int:group_id>")
@login_required()
def setrole(group_id):
    with engine.begin() as conn:
        sql = select([groups.c.name, users.c.last_session]). \
                select_from(join(groups, users_groups, 
                                groups.c.id == users_groups.c.group_id). \
                            join(users, users.c.id == users_groups.c.user_id)). \
                where(and_(users_groups.c.user_id == session["id"],
                           groups.c.id == group_id,
                           groups.c.name.in_(valid_groups)))
        for row in conn.execute(sql):
            group, last_session = row
            session["group"] = group
            
            if last_session.get("group_id", None) != group_id:
                last_session["group_id"] = group_id
                conn.execute(users.update().where(users.c.id == session["id"]).values(last_session=last_session))
            return redirect(request.referrer)
    return redirect(url_for(".logout"))



@app.route("/logout")
@login_required()
def logout():
    session.clear()
    return redirect(url_for(".login"))



@app.route("/sitemenu")
@login_required()
def site_menu():
    menu = []
    with engine.connect() as conn:
        sql = select([sites.c.id, sites.c.name]). \
                select_from(join(sites, users_sites, 
                                    sites.c.id == users_sites.c.site_id)). \
                where(and_(users_sites.c.user_id == session["id"],
                           sites.c.id != session.get("site_id", None),
                           sites.c.deleted == False)). \
                order_by(sites.c.name)
        rows = [{"text": name, "href": url_for(".setsite", site_id=site_id)}
                for site_id, name in conn.execute(sql)]
    if rows:
        menu += [{"text": _("Switch Site")}] + rows
    return render_template("dropdown.html", items=menu)



@app.route("/setsite/<int:site_id>")
@login_required()
def setsite(site_id):
    with engine.begin() as conn:
        sql = select([sites.c.name, users.c.last_session]). \
                select_from(join(sites, users_sites, 
                                sites.c.id == users_sites.c.site_id). \
                            join(users, users.c.id == users_sites.c.user_id)). \
                where(and_(users_sites.c.user_id == session["id"],
                           sites.c.id == site_id,
                           sites.c.deleted == False))
        row = conn.execute(sql).first()
        if row:
            site, last_session = row
            session["site_id"] = site_id
            session["site"] = site
            
            if last_session.get("site_id", None) != site_id:
                last_session["site_id"] = site_id
                conn.execute(users.update().where(users.c.id == session["id"]).values(last_session=last_session))
    return redirect(request.referrer)



@app.route("/projectmenu")
@login_required()
def project_menu():
    menu = []
    with engine.connect() as conn:
        sql = select([projects.c.id, projects.c.name]). \
                select_from(join(projects, users_projects,
                                    projects.c.id == users_projects.c.project_id)). \
                where(and_(users_projects.c.user_id == session["id"],
                           projects.c.id != session.get("project_id", None),
                           projects.c.deleted == False)). \
                order_by(projects.c.name)
        rows = [{"text": name, "href": url_for(".setproject", project_id=project_id)}
                for project_id, name in conn.execute(sql)]
    if rows:
        menu += [{"text": _("Switch Project")},
                 {"text": _("All Projects"), "href": url_for(".setproject")}] + rows
    return render_template("dropdown.html", items=menu)



@app.route("/setproject/all", defaults={"project_id": None})
@app.route("/setproject/<int:project_id>")
@login_required()
def setproject(project_id):
    with engine.begin() as conn:
        if project_id is None:
            sql = select([users.c.last_session]).where(users.c.id == session["id"])
            last_session = conn.execute(sql).scalar()
            row = [None, _("All Projects"), last_session]
        else:
            sql = select([projects.c.id, projects.c.name, users.c.last_session]). \
                    select_from(join(projects, users_projects, 
                                        projects.c.id == users_projects.c.project_id). \
                                join(users, users.c.id == users_projects.c.user_id)). \
                    where(and_(users_projects.c.user_id == session["id"],
                            projects.c.id == project_id,
                            projects.c.deleted == False))
            row = conn.execute(sql).first()
        if row:
            last_session = row[2]
            session["project_id"] = last_session["project_id"] = row[0]
            session["project"] = row[1]
            conn.execute(users.update().where(users.c.id == session["id"]).values(last_session=last_session))
    return redirect(request.referrer)



@app.route("/setlocale/<string:locale>")
@login_required()
def setlocale(locale):
    if locale != session.get("locale", None):
        if locale in current_app.extensions.get("locales", ()):
            session["locale"] = locale
        else:
            session["locale"] = "en_GB"
        with engine.begin() as conn:
            sql = select([users.c.last_session]).where(users.c.id == session["id"])
            last_session = conn.execute(sql).scalar()
            if last_session.get("locale", None) != session["locale"]:
                last_session["locale"] = session["locale"]
                conn.execute(users.update().where(users.c.id == session["id"]).values(last_session=last_session))
    return redirect(request.referrer)



@app.route("/changepassword", methods=["GET", "POST"])
@login_required()
def change_password():
    referrer = request.args.get("referrer")
    with engine.begin() as conn:
        form = ChangePasswordForm(request.form)
        if request.method == "POST" and form.validate():
            sql = select([users.c.password]). \
                        where(users.c.id == session["id"])
            old_password = conn.execute(sql).scalar()
            if old_password and bcrypt_sha256.verify(form.old_password.data, old_password):
                new = {"password": bcrypt_sha256.hash(form.password1.data),
                       "reset_datetime": None}
                old = {"id": session["id"]}
                logic.crud(conn, users, new, old)
                return redirect(referrer)
            form.old_password.errors = _("Old password incorrect.")
        submit = ("Save", url_for(".change_password", referrer=referrer))
        back = ("Cancel", referrer)
    return render_page("login.html", form=form, submit=submit, back=back)



@app.route("/setpassword/<string:token>", methods=["GET", "POST"])
@token_required
def set_password(token):
    with engine.begin() as conn:
        payload = validate_token(token)
        sql = select([users.c.id, users.c.totp_secret]). \
                where(and_(users.c.email == payload.get("email"), \
                            users.c.reset_datetime == payload.get("reset_datetime")))
        old = dict(conn.execute(sql).first() or ())
        if not old:
            return redirect(url_for(".login"))
        
        form = ChangePasswordForm(request.form)
        del form["old_password"]
        if request.method == "POST" and form.validate():
            new = {"password": bcrypt_sha256.hash(form.password1.data)}
            if old["totp_secret"]:
                new["reset_datetime"] = None
                destination = url_for(".login")
            else:
                destination = url_for(".twofactor", token=token)
            logic.crud(conn, users, new, old)
            session.clear()
            return redirect(destination)
                
    submit = ("Save",  url_for(".set_password", token=token))
    return render_page("login.html", form=form, submit=submit)



def send_setpassword_email(email, conn):
    reset_datetime = str(utcnow())
    sql = users.update(). \
            where(users.c.email == email). \
            values(reset_datetime=reset_datetime)
    if conn.execute(sql).rowcount:
        config = current_app.config
        serializer = URLSafeTimedSerializer(config['SECRET_KEY'],
                                            salt="set_password")
        token = serializer.dumps({"email": email,
                                  "reset_datetime": reset_datetime})
        path = url_for("auth.set_password", token=token)
        host = dict(request.headers)["Host"]
        link = f"http://{host}{path}"
        name = config.get("NAME", "<APP>")
        body = _("Please follow {} to reset your {} password. This link can only be used once and will expire in 7 days.").format(link, name)
        subject = _("{} Password Link").format(name)
        if email != "someone@example.com":
            sendmail(email, subject, body)
        else:
            print(link)


@app.route("/qrcode/<string:email>/<string:secret>")
@token_required
def qrcode(email, secret):
    
    service = quote(current_app.config.get("NAME", "<APP>"))
    email = quote(email)
    secret = quote(secret)
    
    # https://github.com/google/google-authenticator/wiki/Key-Uri-Format
    uri = f"otpauth://totp/{service}:{email}?secret={secret}&issuer={service}"
    
    qrcode = pyqrcode.create(uri)
    stream = BytesIO()
    qrcode.svg(stream, scale=5)
    return stream.getvalue(), 200, {
        "Content-Type": "image/svg+xml",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"}



@app.route("/twofactor", methods=["GET", "POST"])
@token_required
def twofactor():
    referrer = request.args.get("referrer") or request.referrer
    token = request.args.get("token", "")
    with engine.begin() as conn:
        if "id" in session:
            user_id = session["id"]
            email = conn.execute(select([users.c.email]).where(users.c.id == user_id)).scalar()
            destination = referrer
            
        else:
            payload = validate_token(token)
            email = payload.get("email")
            user_id = conn.execute(select([users.c.id]). \
                    where(and_(users.c.email == email,
                                users.c.reset_datetime == payload.get("reset_datetime")))). \
                    scalar()
            destination = url_for(".login")
        
        form = TwoFactorForm(request.form)
        if request.method == "POST" and form.validate():
            new = {"totp_secret": form.secret.data}
            if "id" not in session:
                new["reset_datetime"] = None
            sql = users.update(). \
                    where(users.c.id == user_id). \
                    values(**new)
            conn.execute(sql)
            return redirect(destination)
    
    kwargs = {"token": token} if token else {}
    secret = base64.b32encode(os.urandom(10)).decode("utf-8")
    qrcode_url = url_for(".qrcode", email=email, secret=secret, **kwargs)
    form.secret.data = secret
    
    buttons = {"submit": (_("Save"), url_for(".twofactor", referrer=referrer, **kwargs))}
    if "id" in session:
        buttons["back"] = (_("Back"), referrer)
    title = _("Please scan QR code with the Authenticator App on your smartphone.")
    return render_page("twofactor.html", form=form, buttons=buttons, qrcode_url=qrcode_url, title=title)



