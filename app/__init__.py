# __init__.py
from flask import Flask
from app.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)  # Use configuration from Config class

    # Import and register blueprints
    from app.views import home, species, blog, about
    app.register_blueprint(home)
    app.register_blueprint(species)
    app.register_blueprint(blog)
    app.register_blueprint(about)

    return app