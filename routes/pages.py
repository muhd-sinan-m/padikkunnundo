"""
routes/pages.py — HTML page routes served via Jinja2 templates.

Handles the Section 5.4 first-time vs returning user routing:
  • Not authenticated → /login
  • Authenticated, not onboarded → /onboarding
  • Authenticated, onboarded → /dashboard (and other protected pages)
"""

from flask import Blueprint, current_app, redirect, render_template, url_for

from routes.auth import get_current_user, login_required

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    from flask import current_app
    if current_app.config.get("DEV_BYPASS_AUTH"):
        return redirect(url_for("pages.dashboard"))
    user = get_current_user()
    if user is None:
        return redirect(url_for("pages.login"))
    if not user.is_onboarded:
        return redirect(url_for("pages.onboarding"))
    return redirect(url_for("pages.dashboard"))


@pages_bp.route("/login")
def login():
    user = get_current_user()
    if user and user.is_onboarded:
        return redirect(url_for("pages.dashboard"))
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
            "pyqportal": current_app.config["PYQPORTAL_URL"],
            "mcq_quiz":  current_app.config["MCQ_QUIZ_URL"],
            "placement": current_app.config["PLACEMENT_URL"],
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


@pages_bp.route("/schedule")
@login_required
def schedule():
    user = get_current_user()
    if not user.is_onboarded:
        return redirect(url_for("pages.onboarding"))
    return render_template("schedule.html", user=user)


@pages_bp.route("/topics")
@login_required
def topics():
    user = get_current_user()
    if not user.is_onboarded:
        return redirect(url_for("pages.onboarding"))
    return render_template("topics.html", user=user)
