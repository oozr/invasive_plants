# app/views.py
import csv
import os
from datetime import datetime
from flask import Blueprint, render_template, jsonify, current_app, request, flash, url_for, redirect
from flask_mail import Message

from app import mail, limiter, recaptcha
from app.utils.state_database import StateDatabase
from app.utils.species_database import SpeciesDatabase
from app.utils.generate_blog import BlogGenerator
from app.config import Config

# Databases
state_db = StateDatabase(db_path=Config.DATABASE_PATH)
species_db = SpeciesDatabase(db_path=Config.DATABASE_PATH)

# Blueprints
home = Blueprint("home", __name__)
species = Blueprint("species", __name__, url_prefix="/species")
blog = Blueprint("blog", __name__, url_prefix="/blog")
method = Blueprint("method", __name__, url_prefix="/method")
about = Blueprint("about", __name__, url_prefix="/about")

# Blog generator
blog_generator = BlogGenerator()


# ----------------------------
# Helpers
# ----------------------------
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
    return render_template("home.html")


@home.route("/robots.txt")
def robots_txt():
    return current_app.send_static_file("robots.txt")


@home.route("/api/region-weed-counts")
def region_weed_counts():
    """
    Returns list of {country, region, count}.
    Used to colour the map.
    """
    include_region, include_national, include_international = _toggle_params()
    counts = state_db.get_region_weed_counts(
        include_region=include_region,
        include_national=include_national,
        include_international=include_international,
    )
    return jsonify(counts)


@home.route("/api/region")
def region_weeds():
    """
    Returns weeds for a specific (country, region).
    Called by map click.

    Query args:
      country=<country name>
      region=<region name>
      includeRegion/includeNational/includeInternational
    """
    country = request.args.get("country", "").strip()
    region = request.args.get("region", "").strip()
    if not country or not region:
        return jsonify({"error": "country and region are required"}), 400

    include_region, include_national, include_international = _toggle_params()
    weeds = state_db.get_weeds_for_region(
        country=country,
        region=region,
        include_region=include_region,
        include_national=include_national,
        include_international=include_international,
    )
    has_any_data = state_db.country_has_data(country)
    return jsonify({"weeds": weeds, "has_any_data": has_any_data})


@home.route("/api/geojson-files")
def geojson_files():
    """
    Return a list of GeoJSON filenames in static/data/geographic.
    map.js will call this to know which files to load.
    """
    try:
        static_folder = current_app.static_folder
        geo_dir = os.path.join(static_folder, "data", "geographic")

        files = []
        if os.path.isdir(geo_dir):
            for fname in os.listdir(geo_dir):
                if fname.lower().endswith(".geojson"):
                    files.append(fname)

        files.sort()
        return jsonify(files)
    except Exception as e:
        current_app.logger.error(f"Error listing geojson files: {e}")
        return jsonify({"error": "Failed to list geojson files"}), 500


@home.route("/api/home-highlights")
def home_highlights():
    """
    Homepage highlight cards.
    """
    try:
        metrics = state_db.get_highlight_metrics()

        last_updated = None
        db_path = Config.DATABASE_PATH or "weeds.db"
        absolute_db_path = db_path if os.path.isabs(db_path) else os.path.abspath(db_path)
        if os.path.exists(absolute_db_path):
            last_updated = datetime.fromtimestamp(os.path.getmtime(absolute_db_path)).isoformat()

        latest_country_name = (Config.LATEST_COUNTRY_NAMES[0] if Config.LATEST_COUNTRY_NAMES else None) or metrics.get("latest_country")
        latest_country_region = Config.LATEST_COUNTRY_REGION or metrics.get("latest_country_region")
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
    results = species_db.search_weeds(query)
    return jsonify(results)


@species.route("/api/weed-states/by-key/<int:usage_key>")
def weed_states_by_key(usage_key: int):
    """
    Returns regulations grouped by:
      - country for region/national
      - jurisdiction_group (e.g. EU) for international
    """
    try:
        regulations_by_group = species_db.get_states_by_usage_key(usage_key)
        return jsonify(regulations_by_group)
    except Exception as e:
        current_app.logger.error(f"Error fetching states for usage key {usage_key}: {str(e)}")
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
    sources = []
    csv_path = os.path.join(current_app.root_path, "static", "data", "regulatory_sources.csv")

    try:
        with open(csv_path, "r", encoding="utf-8-sig") as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                sources.append(
                    {
                        "country": row.get("country", "Unknown"),
                        "name": row.get("state_province", "Unknown"),
                        "authority": row.get("authority_name", "Unknown"),
                        "source_url": row.get("source_url", "#"),
                        "updated": row.get("last_updated_year", row.get("last_updated", "Unknown")),
                    }
                )
    except Exception as e:
        current_app.logger.error(f"Error reading regulatory_sources.csv: {e}")
        return render_template("method.html", sources=[])

    return render_template("method.html", sources=sources)


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
        msg = Message(
            subject=email_subject,
            recipients=[current_app.config.get("EMAIL_USERNAME")],
            body=email_body,
            reply_to=email,
        )
        mail.send(msg)
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
    conn = state_db.get_connection()
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='weeds'")
        tables = cursor.fetchall()

        row_count = 0
        if tables:
            row_count = conn.execute("SELECT COUNT(*) as count FROM weeds").fetchone()["count"]

        return jsonify({"tables_found": [dict(t) for t in tables], "row_count": row_count})
    finally:
        conn.close()
