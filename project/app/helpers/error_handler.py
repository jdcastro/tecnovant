"""
Custom error handler module for Yet Another Flask Survival Kit (YAFSK)

Author:
    Johnny De Castro <j@jdcastro.co>

Copyright:
    (c) 2024 - 2025 Johnny De Castro. All rights reserved.

License:
    Apache License 2.0 - http://www.apache.org/licenses/LICENSE-2.0

"""

# Python standard library imports
import logging
from logging.handlers import RotatingFileHandler
import traceback

# Third party imports
from flask import render_template
from werkzeug.exceptions import HTTPException


def setup_logging(log_file="errors.log"):
    """
    Configures logging with a rotating file handler.

    Args:
        log_file (str): Path to the log file.

    Returns:
        logging.Logger: Configured logger instance.
    """
    handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,  # 1MB per file
        backupCount=10,  # Keep up to 10 backup files
    )
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger = logging.getLogger(__name__)
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    return logger


def error_handler(app, logger):
    """
    Registers a global error handler for the Flask app.

    Args:
        app (Flask): The Flask application instance.
        logger (logging.Logger): Configured logger instance.
    """

    @app.errorhandler(Exception)
    def handle_exception(e):
        """
        Handles global exceptions and logs them.

        Args:
            e (Exception): The exception instance.

        Returns:
            tuple: Rendered template and HTTP status code.
        """
        logger.error(f"Error occurred: {str(e)}\nTraceback: {traceback.format_exc()}")

        if isinstance(e, HTTPException):
            error_code = e.code
            error_description = e.name
            error_details = str(e)
        else:
            error_code = 500
            error_description = "Internal Server Error"
            error_details = "An unhandled exception occurred."

        return (
            render_template(
                "layouts/error_handler.j2",
                e=error_code,
                e_description=error_description,
                e_details=error_details,
            ),
            error_code,
        )
