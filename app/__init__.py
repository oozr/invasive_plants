from flask import Flask
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import Config
from app.utils.custom_recaptcha import CustomReCaptcha

# ✅ RELATIVE IMPORT (robust inside the app package)
from .utils.db_bootstrap import ensure_db

mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
recaptcha = CustomReCaptcha()

__all__ = ["mail", "csrf", "limiter", "recaptcha", "create_app"]


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ✅ DB bootstrapping must happen before importing views / DB classes
    ensure_db(
        db_path=Config.DATABASE_PATH,
        csv_folder="preprocessing_utils/data",
    )

    # Mail configuration
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = app.config.get("EMAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = app.config.get("EMAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = app.config.get("EMAIL_USERNAME")

    # reCAPTCHA configuration
    app.config["RECAPTCHA_SITE_KEY"] = app.config.get("RECAPTCHA_SITE_KEY")
    app.config["RECAPTCHA_SECRET_KEY"] = app.config.get("RECAPTCHA_SECRET_KEY")

    # Initialize extensions
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    recaptcha.init_app(app)

    # Import and register blueprints
    from app.views import home, species, blog, method, about
    app.register_blueprint(home)
    app.register_blueprint(species)
    app.register_blueprint(blog)
    app.register_blueprint(method)
    app.register_blueprint(about)

    return app
