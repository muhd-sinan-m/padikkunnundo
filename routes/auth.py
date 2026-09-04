from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional
import re

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
from flask_limiter import Limiter
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
oauth = OAuth()


def clean_name(raw_name: str) -> str:
    if not raw_name:
        return raw_name
    name = raw_name.strip()
    regno_pattern = r'\s+\d{2}[A-Z]{2,4}\d{2,4}$'
    return re.sub(regno_pattern, '', name).strip()


def get_cf_real_ip():
    return (
        request.headers.get("CF-Connecting-IP") or
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        request.remote_addr
    )


limiter = Limiter(
    key_func=get_cf_real_ip,
    default_limits=["100 per hour"],
)


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    return True, ""


def init_oauth(app) -> None:
    oauth.init_app(app)
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        client_kwargs={"scope": "openid email profile"},
    )


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
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.PyJWTError:
        return None


def _set_session_cookie(response, user: User):
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


def _create_sso_jwt(user: User) -> str:
    import time
    expiry_seconds = current_app.config.get("SSO_TOKEN_EXPIRY_SECONDS", 300)
    now_ts = int(time.time())
    payload = {
        "user_id": str(user.id),
        "sub": str(user.id),
        "name": user.name or "",
        "email": user.email or "",
        "college": user.college or "",
        "iss": "padikkunnundo",
        "aud": "mcq-quiz",
        "iat": now_ts,
        "exp": now_ts + expiry_seconds,
    }
    return jwt.encode(
        payload,
        current_app.config["JWT_SECRET"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def _decode_sso_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
            audience="mcq-quiz",
            issuer="padikkunnundo",
        )
    except jwt.PyJWTError:
        return None


def get_current_user() -> User | None:
    token = request.cookies.get("session_token")
    if token:
        payload = _decode_jwt(token)
        if payload:
            user = db.session.get(User, int(payload["sub"]))
            if user is not None:
                if user.is_blocked:
                    return None
                return user
    return None


def login_required(f):
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
@limiter.limit("5 per 15 minutes")
def register():
    name = clean_name(request.form.get("name", "").strip())
    password = request.form.get("password", "")
    email = request.form.get("email", "").strip().lower()

    if not name or not password:
        return render_template(
            "login.html",
            error="Full name and password are required.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    if not email:
        return render_template(
            "login.html",
            error="Email is required for account recovery.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return render_template(
            "login.html",
            error="Please provide a valid email address.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    if User.query.filter(User.name.ilike(name)).first():
        return render_template(
            "login.html",
            error="An account with this name already exists.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    if User.query.filter_by(email=email).first():
        return render_template(
            "login.html",
            error="An account with this email already exists.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

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
    db.session.commit()

    return render_template(
        "login.html",
        success="Registration successful! You can now log in.",
        college_name=current_app.config["COLLEGE_NAME"],
        college_domain=current_app.config["COLLEGE_DOMAIN"],
    )


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per 15 minutes")
def login():
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")

    user = User.query.filter(User.name.ilike(name)).first()
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

    if user.is_blocked:
        return render_template(
            "login.html",
            error="Your account has been suspended by an administrator. Please contact support.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 403

    response = redirect(
        url_for("pages.onboarding") if not user.is_onboarded else url_for("pages.dashboard")
    )
    return _set_session_cookie(response, user)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes")
def reset_password_request():
    if request.method == "GET":
        return render_template(
            "reset_request.html",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        )

    email = request.form.get("email", "").strip().lower()
    if not email:
        return render_template(
            "reset_request.html",
            error="Email address is required.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return render_template(
            "reset_request.html",
            error="Please provide a valid email address.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.password_hash or user.is_blocked:
        return render_template(
            "reset_request.html",
            success="If an account with that email exists, you will receive password reset instructions.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        )

    reset_token = secrets.token_urlsafe(32)
    reset_expiry = datetime.now(timezone.utc) + timedelta(
        seconds=current_app.config.get("RESET_TOKEN_EXPIRY_SECONDS", 3600)
    )

    user.reset_token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
    user.reset_token_expiry = reset_expiry
    db.session.commit()

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
        pass

    return render_template(
        "reset_request.html",
        success="If an account with that email exists, you will receive password reset instructions.",
        college_name=current_app.config["COLLEGE_NAME"],
        college_domain=current_app.config["COLLEGE_DOMAIN"],
    )


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes")
def reset_password_confirm(token):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user = User.query.filter_by(reset_token_hash=token_hash).first()

    now_utc = datetime.now(timezone.utc)
    if user and user.reset_token_expiry:
        expiry = user.reset_token_expiry
        if expiry.tzinfo is None:
            is_valid = expiry > datetime.utcnow()
        else:
            is_valid = expiry > now_utc
        if not is_valid:
            user = None
    else:
        user = None

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

    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return render_template(
            "reset_confirm.html",
            token=token,
            error=error_msg,
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 400

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


@auth_bp.route("/google/login")
def google_login():
    redirect_uri = url_for("auth.google_callback", _external=True)
    college_domain = current_app.config.get("COLLEGE_DOMAIN")
    extra_params = {"hd": college_domain} if college_domain else {}
    return oauth.google.authorize_redirect(redirect_uri, **extra_params)


@auth_bp.route("/google/callback")
def google_callback():
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

    if not is_new and user.is_blocked:
        return render_template(
            "login.html",
            error="Your account has been suspended by an administrator. Please contact support.",
            college_name=current_app.config["COLLEGE_NAME"],
            college_domain=current_app.config["COLLEGE_DOMAIN"],
        ), 403

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
    response = redirect(url_for("pages.login"))
    response.delete_cookie("session_token")
    return response


@auth_bp.route("/sso/token")
@login_required
def sso_token():
    user = get_current_user()
    sso_jwt = _create_sso_jwt(user)

    next_path = request.args.get("next", "")
    if next_path and (not next_path.startswith("/") or next_path.startswith("//") or "://" in next_path):
        next_path = ""

    quiz_url = current_app.config.get("MCQ_QUIZ_URL", "").rstrip("/")
    target = f"{quiz_url}/sso/login?token={sso_jwt}"
    if next_path:
        from urllib.parse import quote
        target += f"&next={quote(next_path, safe='')}"

    return redirect(target)


@auth_bp.route("/sso/verify", methods=["POST"])
def sso_verify():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "").strip()

    if not token:
        return jsonify({"valid": False, "error": "Token missing."}), 400

    payload = _decode_sso_jwt(token)
    if payload is None:
        return jsonify({"valid": False, "error": "Token invalid or expired."}), 401

    return jsonify({
        "valid": True,
        "sub": payload.get("sub"),
        "name": payload.get("name"),
        "email": payload.get("email"),
        "college": payload.get("college"),
    }), 200


@auth_bp.route("/markkundo-sso")
@login_required
def markkundo_sso():
    user: User = get_current_user()
    if user is None:
        return redirect(url_for("pages.login"))

    sso_secret = current_app.config.get("SSO_SECRET", "")
    markkundo_url = current_app.config.get("MARK_ANALYSER_URL", "").rstrip("/")
    expiry_seconds = current_app.config.get("MARKKUNDO_SSO_EXPIRY_SECONDS", 300)

    if not sso_secret:
        return "SSO is not configured on this server.", 503

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.email,
        "iss": "padikkunundo",
        "aud": "markkundo",
        "name": user.name or "",
        "iat": now,
        "exp": now + timedelta(seconds=expiry_seconds),
    }
    token = jwt.encode(
        payload,
        sso_secret,
        algorithm=current_app.config.get("JWT_ALGORITHM", "HS256"),
    )

    sso_url = f"{markkundo_url}/auth/sso?token={token}"
    return redirect(sso_url)
