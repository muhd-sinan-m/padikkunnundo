"""
routes/api.py — REST API endpoints consumed by the frontend JavaScript.

All endpoints are scoped to the authenticated user's own data (Section 10).
No endpoint accepts an arbitrary user_id parameter — all queries use the
user_id from the verified JWT session.

Endpoints
─────────
  GET  /api/me                          → current user profile
  POST /api/enroll                      → complete onboarding enrollment
  GET  /api/subjects                    → enrolled subjects + marks for the session
  GET  /api/electives/<semester>        → elective options for a given semester
  GET  /api/marks/<subject_id>          → marks for one subject
  POST /api/marks/<subject_id>          → save/update marks for one subject
  GET  /api/grades/<subject_id>         → grade requirements for one subject
  GET  /api/focus                       → focus priority ranking (Section 7.4)
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from grading import (
    compute_focus_priority,
    compute_grade_requirements,
    get_mark_structure,
)
from models import Announcement, Enrollment, Mark, Subject, User, db
from routes.auth import get_current_user, login_required

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ── /api/me ───────────────────────────────────────────────────────────────────

@api_bp.route("/me")
@login_required
def me():
    user: User = get_current_user()
    return jsonify({
        **user.to_dict(),
        "platforms": {
            "pyqportal": current_app.config["PYQPORTAL_URL"],
            "mcq_quiz":  current_app.config["MCQ_QUIZ_URL"],
            "placement": current_app.config["PLACEMENT_URL"],
            "topics":    current_app.config["TOPIC_URL"],
        },
    })


# ── /api/enroll ───────────────────────────────────────────────────────────────

@api_bp.route("/enroll", methods=["POST"])
@login_required
def enroll():
    """
    Section 4.5 — Enrollment flow.

    Body: { "semester": int, "course": str, "elective_subject_id": int | null }

    Creates enrollments for:
      1. All core (non-elective) subjects for the chosen semester.
      2. The chosen elective subject (if the semester has one).

    For elective groups that span two semesters (e.g. Sem 1–2 language
    electives), the choice automatically carries forward — the student is
    not asked again in Semester 2.
    """
    user: User = get_current_user()
    data = request.get_json(silent=True) or {}

    semester = data.get("semester")
    course = data.get("course", "BCA")
    elective_subject_id = data.get("elective_subject_id")
    elective_subject_ids = data.get("elective_subject_ids")

    if not semester:
        return jsonify({"error": "semester is required."}), 400

    # Normalize elective_subject_ids when present
    if elective_subject_ids is not None and not isinstance(elective_subject_ids, list):
        return jsonify({"error": "Invalid elective_subject_ids."}), 400



    # ── Save basic profile ────────────────────────────────────────────────────
    user.semester = semester
    user.course = course
    user.is_onboarded = True

    # ── Enroll in core subjects ───────────────────────────────────────────────
    core_subjects = Subject.query.filter_by(
        semester=semester, is_elective=False
    ).all()

    for subject in core_subjects:
        existing = Enrollment.query.filter_by(
            user_id=user.id, subject_id=subject.subject_id
        ).first()
        if not existing:
            db.session.add(Enrollment(
                user_id=user.id,
                subject_id=subject.subject_id,
                semester=semester,
            ))
            # Create a blank marks row so we always have one per enrollment.
            db.session.add(Mark(user_id=user.id, subject_id=subject.subject_id))

    # ── Enroll in the chosen elective(s) ─────────────────────────────────────────
    if int(semester) == 5:
        elective_subject_ids = elective_subject_ids or []
        if not isinstance(elective_subject_ids, list) or len(elective_subject_ids) != 3:
            return jsonify({"error": "Please select exactly 3 professional electives."}), 400

        # Verify all 3 ids are valid and belong to pe_5
        subjects = Subject.query.filter(
            Subject.subject_id.in_(elective_subject_ids),
            Subject.elective_group == 'pe_5',
            Subject.is_elective == True,
        ).all()

        valid_ids = {s.subject_id for s in subjects}
        if len(valid_ids) != 3 or any(i not in valid_ids for i in elective_subject_ids):
            return jsonify({"error": "Invalid professional elective selection."}), 400


        # Enroll in each of the 3 electives
        for elective in subjects:
            existing = Enrollment.query.filter_by(
                user_id=user.id, subject_id=elective.subject_id
            ).first()
            if not existing:
                db.session.add(Enrollment(
                    user_id=user.id,
                    subject_id=elective.subject_id,
                    semester=semester,
                ))
                db.session.add(Mark(user_id=user.id, subject_id=elective.subject_id))

    else:
        # Existing Sem 1-4 flow (unchanged): single elective enrollment
        if elective_subject_id:
            elective = db.session.get(Subject, elective_subject_id)
            if elective and elective.is_elective:
                existing = Enrollment.query.filter_by(
                    user_id=user.id, subject_id=elective.subject_id
                ).first()
                if not existing:
                    db.session.add(Enrollment(
                        user_id=user.id,
                        subject_id=elective.subject_id,
                        semester=semester,
                    ))
                    db.session.add(Mark(user_id=user.id, subject_id=elective.subject_id))

    db.session.commit()
    return jsonify({"ok": True, "semester": semester})



# ── /api/subjects ─────────────────────────────────────────────────────────────

@api_bp.route("/subjects")
@login_required
def subjects():
    """
    Return all subjects the authenticated student is enrolled in for their
    current semester, with their mark structure and any entered marks.
    """
    user: User = get_current_user()

    # If user has no semester set, they need to complete onboarding
    if user.semester is None or not user.is_onboarded:
        current_app.logger.warning(
            f"User {user.id} ({user.name}) has no semester set or not onboarded. "
            "Redirect to onboarding needed."
        )
        return jsonify({
            "subjects": [],
            "stats": {
                "total_subjects": 0,
                "marks_entered": 0,
                "on_track_for_aplus": 0,
            },
            "needs_onboarding": True,
        }), 200

    enrollments = (
        Enrollment.query
        .filter_by(user_id=user.id, semester=user.semester)
        .join(Subject)
        .all()
    )

    # Debug: Log if no enrollments found
    if not enrollments:
        current_app.logger.warning(
            f"User {user.id} ({user.name}) in semester {user.semester} "
            "has no enrollments. Onboarding may be incomplete."
        )

    result = []
    marks_entered = 0

    for enr in enrollments:
        subj = enr.subject
        structure = get_mark_structure(int(subj.credit))

        mark_row = Mark.query.filter_by(
            user_id=user.id, subject_id=subj.subject_id
        ).first()

        marks_dict = {}
        if mark_row:
            marks_dict = {
                "isa":  mark_row.isa,
                "cp":   mark_row.cp,
                "lb":   mark_row.lb,
                "ld":   mark_row.ld,
                "sea1": mark_row.sea1,
            }
            if any(v is not None for v in marks_dict.values()):
                marks_entered += 1

        result.append({
            **subj.to_dict(),
            "structure": structure,
            "marks": marks_dict,
        })

    # Summary stats for the dashboard (Section 7.1)
    on_track = _count_on_track(user, enrollments)

    return jsonify({
        "subjects": result,
        "stats": {
            "total_subjects": len(enrollments),
            "marks_entered": marks_entered,
            "on_track_for_aplus": on_track,
        },
    })


def _count_on_track(user: User, enrollments) -> int:
    """Count subjects where A+ is still achievable or already secured."""
    count = 0
    for enr in enrollments:
        subj = enr.subject
        mark_row = Mark.query.filter_by(
            user_id=user.id, subject_id=subj.subject_id
        ).first()
        if not mark_row:
            continue
        result = compute_grade_requirements(
            int(subj.credit),
            isa=mark_row.isa, cp=mark_row.cp,
            lb=mark_row.lb, ld=mark_row.ld, sea1=mark_row.sea1,
        )
        status = result["grades"]["A+"]["status"]
        if status in ("secured", "achievable"):
            count += 1
    return count


# ── /api/electives/<semester> ─────────────────────────────────────────────────

@api_bp.route("/electives/<int:semester>")
@login_required
def electives(semester: int):
    """Return elective subject options available for a given semester."""
    subjects = Subject.query.filter_by(
        semester=semester, is_elective=True
    ).all()
    return jsonify({"electives": [s.to_dict() for s in subjects]})


# ── /api/marks/<subject_id> ───────────────────────────────────────────────────

@api_bp.route("/marks/<int:subject_id>", methods=["GET"])
@login_required
def get_marks(subject_id: int):
    user: User = get_current_user()
    _assert_enrolled(user, subject_id)

    mark_row = Mark.query.filter_by(
        user_id=user.id, subject_id=subject_id
    ).first()
    if not mark_row:
        return jsonify({"marks": {}}), 200

    return jsonify({"marks": mark_row.to_dict()})


@api_bp.route("/marks/<int:subject_id>", methods=["POST"])
@login_required
def save_marks(subject_id: int):
    """
    Save or update mark components for a subject.
    SEA2 is never accepted from the client (Section 6.4).
    All values are clamped to their credit-based maximum at the API layer.
    """
    user: User = get_current_user()
    _assert_enrolled(user, subject_id)

    subj = db.session.get(Subject, subject_id)
    structure = get_mark_structure(int(subj.credit))
    data = request.get_json(silent=True) or {}

    mark_row = Mark.query.filter_by(
        user_id=user.id, subject_id=subject_id
    ).first()
    if not mark_row:
        mark_row = Mark(user_id=user.id, subject_id=subject_id)
        db.session.add(mark_row)

    # Clamp each value to its maximum; null is accepted (mark not yet entered).
    for field in ("isa", "cp", "lb", "ld", "sea1"):
        if field in data:
            raw = data[field]
            if raw is None:
                setattr(mark_row, field, None)
            else:
                clamped = max(0.0, min(float(raw), structure[field]))
                setattr(mark_row, field, clamped)

    db.session.commit()

    # Immediately return updated grade requirements so the UI can update live.
    grade_result = compute_grade_requirements(
        int(subj.credit),
        isa=mark_row.isa, cp=mark_row.cp,
        lb=mark_row.lb, ld=mark_row.ld, sea1=mark_row.sea1,
    )
    return jsonify({"marks": mark_row.to_dict(), "grades": grade_result})


# ── /api/grades/<subject_id> ──────────────────────────────────────────────────

@api_bp.route("/grades/<int:subject_id>")
@login_required
def grades(subject_id: int):
    """
    Compute and return grade requirements for a subject using stored marks.
    This is the A+ Calculator logic exposed as an API (Section 7.3).
    """
    user: User = get_current_user()
    _assert_enrolled(user, subject_id)

    subj = db.session.get(Subject, subject_id)
    mark_row = Mark.query.filter_by(
        user_id=user.id, subject_id=subject_id
    ).first()

    marks = {}
    if mark_row:
        marks = {
            "isa": mark_row.isa, "cp": mark_row.cp,
            "lb": mark_row.lb, "ld": mark_row.ld, "sea1": mark_row.sea1,
        }

    result = compute_grade_requirements(int(subj.credit), **marks)
    return jsonify({
        "subject": subj.to_dict(),
        "grades": result,
    })


# ── /api/focus ────────────────────────────────────────────────────────────────

@api_bp.route("/focus")
@login_required
def focus():
    """
    Section 7.4 — Focus Priority.
    Returns subjects ranked by descending A+ difficulty.
    Subjects with no marks are returned separately.
    """
    user: User = get_current_user()

    enrollments = (
        Enrollment.query
        .filter_by(user_id=user.id, semester=user.semester)
        .join(Subject)
        .all()
    )

    subjects_with_marks = []
    for enr in enrollments:
        subj = enr.subject
        mark_row = Mark.query.filter_by(
            user_id=user.id, subject_id=subj.subject_id
        ).first()
        marks = {}
        if mark_row:
            marks = {
                "isa": mark_row.isa, "cp": mark_row.cp,
                "lb": mark_row.lb, "ld": mark_row.ld, "sea1": mark_row.sea1,
            }
        subjects_with_marks.append({**subj.to_dict(), "marks": marks})

    ranked, no_data = compute_focus_priority(subjects_with_marks)
    return jsonify({"ranked": ranked, "no_data": no_data})




# ── Helpers ───────────────────────────────────────────────────────────────────

@api_bp.route("/notifications")
@login_required
def notifications():
    """Return announcements for the notification bell.

    Returns latest 10 announcements ordered by created_at desc.
    Shape: [{"id":...,"title":...,"body":...,"created_at":...}]
    """
    anns = (
        Announcement.query
        .order_by(Announcement.created_at.desc())
        .limit(10)
        .all()
    )

    return jsonify([
        {
            "id": a.id,
            "title": a.title,
            "body": a.body,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in anns
    ])


def _assert_enrolled(user: User, subject_id: int) -> None:
    """
    Raise a 403 if the current user is not enrolled in the given subject.
    This enforces data isolation: a student cannot read or write
    another student's marks by guessing subject IDs.
    """
    enr = Enrollment.query.filter_by(
        user_id=user.id, subject_id=subject_id
    ).first()
    if not enr:
        from flask import abort
        abort(403)
