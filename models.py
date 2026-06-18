"""
models.py — SQLAlchemy database models.

Matches Section 6 of the PRD exactly.  Field names, types, and constraints
are taken directly from Tables 12–15 in the document.

Schema overview (Section 6.5):
  users (1) ── (many) enrollments (many) ── (1) subjects
  users (1) ── (many) marks       (many) ── (1) subjects

Every marks query is scoped to WHERE user_id = current_user.id.
No student-facing endpoint may accept an arbitrary user_id.
"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """
    Section 6.1 — users table.
    A student's identity is their college Google account email.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    # Set during onboarding; nullable until the student completes setup.
    semester = db.Column(db.Integer, nullable=True)
    course = db.Column(db.String(100), nullable=True)
    # Derived from email domain (e.g. "Marian College Kuttikkanam").
    college = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Becomes True after the student completes the onboarding flow.
    is_onboarded = db.Column(db.Boolean, default=False, nullable=False)

    enrollments = db.relationship("Enrollment", back_populates="user", lazy="dynamic")
    marks = db.relationship("Mark", back_populates="user", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "semester": self.semester,
            "course": self.course,
            "college": self.college,
            "is_onboarded": self.is_onboarded,
        }


class Subject(db.Model):
    """
    Section 6.2 — subjects table.
    Seeded once by the admin; shared across all students.
    The credit value determines the full mark structure (Section 3.2).
    """

    __tablename__ = "subjects"

    subject_id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(255), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    # Stored as Float to accommodate 3-credit subjects (7.5 per component).
    credit = db.Column(db.Float, nullable=False)
    is_elective = db.Column(db.Boolean, default=False, nullable=False)
    # Groups subjects that share an elective choice (e.g. "lang_1_2", "spec_3_4").
    # Null for core subjects.
    elective_group = db.Column(db.String(100), nullable=True)

    enrollments = db.relationship("Enrollment", back_populates="subject")
    marks = db.relationship("Mark", back_populates="subject")

    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "semester": self.semester,
            "credit": self.credit,
            "is_elective": self.is_elective,
            "elective_group": self.elective_group,
        }


class Enrollment(db.Model):
    """
    Section 6.3 — enrollments table.
    Links a student to the specific subjects they are taking in a given semester.
    """

    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.subject_id"), nullable=False
    )
    semester = db.Column(db.Integer, nullable=False)

    user = db.relationship("User", back_populates="enrollments")
    subject = db.relationship("Subject", back_populates="enrollments")

    __table_args__ = (
        db.UniqueConstraint("user_id", "subject_id", name="uq_enrollment"),
    )


class Mark(db.Model):
    """
    Section 6.4 — marks table.
    Stores every mark component a student enters for a subject.
    SEA2 remains null — it is never a student-entered field.
    It is reserved for a future phase where official results could be imported.
    """

    __tablename__ = "marks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.subject_id"), nullable=False
    )

    # CCA sub-components (Section 3.1.1)
    isa = db.Column(db.Float, nullable=True)
    cp = db.Column(db.Float, nullable=True)
    lb = db.Column(db.Float, nullable=True)
    ld = db.Column(db.Float, nullable=True)

    # SEA1
    sea1 = db.Column(db.Float, nullable=True)

    # SEA2 — never entered by the student; reserved for future import.
    sea2 = db.Column(db.Float, nullable=True)

    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="marks")
    subject = db.relationship("Subject", back_populates="marks")

    __table_args__ = (
        db.UniqueConstraint("user_id", "subject_id", name="uq_mark"),
    )

    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "isa": self.isa,
            "cp": self.cp,
            "lb": self.lb,
            "ld": self.ld,
            "sea1": self.sea1,
            "sea2": self.sea2,
        }
