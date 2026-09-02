import time
from urllib.parse import quote
import jwt
from flask import Blueprint, current_app, redirect, render_template, request as flask_request, url_for

from routes.auth import get_current_user, login_required, _create_sso_jwt

pages_bp = Blueprint("pages", __name__)


def _onboarding_redirect():
    user = get_current_user()
    if user and user.semester is not None:
        return redirect(url_for("pages.rollover_onboarding"))
    return redirect(url_for("pages.onboarding"))


@pages_bp.route("/")
def index():
    user = get_current_user()
    if user:
        if user.is_onboarded:
            return redirect(url_for("pages.dashboard"))
        return _onboarding_redirect()
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
    if user.semester is not None:
        return redirect(url_for("pages.rollover_onboarding"))
    return render_template("onboarding.html", user=user)


@pages_bp.route("/rollover-onboarding")
@login_required
def rollover_onboarding():
    user = get_current_user()
    if user.is_onboarded:
        return redirect(url_for("pages.dashboard"))
    if user.semester is None:
        return redirect(url_for("pages.onboarding"))
    return render_template("rollover_onboarding.html", user=user)


@pages_bp.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    if not user.is_onboarded:
        return _onboarding_redirect()
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
        return _onboarding_redirect()
    return render_template("marks.html", user=user)


@pages_bp.route("/calculator")
@login_required
def calculator():
    user = get_current_user()
    if not user.is_onboarded:
        return _onboarding_redirect()
    return render_template("calculator.html", user=user)


@pages_bp.route("/about")
@login_required
def about():
    user = get_current_user()
    if not user.is_onboarded:
        return _onboarding_redirect()
    return render_template("about.html", user=user, active_page="about")


@pages_bp.route("/go-to-doubtundo")
@login_required
def go_to_doubtundo():
    user = get_current_user()
    payload = {
        "user_id": str(user.id),
        "email":   user.email,
        "name":    user.name,
        "exp":     int(time.time()) + 300,
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
    user = get_current_user()
    token = _create_sso_jwt(user)

    quiz_url = current_app.config.get("MCQ_QUIZ_URL", "").rstrip("/")
    target = f"{quiz_url}/sso/login?token={token}"

    next_path = flask_request.args.get("next", "")
    if next_path and (not next_path.startswith("/") or next_path.startswith("//") or "://" in next_path):
        next_path = ""

    if next_path:
        target += f"&next={quote(next_path, safe='')}"

    return redirect(target)
