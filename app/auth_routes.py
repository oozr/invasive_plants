import os
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_mail import Message
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import limiter, mail
from app.utils.auth_store import (
    AuthStore,
    is_allowed_researcher_email,
    normalize_affiliation_name,
    normalize_email,
    utc_now_iso,
)
from app.utils.ror_client import email_matches_ror_domains, fetch_ror_record, normalize_ror_id, search_ror_organizations


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


def _email_is_allowed(email: str) -> bool:
    return is_allowed_researcher_email(
        email,
        current_app.config.get("AUTH_EMAIL_SUFFIXES"),
        current_app.config.get("AUTH_EMAIL_DOMAINS"),
    )


def _email_is_allowed_for_ror(email: str, affiliation_ror_id: str) -> bool:
    if not current_app.config.get("AUTH_ROR_ENABLED"):
        return False
    if not affiliation_ror_id:
        return False
    try:
        record = fetch_ror_record(
            affiliation_ror_id,
            current_app.config.get("ROR_API_BASE_URL", "https://api.ror.org/v2/organizations"),
            current_app.config.get("ROR_API_TIMEOUT_SECONDS", 4),
        )
    except Exception as exc:
        current_app.logger.warning("Unable to validate ROR domain for %s: %s", affiliation_ror_id, exc)
        return False

    allowed_types = {
        item.strip().lower()
        for item in str(current_app.config.get("AUTH_ROR_ALLOWED_TYPES", "")).split(",")
        if item.strip()
    }
    record_types = {str(item or "").strip().lower() for item in (record.get("types") or [])}
    if allowed_types and not (record_types & allowed_types):
        return False

    return email_matches_ror_domains(email, record)


def _access_email_is_allowed(email: str, affiliation_ror_id: str = None) -> bool:
    return _email_is_allowed(email) or _email_is_allowed_for_ror(email, affiliation_ror_id)


def _build_login_token(email: str, affiliation_name: str, affiliation_ror_id: str = None) -> str:
    return _serializer().dumps(
        {
            "email": normalize_email(email),
            "affiliation_name": normalize_affiliation_name(affiliation_name),
            "affiliation_ror_id": normalize_ror_id(affiliation_ror_id) if affiliation_ror_id else None,
            "purpose": "researcher-login",
        }
    )


def _load_login_token(token: str) -> dict:
    max_age = int(current_app.config.get("AUTH_TOKEN_MAX_AGE_SECONDS", 1800))
    payload = _serializer().loads(token, max_age=max_age)
    if payload.get("purpose") != "researcher-login":
        raise BadSignature("Invalid token purpose")
    return {
        "email": normalize_email(payload.get("email")),
        "affiliation_name": normalize_affiliation_name(payload.get("affiliation_name")),
        "affiliation_ror_id": normalize_ror_id(payload.get("affiliation_ror_id")) if payload.get("affiliation_ror_id") else None,
    }


def researcher_email() -> str:
    return normalize_email(session.get("researcher_email"))


def researcher_logged_in() -> bool:
    return bool(researcher_email())


def _send_magic_link(email: str, affiliation_name: str, affiliation_ror_id: str, next_url: str) -> str:
    token = _build_login_token(email, affiliation_name, affiliation_ror_id)
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
        affiliation_name = normalize_affiliation_name(request.form.get("affiliation_name"))
        affiliation_ror_id = normalize_ror_id(request.form.get("affiliation_ror_id")) if request.form.get("affiliation_ror_id") else None
        if not affiliation_name:
            flash("Enter the university, research institution, or government body you represent.", "error")
            return render_template(
                "auth/login.html",
                email=email,
                affiliation_name=affiliation_name,
                affiliation_ror_id=affiliation_ror_id,
                next_url=next_url,
            ), 400
        if len(affiliation_name) > 160:
            flash("Affiliation must be 160 characters or fewer.", "error")
            return render_template(
                "auth/login.html",
                email=email,
                affiliation_name=affiliation_name[:160],
                affiliation_ror_id=affiliation_ror_id,
                next_url=next_url,
            ), 400

        if not _access_email_is_allowed(email, affiliation_ror_id):
            flash("Use an approved institutional email address, or select your organization from the affiliation suggestions if your institution uses a country domain.", "error")
            return render_template(
                "auth/login.html",
                email=email,
                affiliation_name=affiliation_name,
                affiliation_ror_id=affiliation_ror_id,
                next_url=next_url,
            ), 400

        try:
            dev_link = _send_magic_link(email, affiliation_name, affiliation_ror_id, next_url)
        except Exception as exc:
            current_app.logger.error("Unable to send researcher login email: %s", exc)
            flash("We could not send the login email. Please try again later.", "error")
            return render_template(
                "auth/login.html",
                email=email,
                affiliation_name=affiliation_name,
                affiliation_ror_id=affiliation_ror_id,
                next_url=next_url,
            ), 500

        return render_template(
            "auth/login_sent.html",
            email=email,
            dev_link=dev_link if current_app.config.get("AUTH_DEV_SHOW_MAGIC_LINK") else None,
        )

    return render_template("auth/login.html", email="", affiliation_name="", affiliation_ror_id="", next_url=next_url)


@auth.route("/api/affiliations")
@limiter.limit("120 per hour")
def affiliations():
    if not current_app.config.get("AUTH_ROR_ENABLED"):
        return jsonify({"results": []})

    query = request.args.get("q", "").strip()
    if len(query) < 3:
        return jsonify({"results": []})

    try:
        results = search_ror_organizations(
            query,
            current_app.config.get("ROR_API_BASE_URL", "https://api.ror.org/v2/organizations"),
            current_app.config.get("ROR_API_TIMEOUT_SECONDS", 4),
            limit=10,
        )
    except Exception as exc:
        current_app.logger.warning("Unable to search ROR affiliations for %r: %s", query, exc)
        return jsonify({"results": []})

    return jsonify({"results": results})


@auth.route("/verify")
def verify():
    token = request.args.get("token", "")
    next_url = _safe_next_url(request.args.get("next"))

    try:
        token_payload = _load_login_token(token)
    except SignatureExpired:
        flash("That login link has expired. Please request a new one.", "error")
        return redirect(url_for("auth.login", next=next_url))
    except BadSignature:
        flash("That login link is invalid. Please request a new one.", "error")
        return redirect(url_for("auth.login", next=next_url))

    email = token_payload["email"]
    affiliation_name = token_payload["affiliation_name"]
    affiliation_ror_id = token_payload["affiliation_ror_id"]

    if not affiliation_name:
        flash("Please request a new login link with your affiliation.", "error")
        return redirect(url_for("auth.login", next=next_url))

    if not _access_email_is_allowed(email, affiliation_ror_id):
        flash("Use an approved institutional email address, or select your organization from the affiliation suggestions if your institution uses a country domain.", "error")
        return redirect(url_for("auth.login", next=next_url))

    _get_auth_store().record_login(email, affiliation_name, affiliation_ror_id)
    session.clear()
    session["researcher_email"] = email
    session["researcher_affiliation_name"] = affiliation_name
    session["researcher_affiliation_ror_id"] = affiliation_ror_id
    session["researcher_logged_in_at"] = utc_now_iso()
    flash("You are signed in.", "success")
    return redirect(next_url)


@auth.route("/logout", methods=["POST"])
def logout():
    session.pop("researcher_email", None)
    session.pop("researcher_affiliation_name", None)
    session.pop("researcher_affiliation_ror_id", None)
    session.pop("researcher_logged_in_at", None)
    flash("You are signed out.", "success")
    return redirect(url_for("home.index"))
