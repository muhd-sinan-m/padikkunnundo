from __future__ import annotations

from functools import wraps
from typing import Any

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app

from models import Announcement, Enrollment, Mark, Subject, User, db
from routes.auth import get_current_user, login_required
from grading import compute_grade_requirements, get_mark_structure


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None or not getattr(user, "is_admin", False):
            abort(403)
        return f(*args, **kwargs)

    return decorated


def _ensure_post_user() -> User:
    user = get_current_user()
    if user is None:
        abort(403)
    return user


def _mark_components_max(structure: dict[str, float]) -> float:
    # Components allowed in our UI / stored fields
    return float(structure["isa"] + structure["cp"] + structure["lb"] + structure["ld"] + structure["sea1"])


def _compute_class_average_percent(subject: Subject) -> float | None:
    """
    Average mark across all students for a subject.
    Returns None if there are no mark rows for the subject at all.
    """
    structure = get_mark_structure(int(subject.credit))
    max_total = _mark_components_max(structure)

    marks = Mark.query.filter_by(subject_id=subject.subject_id).all()
    if not marks:
        return None

    def entered_total(m: Mark) -> float:
        # Treat NULL as 0 (i.e., not entered).
        isa = float(m.isa or 0)
        cp = float(m.cp or 0)
        lb = float(m.lb or 0)
        ld = float(m.ld or 0)
        sea1 = float(m.sea1 or 0)
        return isa + cp + lb + ld + sea1

    avg_entered = sum(entered_total(m) for m in marks) / len(marks)
    if max_total <= 0:
        return 0.0
    return (avg_entered / max_total) * 100.0


@admin_bp.route("")
@login_required
@admin_required
def admin_dashboard():
    current_user = get_current_user()

    total_users = User.query.count()

    users_per_semester = (
        db.session.query(User.semester, db.func.count(User.id))
        .filter(User.semester.isnot(None))
        .group_by(User.semester)
        .order_by(User.semester.asc())
        .all()
    )
    users_per_semester_dict = {int(sem): int(cnt) for sem, cnt in users_per_semester}

    # Marks entered vs zero marks:
    # Count marks rows where at least one component is not NULL.
    marks_rows = Mark.query.all()
    total_mark_rows = len(marks_rows)
    marks_entered_rows = sum(
        1
        for m in marks_rows
        if any(v is not None for v in (m.isa, m.cp, m.lb, m.ld, m.sea1))
    )

    # Translate “marks entered %” into “entered mark rows / total mark rows”.
    marks_entered_pct = (marks_entered_rows / total_mark_rows * 100.0) if total_mark_rows else 0.0

    # Average mark per subject (% of max)
    subjects = Subject.query.all()
    subject_avg = []
    low_performing_subject_ids = set()
    for s in subjects:
        avg_pct = _compute_class_average_percent(s)
        avg_pct_val = avg_pct if avg_pct is not None else 0.0
        low = avg_pct is not None and avg_pct < 50.0
        if low:
            low_performing_subject_ids.add(s.subject_id)
        subject_avg.append(
            {
                "subject_id": s.subject_id,
                "subject_name": s.subject_name,
                "semester": s.semester,
                "avg_percent": avg_pct_val,
                "is_low_performing": low,
            }
        )

    low_performing_subjects = [
        x for x in subject_avg if x["is_low_performing"]
    ]

    # Users per day (last 14 days)
    users_per_date_rows = (
        db.session.query(
            db.func.date(User.created_at).label("date"),
            db.func.count(User.id).label("count"),
        )
        .filter(User.created_at.isnot(None))
        .group_by(db.func.date(User.created_at))
        .order_by(db.func.date(User.created_at).asc())
        .all()
    )

    # Ensure we return the last 14 days in chronological order.
    # If there are missing days, they will be represented with 0 counts.
    from datetime import date, timedelta
    today = date.today()
    start_day = today - timedelta(days=13)

    counts_map = {row.date.isoformat(): int(row.count) for row in users_per_date_rows}
    users_per_date = [
        {"date": (start_day + timedelta(days=i)).isoformat(), "count": counts_map.get((start_day + timedelta(days=i)).isoformat(), 0)}
        for i in range(14)
    ]

    return render_template(
        "admin.html",
        section="dashboard",
        stats={
            "total_users": total_users,
            "users_per_semester": users_per_semester_dict,
            "marks_entered_pct": marks_entered_pct,
        },
        marks_overview={
            "total_marks_rows": total_mark_rows,
            "marks_entered_rows": marks_entered_rows,
        },
        users_per_date=users_per_date,
        current_user=current_user,
    )


@admin_bp.route("/users")
@login_required
@admin_required
def admin_users_list():
    q = (request.args.get("q") or "").strip().lower()
    query = User.query

    if q:
        query = query.filter(
            (User.name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )

    users = query.order_by(User.created_at.desc()).all()

    def login_method(u: User) -> str:
        # Heuristic: local accounts have password_hash; OAuth users generally have no password_hash.
        return "local" if u.password_hash else "google"

    return render_template(
        "admin.html",
        section="users",
        users=[
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "semester": u.semester,
                "elective": None,  # elective is not stored on User
                "login_method": login_method(u),
                "created_at": u.created_at,
            }
            for u in users
        ],
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_user_edit(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    if request.method == "POST":
        data = request.form
        user.name = (data.get("name") or "").strip()
        user.email = (data.get("email") or "").strip().lower()
        sem = data.get("semester")
        user.semester = int(sem) if sem else None
        user.is_onboarded = True

        # “elective” is not represented in current schema. We interpret “elective” as elective_group
        # stored in Enrollment/Subject; for now, keep field as no-op.
        # (Admin UI will still allow editing; it won’t persist without schema support.)
        db.session.commit()
        flash("User updated.", "success")
        return redirect(url_for("admin.admin_users_list"))

    return render_template(
        "admin.html",
        section="user_edit",
        user=user,
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_user_delete(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    # Hard delete user + enrollments + marks.
    # (No cascade configured in models, so do manual deletes.)
    Mark.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    Enrollment.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()

    flash("User deleted.", "success")
    return redirect(url_for("admin.admin_users_list"))


@admin_bp.route("/subjects")
@login_required
@admin_required
def admin_subjects_list():
    subjects = Subject.query.order_by(Subject.semester.asc(), Subject.subject_name.asc()).all()
    grouped: dict[int, list[Subject]] = {}
    for s in subjects:
        grouped.setdefault(s.semester, []).append(s)

    return render_template(
        "admin.html",
        section="subjects",
        subjects_grouped={
            sem: [s for s in subs]
            for sem, subs in sorted(grouped.items(), key=lambda x: x[0])
        },
    )


@admin_bp.route("/subjects/add", methods=["GET", "POST"])
@login_required
@admin_required
def admin_subject_add():
    if request.method == "POST":
        data = request.form
        subject_name = (data.get("name") or "").strip()

        if not subject_name:
            flash("Subject name is required.", "error")
            return redirect(url_for("admin.admin_subject_add"))

        semester = int(data.get("semester"))
        credits = float(data.get("credits"))

        subject = Subject(
            subject_name=subject_name,
            semester=semester,
            credit=credits,
            is_elective=False,
            is_active=True,
            elective_group=None,
        )

        # Admin UI in this deployment only manages: name, semester, credits, is_active, is_elective/elective_group.


        db.session.add(subject)
        db.session.commit()
        flash("Subject added.", "success")
        return redirect(url_for("admin.admin_subjects_list"))

    return render_template(
        "admin.html",
        section="subject_add",
    )


@admin_bp.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_subject_edit(subject_id: int):
    subject = db.session.get(Subject, subject_id)
    if not subject:
        abort(404)

    if request.method == "POST":
        data = request.form
        subject.subject_name = (data.get("name") or "").strip()
        subject.semester = int(data.get("semester"))
        subject.credit = float(data.get("credits"))
        subject.is_active = data.get("is_active") == "on"

        db.session.commit()

        flash("Subject updated.", "success")
        return redirect(url_for("admin.admin_subjects_list"))

    return render_template(
        "admin.html",
        section="subject_edit",
        subject=subject,
    )


@admin_bp.route("/announcements")
@login_required
@admin_required
def admin_announcements_list():
    announcements = (
        Announcement.query.order_by(Announcement.created_at.desc()).all()
    )
    return render_template(
        "admin.html",
        section="announcements",
        announcements=announcements,
    )


@admin_bp.route("/announcements/add", methods=["POST"])
@login_required
@admin_required
def admin_announcement_add():
    data = request.form
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()

    if not title or not body:
        flash("Title and body are required.", "error")
        return redirect(url_for("admin.admin_announcements_list"))

    user = _ensure_post_user()

    ann = Announcement(
        title=title,
        body=body,
        created_by=user.id,
    )
    db.session.add(ann)
    db.session.commit()

    flash("Announcement added.", "success")
    return redirect(url_for("admin.admin_announcements_list"))


@admin_bp.route("/announcements/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_announcement_delete(id: int):
    ann = db.session.get(Announcement, id)
    if not ann:
        abort(404)

    db.session.delete(ann)
    db.session.commit()

    flash("Announcement deleted.", "success")
    return redirect(url_for("admin.admin_announcements_list"))


@admin_bp.route("/rollover")
@login_required
@admin_required
def admin_rollover():
    users_per_semester = (
        db.session.query(User.semester, db.func.count(User.id))
        .group_by(User.semester)
        .order_by(User.semester.asc())
        .all()
    )
    users_per_semester_dict = {
        int(sem): int(cnt)
        for sem, cnt in users_per_semester
        if sem is not None
    }
    return render_template(
        "admin.html",
        section="rollover",
        users_per_semester=users_per_semester_dict,
    )


@admin_bp.route("/rollover/confirm", methods=["POST"])
@login_required
@admin_required
def admin_rollover_confirm():
    # Increment semester by 1 for all users where semester < 6, cap at 6.
    users = User.query.filter(User.semester.isnot(None)).all()
    for u in users:
        if u.semester < 6:
            u.semester = u.semester + 1
        else:
            u.semester = 6
    db.session.commit()
    flash("Rollover completed.", "success")
    return redirect(url_for("admin.admin_dashboard"))
