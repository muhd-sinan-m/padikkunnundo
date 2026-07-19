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
from flask_wtf.csrf import CSRFProtect, CSRFError
from sqlalchemy import inspect

csrf = CSRFProtect()

from config import Config
from models import db
from routes import api_bp, auth_bp, pages_bp
from routes.admin import admin_bp
from routes.auth import init_oauth, limiter



def create_app(config_class=Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    init_oauth(app)
    csrf.init_app(app)

    # Map custom config key to Flask-Limiter's standard config key
    app.config["RATELIMIT_STORAGE_URI"] = app.config["RATELIMIT_STORAGE_URL"]
    limiter.init_app(app)

    # Apply rate limiting to login route (after blueprint registration)
    # Rate limiting is applied via the @limiter.limit decorator in the route itself

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    # ── CSRF exemptions ───────────────────────────────────────────────────────
    # JSON API endpoints don't use cookie/form sessions — exempt the whole blueprint
    csrf.exempt(api_bp)
    # Google OAuth callback is a redirect from Google, not a form POST
    csrf.exempt("auth.google_callback")
    # Login and register are already protected by rate limiting + domain check +
    # bcrypt — CSRF here would break direct POSTs from non-browser clients.
    csrf.exempt("auth.login")
    csrf.exempt("auth.register")

    # ── Error handlers ────────────────────────────────────────────────────────
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import jsonify, request
        if request.accept_mimetypes.accept_json:
            return jsonify({"error": "CSRF token missing or invalid."}), 400
        return "CSRF token missing or invalid.", 400

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

    @app.after_request
    def add_security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:;"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.template_filter("format_desktop_name")
    def format_desktop_name_filter(name):
        if not name:
            return ""
        if len(name) >= 20:
            parts = name.split()
            if len(parts) > 1:
                first_part = " ".join(parts[:-1])
                last_part = parts[-1]
                from markupsafe import Markup
                return Markup(f'{first_part}<br class="desktop-only-br"> {last_part}')
        return name

    def ensure_schema() -> None:
        """Create missing tables when a local SQLite database is fresh."""
        inspector = inspect(db.engine)
        if "users" not in inspector.get_table_names():
            db.create_all()

    # ── Create tables on first run ────────────────────────────────────────────
    with app.app_context():
        ensure_schema()

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables for the configured database."""
        db.create_all()
        print("Database tables created.")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
