from flask import Flask
from .api.routes import api_bp
from .web.routes import web_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = "supersecretkey"
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(web_bp)
    return app