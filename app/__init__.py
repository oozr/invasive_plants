# __init__.py
from flask import Flask, session
from flask_wtf.csrf import CSRFProtect
from app.config import Config
from app.utils.data_manager import DataManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.utils.custom_recaptcha import CustomReCaptcha


csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
recaptcha = CustomReCaptcha()

__all__ = ['csrf', 'limiter', 'recaptcha', 'create_app']

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # reCAPTCHA configuration
    app.config['RECAPTCHA_SITE_KEY'] = app.config.get('RECAPTCHA_SITE_KEY')
    app.config['RECAPTCHA_SECRET_KEY'] = app.config.get('RECAPTCHA_SECRET_KEY')
    
    # Initialize extensions
    csrf.init_app(app)
    limiter.init_app(app)
    recaptcha.init_app(app)

    # Data manager (local sample vs remote production)
    data_manager = DataManager.from_app(app)
    data_manager.ensure_ready()
    app.extensions["data_manager"] = data_manager

    @app.before_request
    def refresh_data_cache():
        data_manager.maybe_refresh()

    # Import and register blueprints
    from app.views import home, species, blog, method, api_page, about
    from app.auth_routes import auth
    app.register_blueprint(home)
    app.register_blueprint(species)
    app.register_blueprint(blog)
    app.register_blueprint(method)
    app.register_blueprint(api_page)
    app.register_blueprint(about)
    app.register_blueprint(auth)

    @app.context_processor
    def inject_auth_state():
        researcher_email = session.get("researcher_email")
        return {
            "researcher_email": researcher_email,
            "researcher_logged_in": bool(researcher_email),
        }

    return app
