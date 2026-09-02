import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


class Config:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-only-insecure-key")

    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'padikkunnundo.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "pool_timeout": 30,
    }

    DEV_BYPASS_AUTH: bool = os.environ.get("DEV_BYPASS_AUTH", "false").lower() == "true"
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    COLLEGE_DOMAIN: str = os.environ.get("COLLEGE_DOMAIN", "mariancollege.org")
    COLLEGE_NAME: str = "Marian College Kuttikkanam"

    SESSION_TOKEN_EXPIRY_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-only-jwt-secret")
    SSO_TOKEN_EXPIRY_SECONDS: int = int(os.environ.get("SSO_TOKEN_EXPIRY_SECONDS", "300"))

    RATELIMIT_ENABLED: bool = os.environ.get("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_STORAGE_URL: str = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_STRATEGY: str = "fixed-window"

    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = 3600

    RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "")
    MAIL_FROM: str = os.environ.get("MAIL_FROM", "noreply@padikkunnundo.app")
    RESET_TOKEN_EXPIRY_SECONDS: int = int(os.environ.get("RESET_TOKEN_EXPIRY_SECONDS", "3600"))

    PYQPORTAL_URL: str = os.environ.get("PYQPORTAL_URL", "https://pyqportal.app")
    MCQ_QUIZ_URL: str = os.environ.get("MCQ_QUIZ_URL", "https://mcq-portal-ldf6.onrender.com/")
    PLACEMENT_URL: str = os.environ.get("PLACEMENT_URL", "https://lab.pyqportal.app")
    TOPIC_URL: str = os.environ.get("TOPIC_URL", "https://passavam.onrender.com")
    MARK_ANALYSER_URL: str = os.environ.get("MARKKUNDO_URL", "https://markkundo.app")
    DOUBTUNDO_URL: str = os.environ.get("DOUBTUNDO_URL", "https://doubtundo.onrender.com/")

    SSO_SECRET: str = os.environ.get("SSO_SECRET", "dev-only-sso-secret")
    MARKKUNDO_SSO_EXPIRY_SECONDS: int = 300
