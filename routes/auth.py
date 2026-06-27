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

import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

import jwt
import re


def clean_name(raw_name: str) -> str:
    """
    Clean the user's name by removing registration numbers and other non-name patterns.

    Handles patterns like:
    - "MUHAMMED SINAN. M 24UBC145" -> "MUHAMMED SINAN. M"
    - "Name 24BCA001" -> "Name"
    - "Name 24UBC145" -> "Name"

    Registration number patterns typically follow formats like:
    - 2 digits + 2-4 letters + 2-4 digits (e.g., 24UBC145, 24BCA001)
    """
    if not raw_name:
        return raw_name

    name = raw_name.strip()

    # Pattern to match registration numbers at the end of the name
    # Matches patterns like: 24UBC145, 24BCA001, 23MCA042, etc.
    # Format: 2 digits + 2-4 uppercase letters + 2-4 digits
    regno_pattern = r'\s+\d{2}[A-Z]{2,4}\d{2,4}$'

    # Remove registration number pattern from the end
    cleaned = re.sub(regno_pattern, '', name)

    return cleaned.strip()
from authlib.integrations.flask_client import OAuth
from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from models import Enrollment, Mark, Subject, User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

oauth = OAuth()

# ── Rate limiter instance (initialized in create_app) ─────────────────────────
limiter: Optional[Limiter] = None


def init_limiter(limiter_instance: Limiter) -> None:
    """Store the limiter instance for use in route decorators."""
    global limiter
    limiter = limiter_instance


# ── Password strength validation ──────────────────────────────────────────────

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength. Returns (is_valid, error_message).
    Requirements:
      - At least 8 characters
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    return True, ""


# ── Dev user constants ────────────────────────────────────────────────────────
_DEV_EMAIL = "dev@mariancollege.org"
_DEV_NAME = "Dev User"
_DEV_SEMESTER = 4


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


def _set_session_cookie(response, user: User):
    """Attach the session cookie to a redirect response."""
    session_token = _create_jwt(user.id)
    expiry_days = current_app.config["SESSION_TOKEN_EXPIRY_DAYS"]
    response.set_cookie(
        "session_token",
        session_token,
        max_age=expiry_days * 24 * 3600,
        httponly=True,
        samesite="Lax",
        secure=not current_app.debug,
    )
    return response


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
        course="BCA",
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

    If a valid session cookie exists, that user is used.
    If a session cookie exists but is invalid, do not silently fall back to
    another account. Only use the dev fallback when there is no session cookie.
    """
    token = request.cookies.get("session_token")
    if token:
        payload = _decode_jwt(token)
        if payload:
            user = db.session.get(User, int(payload["sub"]))
            if user is not None:
                return user
        return None

    if current_app.config.get("DEV_BYPASS_AUTH"):
        return _get_or_create_dev_user()

    return None


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


@auth_bp.route("/register", methods=["POST"])
def register():
    """Create a new local user account with a stored password hash."""
    name = clean_name(request.form.get("name", "").strip())
    password = request.form.get("password", "")
    email = request.form.get("email", "").strip().lower()

    # Validate required fields
    if not name or not password:
        return render_template(
            "login.html",
            error="Full name and password are required.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    # Validate email (required for password reset functionality)
    if not email:
        return render_template(
            "login.html",
            error="Email is required for account recovery.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    # Validate email format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return render_template(
            "login.html",
            error="Please provide a valid email address.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    # Check for duplicate name
    if User.query.filter_by(name=name).first():
        return render_template(
            "login.html",
            error="That name is already taken. Please choose another.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    # Check for duplicate email
    if User.query.filter_by(email=email).first():
        return render_template(
            "login.html",
            error="An account with this email already exists.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    # Validate password strength
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return render_template(
            "login.html",
            error=error_msg,
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.flush()
    db.session.commit()

    # After registration, redirect to login with a success message
    return render_template(
        "login.html",
        success="Registration successful! You can now log in.",
        college_name=current_app.config["COLLEGE_NAME"],
        college_domain=current_app.config["COLLEGE_DOMAIN"],
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate a local user account stored in the database."""
    # Rate limiting is applied globally via app config
    # Failed login attempts are limited to 5 per 15 minutes per IP
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")

    user = User.query.filter_by(name=name).first()
    if not user or not user.password_hash:
        return render_template(
            "login.html",
            error="Invalid name or password.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 401

    if not check_password_hash(user.password_hash, password):
        return render_template(
            "login.html",
            error="Invalid name or password.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 401

    response = redirect(
        url_for("pages.onboarding") if not user.is_onboarded else url_for("pages.dashboard")
    )
    return _set_session_cookie(response, user)


# ── Password Reset Routes ─────────────────────────────────────────────────────

@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password_request():
    """Display password reset request form and handle submissions."""
    if request.method == "GET":
        return render_template(
            "reset_request.html",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        )

    name = request.form.get("name", "").strip()
    if not name:
        return render_template(
            "reset_request.html",
            error="Full name is required.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    user = User.query.filter_by(name=name).first()

    # Only proceed if user exists AND has an email AND has a password (local auth user)
    if not user or not user.email or not user.password_hash:
        # Return success message anyway to prevent name enumeration
        return render_template(
            "reset_request.html",
            success="If an account with that name exists and has an email, you will receive password reset instructions.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        )

    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    reset_expiry = datetime.now(timezone.utc) + timedelta(
        seconds=current_app.config.get("RESET_TOKEN_EXPIRY_SECONDS", 3600)
    )

    # Store token hash (not the raw token) for security
    user.reset_token_hash = generate_password_hash(reset_token)
    user.reset_token_expiry = reset_expiry
    db.session.commit()

    # Send reset email using Resend API
    try:
        import resend

        resend.api_key = current_app.config["RESEND_API_KEY"]
        mail_from = current_app.config.get("MAIL_FROM", "noreply@padikkunnundo.app")

        reset_url = url_for(
            "auth.reset_password_confirm", token=reset_token, _external=True
        )

        resend.Emails.send({
            "from": f"padikkunnundo.app <{mail_from}>",
            "to": user.email,
            "subject": "Password Reset - padikkunnundo.app",
            "html": f"""
            <p>Hello {user.name},</p>
            <p>You requested a password reset for your padikkunnundo.app account.</p>
            <p>Click the link below to set a new password:</p>
            <p><a href="{reset_url}">{reset_url}</a></p>
            <p>This link expires in 1 hour.</p>
            <p>If you didn't request this, you can safely ignore this email.</p>
            <p>— padikkunnundo.app Team</p>
            """,
        })
    except Exception as e:
        current_app.logger.error(f"Failed to send password reset email: {e}")
        # Still show success message to avoid revealing email issues
        pass

    return render_template(
        "reset_request.html",
        success="If an account with that name exists and has an email, you will receive password reset instructions.",
        college_name=current_app.config["COLLEGE_NAME"],
        college_domain=current_app.config["COLLEGE_DOMAIN"],
    )


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password_confirm(token):
    """Handle password reset with a valid token."""
    # Find user with matching token
    user = None
    for u in User.query.filter(User.reset_token_hash.isnot(None)).all():
        if check_password_hash(u.reset_token_hash, token):
            if u.reset_token_expiry and u.reset_token_expiry > datetime.utcnow():
                user = u
                break

    if not user:
        return render_template(
            "login.html",
            error="Invalid or expired reset link. Please request a new password reset.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    if request.method == "GET":
        return render_template(
            "reset_confirm.html",
            token=token,
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        )

    # POST request - validate and update password
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if password != confirm_password:
        return render_template(
            "reset_confirm.html",
            token=token,
            error="Passwords do not match.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    # Validate password strength
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return render_template(
            "reset_confirm.html",
            token=token,
            error=error_msg,
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    # Update password and clear reset token
    user.password_hash = generate_password_hash(password)
    user.reset_token_hash = None
    user.reset_token_expiry = None
    db.session.commit()

    return render_template(
        "login.html",
        success="Your password has been reset successfully. You can now log in with your new password.",
        college_name=current_app.config["COLLEGE_NAME"],
        college_domain=current_app.config["COLLEGE_DOMAIN"],
    )


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
    raw_name: str = userinfo.get("name", "")
    name = clean_name(raw_name)

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

    destination = url_for("pages.onboarding") if is_new else url_for("pages.dashboard")
    response = redirect(destination)
    return _set_session_cookie(response, user)


@auth_bp.route("/logout")
def logout():
    """
    Section 5.3 — Logout clears the session immediately.
    In dev mode, just redirects to dashboard (no session to clear).
    """
    response = redirect(url_for("pages.login"))
    response.delete_cookie("session_token")
    return response
