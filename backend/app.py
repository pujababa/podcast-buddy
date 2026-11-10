import os
from flask import Flask, jsonify, send_from_directory, redirect
from dotenv import load_dotenv

# Load environment variables if .env file exists
load_dotenv()

import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(
    __name__,
    static_folder=STATIC_DIR,
    static_url_path="/static"
)


# Register API blueprints
from backend.routes.news import news_bp
from backend.routes.episodes import episodes_bp

app.register_blueprint(news_bp)
app.register_blueprint(episodes_bp)

@app.after_request
def add_cors_headers(response):
    """Enable basic CORS headers and disable caching for development flexibility."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/", methods=["GET"])
def index():
    """Redirect root endpoint to the frontend application."""
    return redirect("/app", code=302)

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint returning service status."""
    return jsonify({
        "app": "Podcast Buddy",
        "status": "healthy"
    }), 200

@app.route("/app", methods=["GET"])
@app.route("/ui", methods=["GET"])
@app.route("/index.html", methods=["GET"])
def serve_ui():
    """Serve the frontend homepage during development."""
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/frontend/<path:filename>", methods=["GET"])
def serve_frontend_files(filename):
    """Serve any frontend assets or pages directly if requested."""
    return send_from_directory(FRONTEND_DIR, filename)

if __name__ == "__main__":
    from backend.models.database import init_db
    init_db()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    print(f"Podcast Buddy backend: http://{host}:{port}")
    print(f"Podcast Buddy frontend: http://{host}:{port}/app")
    app.run(host=host, port=port, debug=debug, threaded=True)
