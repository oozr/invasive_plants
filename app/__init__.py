# Updated __init__.py
from flask import Flask
from app.utils.database_retrieve import WeedDatabase

db = WeedDatabase()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key-here'

    from app.views import home, species, blog, about
    app.register_blueprint(home)
    app.register_blueprint(species)
    app.register_blueprint(blog)
    app.register_blueprint(about)

    return app