import time
import base64
import hashlib
import struct
import hmac
import os
from datetime import datetime, timezone
import pdb
from io import BytesIO
from urllib.parse import quote
from functools import wraps
from urllib.parse import urlparse, parse_qs, unquote_plus

import pytz
import pyqrcode
from babel import Locale

from flask import (session,
                   redirect,
                   url_for,
                   request,
                   abort,
                   current_app)

from werkzeug.exceptions import (Conflict,
                                 Forbidden,
                                 BadRequest,
                                 InternalServerError)

from passlib.hash import bcrypt_sha256

from .forms import (LoginForm,
                   ChangePasswordForm,
                   TwoFactorForm)
from .utils import (Transaction,
                    Cursor,
                    Blueprint,
                    sign_token,
                    render_template,
                    render_page,
                    abort,
                    _navbars,
                    original_referrer)
from .aws import sendmail
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



def update_last_session(cur, **kwargs):
    users_id = session["id"]
    sql = """SELECT last_session
             FROM users
             WHERE id = %(users_id)s;"""
    row = cur.execute(sql, {"users_id": users_id})
    last_session = (row or ({},))[0]
    new_session = {**last_session, **kwargs}
    if new_session != last_session:
        sql = """UPDATE users
                 SET last_session = %(last_session)s
                 WHERE id = %(users_id)s;"""
        cur.execute(sql, {"users_id": users_id, "last_session": new_session})



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



@app.insecure_route("/")
def root():
    if "id" in session:
        try:
            return redirect(_navbars[session["role"]]()[0]["href"])
        except (KeyError, IndexError):
            return render_page("base.html")
    else:
        return redirect(url_for(".login"))



@app.insecure_route("/login", methods=["GET", "POST"])
def login():
    feedback = ""
    form = LoginForm(request.form)
    if request.method == "POST" and form.validate():
        with Transaction() as trans:
            with trans.cursor() as cur:
                sql = """SELECT id, password, totp_secret, last_session
                         FROM users
                         WHERE email = %(email)s AND deleted = FALSE;"""
                cur.execute(sql, {"email": form.email.data})
                users_id, password, totp_secret, last_session = cur.fetchone() or (None, "", "", {})
                
        session.clear()
        one_time = hotp(totp_secret, int(time.time()) // 30)
        password_matches = verify_password(form.password.data, password)
        
        if password_matches and form.authenticator.data == one_time:
            session["id"] = users_id
            session["csrf"] = token_urlsafe(64)
            try:
                session["timezone"] = pytz.timezone(form.timezone.data).zone
            except pytz.exceptions.UnknownTimeZoneError:
                session["timezone"] = "UTC"
            
            with Transaction() as trans:
                with trans.cursor() as cur:
                    sql = """SELECT name
                             FROM role_users
                             WHERE users_id = %(users_id)s AND name IN %(valid_roles)s
                             ORDER BY name = %(role)s DESC;"""
                    cur.execute(sql, {"users_id": users_id, "role": last_session.get("role", ""), "valid_roles": Blueprint.valid_roles})
                    role = (cur.fetchone() or (None,))[0]
                        
            if role is not None:
                setrole(role)
            if "project_id" in last_session:
                setproject(last_session["project_id"])
            setlocale(last_session.get("locale", locale_from_headers()))
            
            return redirect(url_for(".root"))
            
        feedback = _("Invalid credentials.")
        
    submit = ("Login", url_for(".login"))
    reset = ("Reset Password", url_for(".reset"))
    return render_page("login.html", form=form, submit=submit, reset=reset, feedback=feedback)



@app.insecure_route("/reset", methods=["GET", "POST"])
def reset():
    feedback = ""
    form = LoginForm(request.form)
    del form["password"]
    if request.method == "POST" and form.validate():
        email = form.email.data
        with Transaction() as trans:
            with trans.cursor() as cur:
                sql = """SELECT totp_secret
                         FROM users
                         WHERE email = %(email)s AND deleted = FALSE;"""
                cur.execute(sql, {"email": email})
                totp_secret = (cur.fetchone() or ("",))[0]
            
                one_time = hotp(totp_secret, int(time.time()) // 30)
                if form.authenticator.data == one_time:
                    send_setpassword_email(cur, email)
                    feedback = _("Please check your inbox for password reset email.")
        
    submit = ("Reset", url_for(".reset"))
    back = ("Back", url_for(".login"))
    return render_page("login.html", form=form, submit=submit, back=back, feedback=feedback)



@app.route("/logoutmenu")
def logout_menu():
    menu = []
    
    rows = []
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT name
                     FROM role_users
                     WHERE users_id = %(users_id)s AND name != %(role)s AND name IN %(valid_roles)s
                     ORDER BY role_users.name;"""
            cur.execute(sql, {"users_id": session["id"], "role": session.get("role", ""), "valid_roles": Blueprint.valid_roles})
            for role, in cur:
                rows.append({"text": _(role), "href": url_for(".setrole", role=role)})
    if rows:
        menu += [{"text": _("Change Role")}] + rows + [{"divider": True}]
    
    rows = []
    for locale in sorted(current_app.extensions["locales"]):
        if locale != session["locale"]:
            name = Locale.parse(locale).get_language_name(locale)
            rows.append({"text": name, "href": url_for(".setlocale", locale=locale)})
    if rows:
        rows.sort(key=lambda x:x["text"])
        menu += [{"text": _("Change Language")}] + rows + [{"divider": True}]
    
    referrer = request.referrer
    qs = parse_qs(urlparse(referrer)[4])
    try:
        referrer = unquote_plus(qs["referrer2"][0])
    except KeyError:
        pass

    menu += [{"text": _("Account")},
             {"text": _("Change Password"), "href": url_for(".change_password", referrer2=referrer)},
             {"text": _("Two Factor Auth"), "href": url_for(".twofactor", referrer2=referrer)},
             {"text": _("Logout"), "href": url_for(".logout")}]
    return render_template("dropdown.html", items=menu)



@app.route("/setrole/<string:role>")
def setrole(role):
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT name
                     FROM role_users
                     WHERE users_id = %(users_id)s AND name = %(role)s AND name IN %(valid_roles)s;"""
            cur.execute(sql, {"users_id": session["id"], "role": role, "valid_roles": Blueprint.valid_roles})
            role = (cur.fetchone() or (None,))[0]
            
            if role is not None:
                session["role"] = role
                update_last_session(cur, role=role)
                return redirect(request.referrer)
    return redirect(url_for(".logout"))



@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for(".login"))



@app.route("/projectmenu")
def project_menu():
    menu = []
    with Transaction() as trans:
        with trans.cursor() as cur:
            sql = """SELECT project.id, project.name
                     FROM project
                     INNER JOIN project_users ON project.id = project_users.project_id
                     WHERE project_users.users_id = %(users_id)s AND project.id != %(project_id)s AND project.deleted = FALSE
                     ORDER BY project.name;"""
            cur.execute(sql, {"users_id": session["id"], "project_id": session.get("project_id", 0)})
            rows = [{"text": name, "href": url_for(".setproject", project_id=project_id)} for project_id, name in cur]

    if rows:
        menu += [{"text": _("Switch Project")},
                 {"text": _("All Projects"), "href": url_for(".setproject")}] + rows
    return render_template("dropdown.html", items=menu)



@app.route("/setproject/all", defaults={"project_id": None})
@app.route("/setproject/<int:project_id>")
def setproject(project_id):
    if project_id is None:
        project = _("All Projects")
    else:
        with Cursor() as cur:
            sql = """SELECT project.name
                        FROM project
                        INNER JOIN project_users ON project.id = project_users.project_id
                        WHERE project_users.users_id = %(users_id)s AND project.id = %(project_id)s AND project.deleted = FALSE;"""
            cur.execute(sql, {"users_id": session["id"], "project_id": project_id})
            project = (cur.fetchone() or (None,))[0]

    if project:
        session["project_id"] = project_id
        session["project"] = project
        update_last_session(cur, project_id=project_id, project=project)
    return redirect(request.referrer)



@app.route("/setlocale/<string:locale>")
def setlocale(locale):
    if locale not in current_app.extensions["locales"]:
        locale = "en_GB"
    session["locale"] = locale
    
    with Transaction() as trans:
        with trans.cursor() as cur:
            update_last_session(cur, locale=locale)
    return redirect(request.referrer)



@app.route("/changepassword", methods=["GET", "POST"])
def change_password():
    referrer = request.args.get("referrer2")
        
    form = ChangePasswordForm(request.form)
    if request.method == "POST" and form.validate():
        with Cursor() as cur:
            sql = """SELECT password
                     FROM  users
                     WHERE id = %(users_id)s;"""
            cur.execute(sql, {"users_id": session["id"]})
            old_password = (cur.fetchone() or ("",))[0]
            if bcrypt_sha256.verify(form.old_password.data, old_password):
                sql = """UPDATE users
                         SET password = %(password)s, reset_datetime = %(reset_datetime)s
                         WHERE id = %(id)s;"""
                cur.execute(sql, {"password": bcrypt_sha256.hash(form.password1.data),
                                  "reset_datetime": None,
                                  "id": session["id"]})
                return redirect(referrer)
        form.old_password.errors = _("Old password incorrect.")
    
    submit = ("Save", url_for(".change_password", referrer2=referrer))
    back = ("Cancel", referrer)
    return render_page("login.html", form=form, submit=submit, back=back)



@app.signed_route("/setpassword", methods=["GET", "POST"], max_age=60*60*24*7)
def set_password(token):
    reset_datetime = token.get("reset_datetime", datetime.now(tz=timezone.utc))
    email = token.get("email", "")
    
    with Cursor() as cur:
        sql = """SELECT id, totp_secret
                 FROM users
                 WHERE email = %(email)s AND reset_datetime = %(reset_datetime)s;"""
        cur.execute(sql, {"email": email, "reset_datetime": reset_datetime})
        users_id, totp_secret = cur.fetchone() or (None, None)
        if users_id is None:
            return redirect(url_for(".login"))
        
        form = ChangePasswordForm(request.form)
        del form["old_password"]
        if request.method == "POST" and form.validate():
            if totp_secret:
                reset_datetime = None
                destination = url_for(".login")
            else:
                destination = url_for(".twofactor", token=token)
                
            sql = """UPDATE users
                     SET password = %(password)s, reset_datetime = %(reset_datetime)s
                     WHERE id = %(users_id)s;"""
            cur.execute(sql, {"password": bcrypt_sha256.hash(form.password1.data),
                              "reset_datetime": reset_datetime,
                              "users_id": users_id})
            session.clear()
            return redirect(destination)
                
    submit = ("Save",  url_for(".set_password", token=token))
    return render_page("login.html", form=form, submit=submit)



def send_setpassword_email(cur, email):
    reset_datetime = str(datetime.now(tz=timezone.utc))
    sql = """UPDATE users
             SET reset_datetime = %(reset_datetime)s
             WHERE users.email = %(email)s;"""
    cur.execute(sql, {"reset_datetime": reset_datetime, "email": email})
    if cur.rowcount:
        token = sign_token({"email": email, "reset_datetime": reset_datetime}, salt="set_password")
        path = url_for("auth.set_password", token=token)
        host = dict(request.headers)["Host"]
        link = f"http://{host}{path}"
        name = current_app.config.get("NAME", "<APP>")
        body = _("Please follow {} to reset your {} password. This link can only be used once and will expire in 7 days.").format(link, name)
        subject = _("{} Password Link").format(name)
        if email != "someone@example.com":
            sendmail(email, subject, body)
        else:
            print(link)


@app.signed_route("/qrcode/<string:email>/<string:secret>", salt="set_password", max_age=60*60*24*7)
def qrcode(token, email, secret):
    
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



@app.signed_route("/twofactor", methods=["GET", "POST"], salt="set_password", max_age=60*60*24*7)
def twofactor(token):
    referrer = request.args.get("referrer2") or request.referrer
    token = request.args.get("token", "")
    with Transaction() as trans:
        with trans.cursor() as cur:
            if "id" in session:
                users_id = session["id"]
                sql = """SELECT email
                         FROM users
                         WHERE id = %(users_id)s;"""
                cur.execute(sql, {"users_id": users_id})
                email = (cur.fetchone() or ("",))[0]
                destination = referrer
                
            else:
                email = token.get("email")
                sql = """SELECT id
                         FROM users
                         WHERE email = %(email)s AND reset_datetime = %(reset_datetime)s;"""
                cur.execute(sql, {"email": email, "reset_datetime": token.get("reset_datetime", datetime.now(tz=timezone.utc))})
                users_id = (cur.fetchone() or (0,))[0]
                destination = url_for(".login")
            
            form = TwoFactorForm(request.form)
            if request.method == "POST" and form.validate():
                sql = """UPDATE users
                         SET totp_secret = %(totp_secret)s, reset_datetime = NULL
                         WHERE id = %(users_id)s;"""
                cur.execute(sql, {"users_id": users_id,
                                  "totp_secret": form.secret.data,
                                  "reset_datetime": None})
                return redirect(destination)
    
    kwargs = {"token": token} if token else {}
    secret = base64.b32encode(os.urandom(10)).decode("utf-8")
    qrcode_url = url_for(".qrcode", email=email, secret=secret, **kwargs)
    form.secret.data = secret
    
    buttons = {"submit": (_("Save"), url_for(".twofactor", referrer2=referrer, **kwargs))}
    if "id" in session:
        buttons["back"] = (_("Back"), referrer)
    title = _("Please scan QR code with the Authenticator App on your smartphone.")
    return render_page("twofactor.html", form=form, buttons=buttons, qrcode_url=qrcode_url, title=title)



