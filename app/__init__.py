from flask import Flask

from .routes.api import api_bp
from .routes.pages import pages_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
    return app

