# app/views.py
import gzip
import hmac
import json
import os
from datetime import datetime
from urllib.parse import urlparse
import requests as http_requests
from flask import Blueprint, render_template, jsonify, current_app, request, flash, url_for, redirect, send_from_directory, abort, session
from werkzeug.utils import safe_join
from werkzeug.security import check_password_hash

from app import limiter, recaptcha
from app.utils.state_database import StateDatabase
from app.utils.species_database import SpeciesDatabase
from app.utils.generate_blog import BlogGenerator
from app.utils.email_sender import send_email

# Blueprints
home = Blueprint("home", __name__)
species = Blueprint("species", __name__, url_prefix="/species")
blog = Blueprint("blog", __name__, url_prefix="/blog")
method = Blueprint("method", __name__, url_prefix="/method")
api_page = Blueprint("api_page", __name__, url_prefix="/api")
about = Blueprint("about", __name__, url_prefix="/about")

# Blog generator
blog_generator = BlogGenerator()


# ----------------------------
# Helpers
# ----------------------------
def _get_state_db() -> StateDatabase:
    db = current_app.extensions.get("state_db")
    if db is None:
        db = StateDatabase(
            db_path=current_app.config.get("DATABASE_PATH", "weeds.db"),
            geojson_dir=current_app.config.get("GEOJSON_DIR"),
        )
        current_app.extensions["state_db"] = db
    return db


def _get_species_db() -> SpeciesDatabase:
    db = current_app.extensions.get("species_db")
    if db is None:
        db = SpeciesDatabase(
            db_path=current_app.config.get("DATABASE_PATH", "weeds.db"),
            geojson_dir=current_app.config.get("GEOJSON_DIR"),
        )
        current_app.extensions["species_db"] = db
    return db


def _bool_arg(name: str, default: bool = True) -> bool:
    v = request.args.get(name, str(default)).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _toggle_params():
    """
    3-toggle system (all ON by default):
      includeRegion
      includeNational
      includeInternational
    """
    include_region = _bool_arg("includeRegion", True)
    include_national = _bool_arg("includeNational", True)
    include_international = _bool_arg("includeInternational", True)
    return include_region, include_national, include_international


# ----------------------------
# Home routes
# ----------------------------
@home.route("/")
def index():
    metrics_enabled = str(current_app.config.get("OOZR_METRICS_ENABLED", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return render_template(
        "home.html",
        geojson_path=current_app.config.get("GEOJSON_URL_PATH", "/data/geojson/"),
        data_version=current_app.config.get("DATA_VERSION", ""),
        oozr_base_url=current_app.config.get("OOZR_BASE_URL", ""),
        oozr_project_slug=current_app.config.get("OOZR_PROJECT_SLUG", "regulatedplants"),
        oozr_metrics_enabled=metrics_enabled,
    )


@home.route("/privacy")
def privacy():
    return render_template("privacy.html")


@home.route("/robots.txt")
def robots_txt():
    return current_app.send_static_file("robots.txt")


@home.route("/api/region-weed-counts")
def region_weed_counts():
    """
    Returns map rows keyed by stable geo_region_id.
    Used to colour the map and drive tooltip provenance.
    """
    include_region, include_national, include_international = _toggle_params()
    counts = _get_state_db().get_region_weed_counts(
        include_region=include_region,
        include_national=include_national,
        include_international=include_international,
    )
    return jsonify(counts)


@home.route("/api/region")
def region_weeds():
    """
    Returns weeds for a specific mapped geo region.
    Called by map click.

    Query args:
      geo_region_id=<stable map region id>
      includeRegion/includeNational/includeInternational
    """
    geo_region_id = request.args.get("geo_region_id", "").strip()
    if not geo_region_id:
        return jsonify({"error": "geo_region_id is required"}), 400

    include_region, include_national, include_international = _toggle_params()
    payload = _get_state_db().get_weeds_for_geo_region(
        geo_region_id=geo_region_id,
        include_region=include_region,
        include_national=include_national,
        include_international=include_international,
    )
    if not payload.get("geo_region"):
        return jsonify({"error": "geo_region_id not found"}), 404

    authenticated = bool(session.get("researcher_email"))
    sample_limit = max(0, int(current_app.config.get("AUTH_ANONYMOUS_SAMPLE_LIMIT", 5)))
    weeds = payload.get("weeds") or []
    total_count = len(weeds)
    if not authenticated:
        payload["weeds"] = weeds[:sample_limit]

    payload["authenticated"] = authenticated
    payload["sample_limit"] = sample_limit
    payload["total_count"] = total_count
    payload["is_sample"] = (not authenticated) and total_count > len(payload.get("weeds") or [])

    return jsonify(payload)


@home.route("/api/geojson-files")
def geojson_files():
    """
    Return a list of GeoJSON filenames in static/data/geographic.
    map.js will call this to know which files to load.
    """
    try:
        geo_dir = current_app.config.get("GEOJSON_DIR")

        files = []
        if geo_dir and os.path.isdir(geo_dir):
            for fname in os.listdir(geo_dir):
                if fname.lower().endswith(".geojson"):
                    files.append(fname)

        files.sort()
        return jsonify(files)
    except Exception as e:
        current_app.logger.error(f"Error listing geojson files: {e}")
        return jsonify({"error": "Failed to list geojson files"}), 500


@home.route("/data/geojson/<path:filename>")
def geojson_file(filename: str):
    geo_dir = current_app.config.get("GEOJSON_DIR")
    if not geo_dir:
        return jsonify({"error": "GeoJSON directory not configured"}), 500
    file_path = safe_join(geo_dir, filename)
    if not file_path or not os.path.isfile(file_path):
        abort(404)

    data_version = str(current_app.config.get("DATA_VERSION") or "").strip()
    request_version = request.args.get("v", "").strip()
    has_current_version = bool(data_version and request_version == data_version)
    max_age = int(current_app.config.get("GEOJSON_CACHE_MAX_AGE_SECONDS", 31536000))

    accepts_gzip = "gzip" in request.headers.get("Accept-Encoding", "").lower()
    if has_current_version and accepts_gzip:
        with open(file_path, "rb") as f:
            compressed = gzip.compress(f.read(), compresslevel=6)
        response = current_app.response_class(
            compressed,
            mimetype="application/geo+json",
        )
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Vary"] = "Accept-Encoding"
        response.headers["Cache-Control"] = f"public, max-age={max_age}, immutable"
        return response

    response = send_from_directory(
        geo_dir,
        filename,
        max_age=max_age if has_current_version else 0,
    )
    response.headers["Vary"] = "Accept-Encoding"
    if has_current_version:
        response.headers["Cache-Control"] = f"public, max-age={max_age}, immutable"
    else:
        response.headers["Cache-Control"] = "no-cache"
    return response


@home.route("/api/home-highlights")
def home_highlights():
    """
    Homepage highlight cards.
    """
    try:
        metrics = _get_state_db().get_highlight_metrics()

        last_updated = None
        db_path = current_app.config.get("DATABASE_PATH") or "weeds.db"
        absolute_db_path = db_path if os.path.isabs(db_path) else os.path.abspath(db_path)
        if os.path.exists(absolute_db_path):
            last_updated = datetime.fromtimestamp(os.path.getmtime(absolute_db_path)).isoformat()

        override_country = current_app.config.get("LATEST_COUNTRY_NAME")
        if override_country:
            latest_country_name = override_country
            latest_country_region = override_country  # use country as link target
            latest_country_regions = metrics.get("latest_country_regions", 0) or 1
        else:
            latest_country_name = metrics.get("latest_country")
            latest_country_region = metrics.get("latest_country_region") or latest_country_name
            latest_country_regions = metrics.get("latest_country_regions", 0) or 1

        return jsonify(
            {
                "stats": {
                    "species": metrics.get("species_count", 0),
                    "jurisdictions": metrics.get("jurisdiction_count", 0),
                },
                "latestCountry": {
                    "name": latest_country_name,
                    "jurisdictions": latest_country_regions,
                    # home_highlights.js expects "stateName" (we'll supply region)
                    "stateName": latest_country_region,
                },
                "topSpecies": metrics.get("top_species"),
                "topJurisdiction": metrics.get("top_jurisdiction"),
                "lastUpdated": last_updated,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error building home highlights: {e}")
        return jsonify({"error": "Failed to load highlights"}), 500


# ----------------------------
# Species routes
# ----------------------------
@species.route("/")
def index():
    return render_template("species.html")


@species.route("/api/search")
def search_species():
    query = request.args.get("q", "")
    results = _get_species_db().search_weeds(query)
    return jsonify(results)


@species.route("/api/by-species-id/<species_id>")
def species_by_id(species_id: str):
    result = _get_species_db().get_species_by_id(species_id)
    if not result:
        return jsonify({"error": "Species not found"}), 404
    return jsonify(result)


@species.route("/api/weed-states/by-key/<int:usage_key>")
def weed_states_by_key(usage_key: int):
    """
    Returns regulations grouped by:
      - country for region/national
      - jurisdiction_group (e.g. EU) for international
    """
    try:
        regulations_by_group = _get_species_db().get_states_by_usage_key(usage_key)
        return jsonify(regulations_by_group)
    except Exception as e:
        current_app.logger.error(f"Error fetching states for usage key {usage_key}: {str(e)}")
        return jsonify({"error": "Failed to fetch states"}), 500


@species.route("/api/weed-states/by-species-id/<species_id>")
def weed_states_by_species_id(species_id: str):
    """
    Returns regulations for one stable species row. GBIF usage keys are not
    unique in the v1.1 data, so species search uses species_id for lookups.
    """
    try:
        regulations_by_group = _get_species_db().get_states_by_species_id(species_id)
        return jsonify(regulations_by_group)
    except Exception as e:
        current_app.logger.error(f"Error fetching states for species ID {species_id}: {str(e)}")
        return jsonify({"error": "Failed to fetch states"}), 500


# ----------------------------
# Blog routes
# ----------------------------
@blog.route("/")
def index():
    tag = request.args.get("tag")
    posts = blog_generator.get_posts_by_tag(tag) if tag else blog_generator.blog_posts

    return render_template(
        "blog.html",
        blog_posts=posts,
        all_tags=blog_generator.tags,
        current_tag=tag,
        title="Blog" if not tag else f"Blog - {tag}",
        description="Latest updates about regulated weeds",
    )


@blog.route("/<slug>")
def post(slug):
    post = blog_generator.get_post_by_slug(slug)
    if post:
        return render_template("blog_post.html", post=post, title=post["title"])
    return "Post not found", 404


# ----------------------------
# Method routes
# ----------------------------
@method.route("/")
def index():
    try:
        sources = _get_state_db().get_method_sources()
    except Exception as e:
        current_app.logger.error(f"Error loading methodology sources from database: {e}")
        return render_template("method.html", sources=[])

    return render_template("method.html", sources=sources)


# ----------------------------
# API page routes
# ----------------------------
def _safe_api_next_path(value: str) -> str:
    parsed = urlparse(value or "")
    if parsed.scheme or parsed.netloc:
        return url_for("api_page.portal")
    if not parsed.path.startswith("/api"):
        return url_for("api_page.portal")
    return parsed.path or url_for("api_page.portal")


def _api_portal_configured() -> bool:
    email = (current_app.config.get("API_PORTAL_EMAIL") or "").strip()
    password = current_app.config.get("API_PORTAL_PASSWORD") or ""
    password_hash = current_app.config.get("API_PORTAL_PASSWORD_HASH") or ""
    return bool(email and (password or password_hash))


def _api_portal_credentials_valid(email: str, password: str) -> bool:
    expected_email = (current_app.config.get("API_PORTAL_EMAIL") or "").strip().lower()
    if not expected_email or not hmac.compare_digest(email, expected_email):
        return False

    password_hash = current_app.config.get("API_PORTAL_PASSWORD_HASH") or ""
    if password_hash:
        return check_password_hash(password_hash, password)

    expected_password = current_app.config.get("API_PORTAL_PASSWORD") or ""
    if not expected_password:
        return False
    return hmac.compare_digest(password, expected_password)


def _api_demo_rate_limit() -> str:
    return current_app.config.get("API_DEMO_RATE_LIMIT", "30 per hour")


def _api_demo_string(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _api_demo_payload():
    incoming = request.get_json(silent=True) or {}
    if not isinstance(incoming, dict):
        incoming = {}

    ship_to = incoming.get("ship_to")
    if not isinstance(ship_to, dict):
        ship_to = {}

    plant_query = _api_demo_string(incoming.get("plant_query") or incoming.get("plant"), 200)
    country = _api_demo_string(ship_to.get("country") or incoming.get("country"), 64)
    region = _api_demo_string(
        ship_to.get("region") or incoming.get("region") or incoming.get("state"),
        64,
    )
    return plant_query, country, region


@api_page.route("")
def api_index():
    return render_template(
        "api.html",
        api_service_base_url=current_app.config.get("API_SERVICE_BASE_URL", "").rstrip("/"),
    )


@api_page.route("/login", methods=["GET", "POST"])
def login():
    next_path = _safe_api_next_path(request.values.get("next") or url_for("api_page.portal"))
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if _api_portal_credentials_valid(email, password):
            session["api_portal_email"] = email
            session["api_portal_org"] = current_app.config.get("API_PORTAL_ORG")
            session["api_portal_plan"] = current_app.config.get("API_PORTAL_PLAN")
            return redirect(next_path)
        error = "The email or password was not recognized."

    return render_template(
        "api_login.html",
        error=error,
        next_path=next_path,
        portal_configured=_api_portal_configured(),
    )


@api_page.route("/logout", methods=["POST"])
def logout():
    session.pop("api_portal_email", None)
    session.pop("api_portal_org", None)
    session.pop("api_portal_plan", None)
    return redirect(url_for("api_page.api_index"))


@api_page.route("/demo/regulatory-check", methods=["POST"])
@limiter.limit(_api_demo_rate_limit)
def demo_regulatory_check():
    plant_query, country, region = _api_demo_payload()
    if not plant_query:
        return jsonify({"error": "plant_query is required"}), 400
    if not country:
        return jsonify({"error": "ship_to.country is required"}), 400

    base_url = (current_app.config.get("API_SERVICE_BASE_URL") or "").rstrip("/")
    if not base_url:
        return jsonify(
            {
                "error": (
                    "API service base URL is not configured. Set API_SERVICE_BASE_URL "
                    "to the v1 API host, for example http://127.0.0.1:8001 in local preview."
                )
            }
        ), 500

    ship_to = {"country": country}
    if region:
        ship_to["region"] = region

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    demo_token = current_app.config.get("API_DEMO_TOKEN") or ""
    if demo_token:
        headers["Authorization"] = f"Bearer {demo_token}"

    upstream_url = f"{base_url}/v1/regulatory-check"
    try:
        upstream_response = http_requests.post(
            upstream_url,
            json={"plant_query": plant_query, "ship_to": ship_to},
            headers=headers,
            timeout=max(1, int(current_app.config.get("API_DEMO_TIMEOUT_SECONDS", 8))),
        )
    except http_requests.RequestException as exc:
        current_app.logger.warning("API demo request failed: %s", exc)
        return jsonify({"error": "The API service is not reachable right now."}), 502

    try:
        payload = upstream_response.json()
    except ValueError:
        current_app.logger.warning(
            "API demo received non-JSON response from %s with status %s",
            upstream_url,
            upstream_response.status_code,
        )
        return jsonify({"error": "The API service returned an unreadable response."}), 502

    if upstream_response.status_code in {401, 403}:
        return jsonify(
            {
                "error": "Demo API access is not configured.",
                "upstream_status": upstream_response.status_code,
            }
        ), 502
    if upstream_response.status_code >= 500:
        return jsonify(
            {
                "error": "The API service returned an upstream error.",
                "upstream_status": upstream_response.status_code,
            }
        ), 502
    return jsonify(payload), upstream_response.status_code


@api_page.route("/portal")
def portal():
    email = session.get("api_portal_email")
    if not email:
        return redirect(url_for("api_page.login", next=url_for("api_page.portal")))

    return render_template(
        "api_portal.html",
        email=email,
        org=session.get("api_portal_org") or current_app.config.get("API_PORTAL_ORG"),
        plan=session.get("api_portal_plan") or current_app.config.get("API_PORTAL_PLAN"),
        api_service_base_url=current_app.config.get("API_SERVICE_BASE_URL", "").rstrip("/"),
    )


@api_page.route("/docs")
def docs():
    return render_template("api_docs.html")


@api_page.route("/openapi.json")
def openapi_json():
    spec_path = current_app.config.get("API_OPENAPI_PATH")
    if not spec_path:
        return jsonify({"error": "OpenAPI document is not configured"}), 500
    if not os.path.isabs(spec_path):
        spec_path = os.path.abspath(spec_path)
    if not os.path.isfile(spec_path):
        return jsonify({"error": "OpenAPI document not found"}), 404
    with open(spec_path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


# ----------------------------
# About routes
# ----------------------------
@about.route("/")
def index():
    return render_template("about.html")


@about.route("/contact", methods=["POST"])
@limiter.limit("5 per hour")
def contact():
    # Honeypot bot field
    if request.form.get("website"):
        return redirect(url_for("about.index"))

    # reCAPTCHA
    if not recaptcha.verify():
        flash("Please complete the reCAPTCHA verification.", "error")
        return redirect(url_for("about.index"))

    name = request.form.get("name")
    email = request.form.get("email")
    subject_type = request.form.get("subject")
    message_text = request.form.get("message")

    if not all([name, email, subject_type, message_text]):
        flash("All fields are required", "error")
        return redirect(url_for("about.index"))

    subject_map = {
        "general": "General Inquiry",
        "data": "Data Correction Request",
        "collaboration": "Collaboration Request",
        "other": "Other Inquiry",
    }
    email_subject = f"[Regulated Plants] {subject_map.get(subject_type, 'Contact Form')}"

    email_body = f"""
You have received a new message from the Regulated Plants contact form:

Name: {name}
Email: {email}
Subject: {subject_map.get(subject_type, 'Not specified')}

Message:
{message_text}
""".strip()

    try:
        send_email(
            current_app.config,
            email_subject,
            current_app.config.get("CONTACT_EMAIL"),
            email_body,
            reply_to=email,
        )
        flash("Thank you for your message! We will get back to you soon.", "success")
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        flash("There was an issue sending your message. Please try again later.", "error")

    return redirect(url_for("about.index"))


# ----------------------------
# Debug route
# ----------------------------
@home.route("/debug/table-check")
def check_tables():
    if current_app.config.get("DEBUG") is not True:
        abort(404)

    conn = _get_state_db().get_connection()
    try:
        expected = ["plants", "jurisdictions", "regulations"]
        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name IN ('plants', 'jurisdictions', 'regulations')
            ORDER BY name
            """
        ).fetchall()

        available = {row["name"] for row in tables}
        counts = {}
        for table_name in expected:
            if table_name not in available:
                counts[table_name] = 0
                continue
            row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
            counts[table_name] = row["count"] if row else 0

        return jsonify({"tables_found": [dict(t) for t in tables], "row_counts": counts})
    finally:
        conn.close()


@home.route("/api/data-status")
def data_status():
    if current_app.config.get("DEBUG") is not True:
        abort(404)

    db_path = current_app.config.get("DATABASE_PATH")
    geojson_dir = current_app.config.get("GEOJSON_DIR")
    manifest_path = current_app.config.get("DATA_MANIFEST_PATH")

    return jsonify(
        {
            "mode": current_app.config.get("DATA_MODE"),
            "version": current_app.config.get("DATA_VERSION"),
            "manifestPath": manifest_path,
            "database": {"path": db_path, "exists": bool(db_path and os.path.exists(db_path))},
            "geojson": {
                "dir": geojson_dir,
                "exists": bool(geojson_dir and os.path.isdir(geojson_dir)),
            },
        }
    )
