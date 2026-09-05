from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, abort
from sqlalchemy.orm import joinedload

from grading import (
    compute_focus_priority,
    compute_grade_requirements,
    get_mark_structure,
)
from models import Announcement, AnnouncementRead, Enrollment, Mark, Subject, User, db
from routes.auth import get_current_user, login_required

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _get_marks_map(user_id: int) -> dict:
    rows = Mark.query.filter_by(user_id=user_id).all()
    return {m.subject_id: m for m in rows}


def _assert_enrolled(user: User, subject_id: int) -> None:
    enr = Enrollment.query.filter_by(
        user_id=user.id, subject_id=subject_id
    ).first()
    if not enr:
        abort(403)


def _count_on_track(enrollments, marks_map: dict) -> int:
    count = 0
    for enr in enrollments:
        subj = enr.subject
        mark_row = marks_map.get(subj.subject_id)
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


@api_bp.route("/me")
@login_required
def me():
    user: User = get_current_user()
    return jsonify({
        **user.to_dict(),
        "platforms": {
            "pyqportal":     current_app.config["PYQPORTAL_URL"],
            "mcq_quiz":      current_app.config["MCQ_QUIZ_URL"],
            "lab_practice":  current_app.config["LAB_PRACTICE_URL"],
            "passavam":      current_app.config["PASSAVAM_URL"],
            "mark_analyser": current_app.config["MARK_ANALYSER_URL"],
            "doubtundo":     current_app.config["DOUBTUNDO_URL"],
        },
    })


@api_bp.route("/enroll", methods=["POST"])
@login_required
def enroll():
    user: User = get_current_user()
    data = request.get_json(silent=True) or {}

    semester = data.get("semester")
    course = data.get("course", "BCA")
    elective_subject_id = data.get("elective_subject_id")
    elective_subject_ids = data.get("elective_subject_ids")

    if not semester:
        return jsonify({"error": "semester is required."}), 400

    if elective_subject_ids is not None and not isinstance(elective_subject_ids, list):
        return jsonify({"error": "Invalid elective_subject_ids."}), 400

    user.semester = semester
    user.course = course
    user.is_onboarded = True

    core_subjects = Subject.query.filter_by(
        semester=semester, is_elective=False
    ).all()

    existing_subject_ids = {
        row[0]
        for row in db.session.query(Enrollment.subject_id)
        .filter_by(user_id=user.id)
        .all()
    }

    for subject in core_subjects:
        if subject.subject_id not in existing_subject_ids:
            db.session.add(Enrollment(
                user_id=user.id,
                subject_id=subject.subject_id,
                semester=semester,
            ))
            db.session.add(Mark(user_id=user.id, subject_id=subject.subject_id))
            existing_subject_ids.add(subject.subject_id)

    if int(semester) in (5, 6):
        elective_subject_ids = elective_subject_ids or []
        if not isinstance(elective_subject_ids, list) or len(elective_subject_ids) != 3:
            return jsonify({"error": "Please select exactly 3 professional electives."}), 400

        subjects = Subject.query.filter(
            Subject.subject_id.in_(elective_subject_ids),
            Subject.elective_group == 'pe_5',
            Subject.is_elective == True,
        ).all()

        valid_ids = {s.subject_id for s in subjects}
        if len(valid_ids) != 3 or any(i not in valid_ids for i in elective_subject_ids):
            return jsonify({"error": "Invalid professional elective selection."}), 400

        for elective in subjects:
            if elective.subject_id not in existing_subject_ids:
                db.session.add(Enrollment(
                    user_id=user.id,
                    subject_id=elective.subject_id,
                    semester=semester,
                ))
                db.session.add(Mark(user_id=user.id, subject_id=elective.subject_id))
                existing_subject_ids.add(elective.subject_id)
    else:
        if elective_subject_id:
            elective = db.session.get(Subject, elective_subject_id)
            if elective and elective.is_elective:
                if elective.subject_id not in existing_subject_ids:
                    db.session.add(Enrollment(
                        user_id=user.id,
                        subject_id=elective.subject_id,
                        semester=semester,
                    ))
                    db.session.add(Mark(user_id=user.id, subject_id=elective.subject_id))
                    existing_subject_ids.add(elective.subject_id)

    db.session.commit()
    return jsonify({"ok": True, "semester": semester})


@api_bp.route("/subjects")
@login_required
def subjects():
    user: User = get_current_user()

    if user.semester is None or not user.is_onboarded:
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
        .options(joinedload(Enrollment.subject))
        .all()
    )

    marks_map = _get_marks_map(user.id)
    result = []
    marks_entered = 0

    for enr in enrollments:
        subj = enr.subject
        structure = get_mark_structure(int(subj.credit))
        mark_row = marks_map.get(subj.subject_id)

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

    on_track = _count_on_track(enrollments, marks_map)

    return jsonify({
        "semester": user.semester,
        "subjects": result,
        "stats": {
            "total_subjects": len(enrollments),
            "marks_entered": marks_entered,
            "on_track_for_aplus": on_track,
        },
    })


@api_bp.route("/electives/<int:semester>")
@login_required
def electives(semester: int):
    subjects = Subject.query.filter_by(
        semester=semester, is_elective=True
    ).all()
    return jsonify({"electives": [s.to_dict() for s in subjects]})


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

    for field in ("isa", "cp", "lb", "ld", "sea1"):
        if field in data:
            raw = data[field]
            if raw is None:
                setattr(mark_row, field, None)
            else:
                clamped = max(0.0, min(float(raw), structure[field]))
                setattr(mark_row, field, clamped)

    db.session.commit()

    grade_result = compute_grade_requirements(
        int(subj.credit),
        isa=mark_row.isa, cp=mark_row.cp,
        lb=mark_row.lb, ld=mark_row.ld, sea1=mark_row.sea1,
    )
    return jsonify({"marks": mark_row.to_dict(), "grades": grade_result})


@api_bp.route("/grades/<int:subject_id>")
@login_required
def grades(subject_id: int):
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


@api_bp.route("/focus")
@login_required
def focus():
    user: User = get_current_user()

    enrollments = (
        Enrollment.query
        .filter_by(user_id=user.id, semester=user.semester)
        .options(joinedload(Enrollment.subject))
        .all()
    )

    marks_map = _get_marks_map(user.id)
    subjects_with_marks = []
    for enr in enrollments:
        subj = enr.subject
        mark_row = marks_map.get(subj.subject_id)
        marks = {}
        if mark_row:
            marks = {
                "isa": mark_row.isa, "cp": mark_row.cp,
                "lb": mark_row.lb, "ld": mark_row.ld, "sea1": mark_row.sea1,
            }
        subjects_with_marks.append({**subj.to_dict(), "marks": marks})

    ranked, no_data = compute_focus_priority(subjects_with_marks)
    return jsonify({"ranked": ranked, "no_data": no_data})


@api_bp.route("/notifications")
@login_required
def notifications():
    user = get_current_user()
    anns = (
        Announcement.query
        .order_by(Announcement.created_at.desc())
        .limit(20)
        .all()
    )

    read_ids = set()
    if user:
        read_records = AnnouncementRead.query.filter_by(user_id=user.id).all()
        read_ids = {r.announcement_id for r in read_records}

    result = []
    unread_count = 0
    for a in anns:
        is_read = a.id in read_ids
        if not is_read:
            unread_count += 1
        result.append({
            "id": a.id,
            "title": a.title,
            "body": a.body,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "is_read": is_read,
        })

    return jsonify({
        "notifications": result,
        "unread_count": unread_count,
    })


@api_bp.route("/notifications/<int:announcement_id>/read", methods=["POST"])
@login_required
def mark_notification_read(announcement_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    existing = AnnouncementRead.query.filter_by(
        user_id=user.id, announcement_id=announcement_id
    ).first()
    if not existing:
        db.session.add(AnnouncementRead(user_id=user.id, announcement_id=announcement_id))
        db.session.commit()

    return jsonify({"success": True, "announcement_id": announcement_id, "is_read": True})


@api_bp.route("/notifications/<int:announcement_id>/unread", methods=["POST"])
@login_required
def mark_notification_unread(announcement_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    AnnouncementRead.query.filter_by(
        user_id=user.id, announcement_id=announcement_id
    ).delete(synchronize_session=False)
    db.session.commit()

    return jsonify({"success": True, "announcement_id": announcement_id, "is_read": False})


@api_bp.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_notifications_read():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    anns = Announcement.query.all()
    existing_reads = {
        r.announcement_id
        for r in AnnouncementRead.query.filter_by(user_id=user.id).all()
    }
    for a in anns:
        if a.id not in existing_reads:
            db.session.add(AnnouncementRead(user_id=user.id, announcement_id=a.id))
    db.session.commit()

    return jsonify({"success": True, "unread_count": 0})

