"""
app.py — Flask application factory.

Usage:
    # Development
    python app.py

    # Or with flask CLI
    flask run --debug

One-time setup:
    python seed.py     ← populates the subjects table
"""

import os

from dotenv import load_dotenv
from flask import Flask

from config import Config
from models import db
from routes import api_bp, auth_bp, pages_bp
from routes.auth import init_oauth

load_dotenv()


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    init_oauth(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    # ── Error handlers ────────────────────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        from flask import jsonify, request
        if request.accept_mimetypes.accept_json:
            return jsonify({"error": "Access denied."}), 403
        return "Access denied.", 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import jsonify, request
        if request.accept_mimetypes.accept_json:
            return jsonify({"error": "Not found."}), 404
        return "Page not found.", 404

    # ── Create tables on first run ────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
