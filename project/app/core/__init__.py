from flask import Blueprint

core = Blueprint("core", __name__, url_prefix="/", template_folder="templates")

core_api = Blueprint("core_api", __name__, url_prefix="/api/core")

from . import web_routes, api_routes
