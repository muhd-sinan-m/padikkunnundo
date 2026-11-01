from datetime import datetime
import time
from urllib.parse import quote
import jwt
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request as flask_request, url_for

from models import Feedback, db
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
            "lab_practice":  current_app.config["LAB_PRACTICE_URL"],
            "passavam":      current_app.config["PASSAVAM_URL"],
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


@pages_bp.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    user = get_current_user()
    if not user.is_onboarded:
        return _onboarding_redirect()

    # Determine class representation
    if user.course and user.semester:
        user_class = f"{user.course} - Sem {user.semester}"
    elif user.semester:
        user_class = f"Semester {user.semester}"
    elif user.course:
        user_class = user.course
    else:
        user_class = "Student"

    if flask_request.method == "POST":
        if flask_request.is_json:
            data = flask_request.get_json() or {}
            rating_raw = data.get("rating")
            feedback_text = (data.get("feedback") or "").strip()
        else:
            rating_raw = flask_request.form.get("rating")
            feedback_text = (flask_request.form.get("feedback") or "").strip()

        # Validate rating
        try:
            rating = int(rating_raw)
            if rating < 1 or rating > 5:
                raise ValueError()
        except (TypeError, ValueError):
            if flask_request.is_json:
                return jsonify({"error": "Please provide a star rating between 1 and 5."}), 400
            flash("Please select a rating between 1 and 5 stars.", "error")
            return render_template(
                "feedback.html",
                user=user,
                user_class=user_class,
                submitted=False,
                error="Please select a rating between 1 and 5 stars.",
            ), 400

        # Validate feedback text
        if not feedback_text or len(feedback_text) < 3:
            if flask_request.is_json:
                return jsonify({"error": "Please enter your feedback before submitting."}), 400
            flash("Please enter your feedback before submitting.", "error")
            return render_template(
                "feedback.html",
                user=user,
                user_class=user_class,
                submitted=False,
                selected_rating=rating,
                error="Please enter your feedback before submitting.",
            ), 400

        # Save feedback record with user_id, name, class, star rating, feedback text
        entry = Feedback(
            user_id=user.id,
            name=user.name,
            student_class=user_class,
            rating=rating,
            feedback_text=feedback_text,
            created_at=datetime.utcnow(),
        )
        db.session.add(entry)
        db.session.commit()

        if flask_request.is_json:
            return jsonify({"success": True, "message": "Thank you for your feedback!"}), 200

        flash("Thank you! Your feedback has been submitted successfully.", "success")
        return redirect(url_for("pages.feedback", submitted="1"))

    # GET request
    submitted = flask_request.args.get("submitted") == "1"
    return render_template(
        "feedback.html",
        user=user,
        user_class=user_class,
        submitted=submitted,
    )

