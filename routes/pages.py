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
