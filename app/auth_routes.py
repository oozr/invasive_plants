import os
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_mail import Message
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import limiter, mail
from app.utils.auth_store import AuthStore, is_allowed_researcher_email, normalize_email, utc_now_iso


auth = Blueprint("auth", __name__, url_prefix="/auth")


def _project_root() -> str:
    return current_app.config.get("PROJECT_ROOT") or os.path.abspath(os.path.join(current_app.root_path, os.pardir))


def _get_auth_store() -> AuthStore:
    store = current_app.extensions.get("auth_store")
    if store is None:
        store = AuthStore(
            db_path=current_app.config.get("AUTH_DATABASE_PATH", "auth_users.db"),
            project_root=_project_root(),
        )
        current_app.extensions["auth_store"] = store
    return store


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="researcher-login")


def _safe_next_url(value: str) -> str:
    if not value:
        return url_for("home.index")
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return url_for("home.index")
    return value if value.startswith("/") else url_for("home.index")


def _build_login_token(email: str) -> str:
    return _serializer().dumps({"email": normalize_email(email), "purpose": "researcher-login"})


def _load_login_token(token: str) -> str:
    max_age = int(current_app.config.get("AUTH_TOKEN_MAX_AGE_SECONDS", 1800))
    payload = _serializer().loads(token, max_age=max_age)
    if payload.get("purpose") != "researcher-login":
        raise BadSignature("Invalid token purpose")
    return normalize_email(payload.get("email"))


def researcher_email() -> str:
    return normalize_email(session.get("researcher_email"))


def researcher_logged_in() -> bool:
    return bool(researcher_email())


def _send_magic_link(email: str, next_url: str) -> str:
    token = _build_login_token(email)
    verify_url = url_for("auth.verify", token=token, next=next_url, _external=True)
    subject = "Your Regulated Plants login link"
    body = f"""
Use this link to sign in to the Regulated Plants Database:

{verify_url}

This link expires in 30 minutes. If you did not request it, you can ignore this email.
""".strip()

    if current_app.config.get("AUTH_DEV_SHOW_MAGIC_LINK"):
        return verify_url

    msg = Message(subject=subject, recipients=[email], body=body)
    mail.send(msg)
    return verify_url


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per hour", methods=["POST"])
def login():
    next_url = _safe_next_url(request.values.get("next"))

    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        if not is_allowed_researcher_email(email, current_app.config.get("AUTH_EMAIL_SUFFIXES")):
            flash("Use a valid .edu or .gov email address to request researcher access.", "error")
            return render_template("auth/login.html", email=email, next_url=next_url), 400

        try:
            dev_link = _send_magic_link(email, next_url)
        except Exception as exc:
            current_app.logger.error("Unable to send researcher login email: %s", exc)
            flash("We could not send the login email. Please try again later.", "error")
            return render_template("auth/login.html", email=email, next_url=next_url), 500

        return render_template(
            "auth/login_sent.html",
            email=email,
            dev_link=dev_link if current_app.config.get("AUTH_DEV_SHOW_MAGIC_LINK") else None,
        )

    return render_template("auth/login.html", email="", next_url=next_url)


@auth.route("/verify")
def verify():
    token = request.args.get("token", "")
    next_url = _safe_next_url(request.args.get("next"))

    try:
        email = _load_login_token(token)
    except SignatureExpired:
        flash("That login link has expired. Please request a new one.", "error")
        return redirect(url_for("auth.login", next=next_url))
    except BadSignature:
        flash("That login link is invalid. Please request a new one.", "error")
        return redirect(url_for("auth.login", next=next_url))

    if not is_allowed_researcher_email(email, current_app.config.get("AUTH_EMAIL_SUFFIXES")):
        flash("Use a valid .edu or .gov email address to request researcher access.", "error")
        return redirect(url_for("auth.login", next=next_url))

    _get_auth_store().record_login(email)
    session.clear()
    session["researcher_email"] = email
    session["researcher_logged_in_at"] = utc_now_iso()
    flash("You are signed in.", "success")
    return redirect(next_url)


@auth.route("/logout", methods=["POST"])
def logout():
    session.pop("researcher_email", None)
    session.pop("researcher_logged_in_at", None)
    flash("You are signed out.", "success")
    return redirect(url_for("home.index"))
