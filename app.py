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
from dotenv import load_dotenv
load_dotenv()
import os

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import inspect

from config import Config
from models import db
from routes import api_bp, auth_bp, pages_bp
from routes.admin import admin_bp
from routes.auth import init_oauth, init_limiter



def create_app(config_class=Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    init_oauth(app)

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "100 per hour"],
        storage_uri=app.config["RATELIMIT_STORAGE_URL"],
        strategy=app.config["RATELIMIT_STRATEGY"],
        enabled=app.config["RATELIMIT_ENABLED"],
    )
    init_limiter(limiter)

    # Apply rate limiting to login route (after blueprint registration)
    # Rate limiting is applied via the @limiter.limit decorator in the route itself

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

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

    def ensure_schema() -> None:
        """Create missing tables when a local SQLite database is fresh."""
        inspector = inspect(db.engine)
        if "users" not in inspector.get_table_names():
            db.create_all()

    # ── Create tables on first run ────────────────────────────────────────────
    with app.app_context():
        ensure_schema()

    @app.before_request
    def ensure_schema_before_request():
        ensure_schema()

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables for the configured database."""
        db.create_all()
        print("Database tables created.")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, host="0.0.0.0", port=5000)
