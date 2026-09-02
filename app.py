from dotenv import load_dotenv
load_dotenv()
import os

from flask import Flask, request, jsonify, render_template
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

    if not app.debug:
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000

    db.init_app(app)
    init_oauth(app)
    csrf.init_app(app)

    app.config["RATELIMIT_STORAGE_URI"] = app.config["RATELIMIT_STORAGE_URL"]
    limiter.init_app(app)

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    csrf.exempt(api_bp)
    csrf.exempt("auth.google_callback")
    csrf.exempt("auth.login")
    csrf.exempt("auth.register")
    csrf.exempt("auth.sso_verify")
    csrf.exempt("auth.markkundo_sso")

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if request.accept_mimetypes.accept_json:
            return jsonify({"error": "CSRF token missing or invalid."}), 400
        return "CSRF token missing or invalid.", 400

    @app.errorhandler(403)
    def forbidden(e):
        if request.accept_mimetypes.accept_json:
            return jsonify({"error": "Access denied."}), 403
        return "Access denied.", 403

    @app.errorhandler(404)
    def not_found(e):
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({"error": "Not found."}), 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({"error": "Internal server error."}), 500
        return render_template("500.html"), 500

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

        if request.path.startswith("/static/"):
            if not app.debug:
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif not app.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    @app.template_filter("format_desktop_name")
    def format_desktop_name_filter(name):
        if not name:
            return ""
        parts = name.split()
        if len(parts) > 1:
            i = len(parts) - 1
            while i >= 0 and len(parts[i]) <= 1:
                i -= 1
            initials_start = i + 1
            if initials_start < len(parts):
                initials = "".join(parts[initials_start:])
                parts = parts[:initials_start] + [initials]
        cleaned_name = " ".join(parts)

        if len(cleaned_name) >= 20:
            if len(parts) > 1:
                first_part = " ".join(parts[:-1])
                last_part = parts[-1]
                from markupsafe import Markup, escape
                return Markup(f'{escape(first_part)}<br class="desktop-only-br"> {escape(last_part)}')
        return cleaned_name

    def ensure_schema() -> None:
        inspector = inspect(db.engine)
        if "users" not in inspector.get_table_names():
            db.create_all()

        index_statements = [
            "CREATE INDEX IF NOT EXISTS ix_enrollments_user_semester ON enrollments (user_id, semester);",
            "CREATE INDEX IF NOT EXISTS ix_subjects_sem_elective ON subjects (semester, is_elective, is_active);",
            "CREATE INDEX IF NOT EXISTS ix_subjects_semester ON subjects (semester);",
            "CREATE INDEX IF NOT EXISTS ix_announcements_created_at ON announcements (created_at);",
            "CREATE INDEX IF NOT EXISTS ix_users_semester ON users (semester);",
            "CREATE INDEX IF NOT EXISTS ix_users_created_at ON users (created_at);",
            "CREATE INDEX IF NOT EXISTS ix_users_reset_token_hash ON users (reset_token_hash);",
        ]
        for stmt in index_statements:
            try:
                db.session.execute(db.text(stmt))
                db.session.commit()
            except Exception:
                db.session.rollback()

        if db.engine.dialect.name == "postgresql":
            for table, pk in [
                ("subjects", "subject_id"),
                ("users", "id"),
                ("enrollments", "id"),
                ("marks", "id"),
                ("announcements", "id"),
            ]:
                try:
                    db.session.execute(db.text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), COALESCE((SELECT MAX({pk}) FROM {table}), 1));"
                    ))
                    db.session.commit()
                except Exception:
                    db.session.rollback()

    with app.app_context():
        ensure_schema()

    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        print("Database tables created.")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
