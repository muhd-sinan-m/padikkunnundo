"""
routes/auth.py — Google OAuth 2.0 flow and session management.

Implements Section 5 of the PRD:
  • Google OAuth only (no email/password).
  • Domain restriction enforced immediately after the callback,
    before any user record is created or loaded.
  • JWT issued on success, stored in an httpOnly cookie.
  • 30-day session expiry (Section 5.3).
  • Logout immediately clears the session.

DEV_BYPASS_AUTH mode (config.DEV_BYPASS_AUTH = True):
  Skips all of the above.  A local dev user is auto-created in the DB on
  first request and returned directly from get_current_user().
  Flip DEV_BYPASS_AUTH to False and add real credentials when ready for OAuth.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from authlib.integrations.flask_client import OAuth
from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from models import Enrollment, Mark, Subject, User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

oauth = OAuth()

# ── Dev user constants ────────────────────────────────────────────────────────
_DEV_EMAIL    = "dev@mariancollege.org"
_DEV_NAME     = "Muhammed Sinan M"
_DEV_SEMESTER = 3


def init_oauth(app) -> None:
    """Bind authlib OAuth to the Flask app and register the Google provider."""
    oauth.init_app(app)
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        client_kwargs={"scope": "openid email profile"},
    )


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _create_jwt(user_id: int) -> str:
    expiry_days = current_app.config["SESSION_TOKEN_EXPIRY_DAYS"]
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=expiry_days),
    }
    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def _decode_jwt(token: str) -> dict | None:
    """Decode and validate the JWT.  Returns None on any failure."""
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.PyJWTError:
        return None


# ── Dev bypass helper ─────────────────────────────────────────────────────────

def _get_or_create_dev_user() -> User:
    """
    Return the local dev user, creating it on first call.
    Pre-onboarded at Semester 3 with all core subjects enrolled.
    """
    user = User.query.filter_by(email=_DEV_EMAIL).first()
    if user:
        return user

    user = User(
        email=_DEV_EMAIL,
        name=_DEV_NAME,
        semester=_DEV_SEMESTER,
        course="BCA Cyber Security",
        college="Marian College Kuttikkanam",
        is_onboarded=True,
    )
    db.session.add(user)
    db.session.flush()  # get user.id before committing

    # Auto-enroll in all core subjects for Semester 3.
    core_subjects = Subject.query.filter_by(
        semester=_DEV_SEMESTER, is_elective=False
    ).all()
    for subj in core_subjects:
        db.session.add(Enrollment(
            user_id=user.id,
            subject_id=subj.subject_id,
            semester=_DEV_SEMESTER,
        ))
        db.session.add(Mark(user_id=user.id, subject_id=subj.subject_id))

    db.session.commit()
    return user


# ── Public auth helpers ───────────────────────────────────────────────────────

def get_current_user() -> User | None:
    """
    Return the authenticated user for this request.

    DEV_BYPASS_AUTH = True  → always returns the local dev user (auto-created).
    DEV_BYPASS_AUTH = False → reads and validates the JWT from the cookie.
    """
    if current_app.config.get("DEV_BYPASS_AUTH"):
        return _get_or_create_dev_user()

    token = request.cookies.get("session_token")
    if not token:
        return None
    payload = _decode_jwt(token)
    if not payload:
        return None
    return db.session.get(User, int(payload["sub"]))


def login_required(f):
    """
    Decorator that ensures the request is authenticated.

    DEV_BYPASS_AUTH = True  → always passes through (no redirect to login).
    DEV_BYPASS_AUTH = False → redirects to /login (or 401 for JSON requests).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            if request.accept_mimetypes.accept_json:
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("pages.login"))
        return f(*args, **kwargs)
    return decorated


# ── OAuth routes (only active when DEV_BYPASS_AUTH = False) ──────────────────

@auth_bp.route("/google/login")
def google_login():
    """Redirect the browser to Google's OAuth consent screen."""
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    """
    Handle the OAuth callback from Google.

    Section 5.2 — Domain restriction:
      Domain validation happens immediately after the OAuth callback,
      before any profile is created.
    """
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        return render_template(
            "login.html",
            error="Authentication failed. Please try again.",
        ), 400

    userinfo = token.get("userinfo") or {}
    email: str = userinfo.get("email", "")
    name: str  = userinfo.get("name", "")

    college_domain: str = current_app.config["COLLEGE_DOMAIN"]
    if not email.endswith(f"@{college_domain}"):
        return render_template(
            "login.html",
            error=(
                f"Only {current_app.config['COLLEGE_NAME']} accounts "
                f"(@{college_domain}) are permitted. "
                "Personal Gmail addresses are not accepted."
            ),
        ), 403

    user = User.query.filter_by(email=email).first()
    is_new = user is None

    if is_new:
        user = User(
            email=email,
            name=name,
            college=current_app.config["COLLEGE_NAME"],
        )
        db.session.add(user)
        db.session.commit()

    session_token = _create_jwt(user.id)
    expiry_days   = current_app.config["SESSION_TOKEN_EXPIRY_DAYS"]

    destination = url_for("pages.onboarding") if is_new else url_for("pages.dashboard")
    response = redirect(destination)
    response.set_cookie(
        "session_token",
        session_token,
        max_age=expiry_days * 24 * 3600,
        httponly=True,
        samesite="Lax",
        secure=not current_app.debug,
    )
    return response


@auth_bp.route("/logout")
def logout():
    """
    Section 5.3 — Logout clears the session immediately.
    In dev mode, just redirects to dashboard (no session to clear).
    """
    if current_app.config.get("DEV_BYPASS_AUTH"):
        return redirect(url_for("pages.dashboard"))
    response = redirect(url_for("pages.login"))
    response.delete_cookie("session_token")
    return response
