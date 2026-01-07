# __init__.py
from flask import Flask
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from app.config import Config
from app.utils.data_manager import DataManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.utils.custom_recaptcha import CustomReCaptcha


mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
recaptcha = CustomReCaptcha()

__all__ = ['mail', 'csrf', 'limiter', 'recaptcha', 'create_app']

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Mail configuration
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = app.config.get('EMAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = app.config.get('EMAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = app.config.get('EMAIL_USERNAME')
    
    # reCAPTCHA configuration
    app.config['RECAPTCHA_SITE_KEY'] = app.config.get('RECAPTCHA_SITE_KEY')
    app.config['RECAPTCHA_SECRET_KEY'] = app.config.get('RECAPTCHA_SECRET_KEY')
    
    # Initialize extensions
    mail.init_app(app)
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
    from app.views import home, species, blog, method, about
    app.register_blueprint(home)
    app.register_blueprint(species)
    app.register_blueprint(blog)
    app.register_blueprint(method) 
    app.register_blueprint(about)

    return app
