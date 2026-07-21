"""
routes/pages.py — HTML page routes served via Jinja2 templates.

Handles the Section 5.4 first-time vs returning user routing:
  • Not authenticated → /login
  • Authenticated, not onboarded → /onboarding
  • Authenticated, onboarded → /dashboard (and other protected pages)
"""

import time

from flask import Blueprint, current_app, redirect, render_template, url_for
import jwt

from routes.auth import get_current_user, login_required, _create_sso_jwt

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    user = get_current_user()
    if user:
        if user.is_onboarded:
            return redirect(url_for("pages.dashboard"))
        return redirect(url_for("pages.onboarding"))
    return redirect(url_for("pages.login"))


@pages_bp.route("/login")
def login():
    return render_template(
        "login.html",
        college_name=current_app.config["COLLEGE_NAME"],
        college_domain=current_app.config["COLLEGE_DOMAIN"],
    )


@pages_bp.route("/onboarding")
@login_required
def onboarding():
    user = get_current_user()
    if user.is_onboarded:
        return redirect(url_for("pages.dashboard"))
    return render_template("onboarding.html", user=user)


@pages_bp.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    if not user.is_onboarded:
        return redirect(url_for("pages.onboarding"))
    return render_template(
        "dashboard.html",
        user=user,
        platforms={
            "pyqportal":     current_app.config["PYQPORTAL_URL"],
            "mcq_quiz":      current_app.config["MCQ_QUIZ_URL"],
            "placement":     current_app.config["PLACEMENT_URL"],
            "topics":        current_app.config["TOPIC_URL"],
            "mark_analyser": current_app.config["MARK_ANALYSER_URL"],
            "doubtundo":     current_app.config["DOUBTUNDO_URL"],
        },
    )


@pages_bp.route("/marks")
@login_required
def marks():
    user = get_current_user()
    if not user.is_onboarded:
        return redirect(url_for("pages.onboarding"))
    return render_template("marks.html", user=user)


@pages_bp.route("/calculator")
@login_required
def calculator():
    user = get_current_user()
    if not user.is_onboarded:
        return redirect(url_for("pages.onboarding"))
    return render_template("calculator.html", user=user)


@pages_bp.route("/about")
@login_required
def about():
    user = get_current_user()
    if not user.is_onboarded:
        return redirect(url_for("pages.onboarding"))
    return render_template("about.html", user=user, active_page="about")


@pages_bp.route("/go-to-doubtundo")
@login_required
def go_to_doubtundo():
    """
    SSO bridge to Doubtundo.

    Mints a short-lived JWT (5 min) containing the current user's identity
    and redirects to DOUBTUNDO_URL/auth?token=<token>.
    Doubtundo verifies the token with the shared JWT_SECRET and signs the
    user in without requiring a separate login.
    """
    user = get_current_user()
    payload = {
        "user_id": str(user.id),
        "email":   user.email,
        "name":    user.name,
        "exp":     int(time.time()) + 300,  # 5-minute expiry
    }
    token = jwt.encode(
        payload,
        current_app.config["JWT_SECRET"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )
    dest = current_app.config["DOUBTUNDO_URL"]
    return redirect(f"{dest}/auth?token={token}")


@pages_bp.route("/go-to-mcq")
@login_required
def go_to_mcq():
    """
    SSO bridge to the MCQ Quiz portal.

    Mints a 5-minute JWT (signed with JWT_SECRET, iss="padikkunnundo",
    aud="mcq-quiz") and redirects to {MCQ_QUIZ_URL}/sso/login?token=<jwt>.
    The MCQ portal validates the token with the shared JWT_SECRET and
    signs the user in without requiring a separate login.

    Optional query param:
      ?next=<path>  — forwarded to the MCQ portal so it can redirect the
                       user to a specific page after login.
    """
    from flask import request as flask_request
    from urllib.parse import quote

    user = get_current_user()
    token = _create_sso_jwt(user)

    quiz_url = current_app.config.get("MCQ_QUIZ_URL", "https://quiz.pyqportal.app").rstrip("/")
    target = f"{quiz_url}/sso/login?token={token}"

    next_path = flask_request.args.get("next", "")
    if next_path:
        target += f"&next={quote(next_path, safe='')}"

    return redirect(target)
