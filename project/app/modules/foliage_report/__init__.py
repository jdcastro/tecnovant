from flask import Blueprint

foliage_report = Blueprint("foliage_report", __name__,
                            url_prefix="/dashboard/foliage_report",
                            template_folder="templates")
foliage_report_api = Blueprint("foliage_report_api", __name__,
                               url_prefix="/api/foliage/report")

from . import web_routes, api_routes
