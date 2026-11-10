"""
WSGI Entry Point for Production Deployment (e.g. Render, Gunicorn).
Exposes the Flask application instance as 'app'.
"""
import sys
import os

# Ensure the project root directory is in the Python search path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app import app
from backend.models.database import init_db

# Ensure database tables and schema exist upon production server launch
try:
    init_db()
except Exception as e:
    import logging
    logging.getLogger("wsgi").warning("Database initialization check during startup: %s", e)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

