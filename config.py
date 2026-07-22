"""
config.py — Application configuration.

All tuneable values are read from environment variables (set in .env).
Never hard-code secrets here; this file is safe to commit to version control.
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


class Config:
    # ── Flask ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-only-insecure-key")

    # ── Database ──────────────────────────────────────────────────────────────
    # Defaults to SQLite for local development.
    # Set DATABASE_URL to a PostgreSQL URI for production (AWS RDS).
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'padikkunnundo.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # ── Dev mode — bypass authentication ─────────────────────────────────────
    # Set to True to skip Google OAuth entirely.
    # A local dev user is auto-created on first run.
    # Flip to False when real OAuth credentials are in .env.
    DEV_BYPASS_AUTH: bool = os.environ.get("DEV_BYPASS_AUTH", "false").lower() == "true"
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
    # Secret used to sign cross-platform SSO tokens (e.g. for MCQ quiz site).
    # MUST match JWT_SECRET on every sister platform. Override via env var.
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-only-jwt-secret")
    # Short-lived SSO handoff tokens — 5 minutes is intentionally tight because
    # the token travels in a URL query parameter and could appear in server logs.
    SSO_TOKEN_EXPIRY_SECONDS: int = int(os.environ.get("SSO_TOKEN_EXPIRY_SECONDS", "300"))

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    # Rate limit for login attempts: 5 failed attempts per 15 minutes
    RATELIMIT_ENABLED: bool = os.environ.get("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_STORAGE_URL: str = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_STRATEGY: str = "fixed-window"


    RATELIMIT_STORAGE_URL: str = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_STRATEGY: str = "fixed-window"
    RATELIMIT_ENABLED: bool = True

    # ── CSRF Protection ─────────────────────────────────────────────────────────
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = 3600  # 1 hour
    # ── Email / Password Reset (Resend API) ───────────────────────────────────
    RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "")
    MAIL_FROM: str = os.environ.get("MAIL_FROM", "noreply@padikkunnundo.app")
    # Password reset token expiry in seconds (default: 1 hour)
    RESET_TOKEN_EXPIRY_SECONDS: int = int(os.environ.get("RESET_TOKEN_EXPIRY_SECONDS", "3600"))

    # ── Sister Platform URLs ──────────────────────────────────────────────────
    PYQPORTAL_URL: str = "https://pyqportal.app"
    MCQ_QUIZ_URL: str = "https://mcq-portal-ldf6.onrender.com/"
    PLACEMENT_URL: str = "https://lab.pyqportal.app"
    TOPIC_URL: str = "https://passavam.onrender.com"
    MARK_ANALYSER_URL: str = os.environ.get("MARKKUNDO_URL", "https://markkundo.app")
    DOUBTUNDO_URL: str = os.environ.get("DOUBTUNDO_URL", "https://doubtundo.onrender.com/")

    # ── Cross-App SSO (markkundo) ───────────────────────────────────────────────
    # Shared secret used to sign JWT tokens for markkundo SSO.
    # MUST match the SSO_SECRET in markkundo's .env.
    SSO_SECRET: str = os.environ.get("SSO_SECRET", "dev-only-sso-secret")
    # Short-lived SSO token expiry (seconds) — 5 min intentionally tight
    MARKKUNDO_SSO_EXPIRY_SECONDS: int = 300

