"""
config.py — Application configuration.

All tuneable values are read from environment variables (set in .env).
Never hard-code secrets here; this file is safe to commit to version control.
"""

import os


class Config:
    # ── Flask ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-only-insecure-key")

    # ── Database ──────────────────────────────────────────────────────────────
    # Defaults to SQLite for local development.
    # Set DATABASE_URL to a PostgreSQL URI for production (AWS RDS).
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", "sqlite:///padikkunnundo.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # ── Dev mode — bypass authentication ─────────────────────────────────────
    # Set to True to skip Google OAuth entirely.
    # A local dev user is auto-created on first run.
    # Flip to False when real OAuth credentials are in .env.
    DEV_BYPASS_AUTH: bool = os.environ.get("DEV_BYPASS_AUTH", "true").lower() != "false"

    # ── Google OAuth 2.0 ─────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    # ── College Domain Restriction ────────────────────────────────────────────
    # Only accounts on this domain are allowed through after OAuth.
    COLLEGE_DOMAIN: str = os.environ.get("COLLEGE_DOMAIN", "mariancollege.org")
    COLLEGE_NAME: str = "Marian College Kuttikkanam"

    # ── Session / JWT ─────────────────────────────────────────────────────────
    SESSION_TOKEN_EXPIRY_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"

    # ── Sister Platform URLs ──────────────────────────────────────────────────
    PYQPORTAL_URL: str = "https://pyqportal.app"
    MCQ_QUIZ_URL: str = "https://quiz.pyqportal.app"
    PLACEMENT_URL: str = "https://placement.pyqportal.app"
