from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    semester = db.Column(db.Integer, nullable=True, index=True)
    course = db.Column(db.String(100), nullable=True)
    college = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_onboarded = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_blocked = db.Column(db.Boolean, default=False, nullable=False, index=True)
    blocked_at = db.Column(db.DateTime, nullable=True)

    reset_token_hash = db.Column(db.String(255), nullable=True, index=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    enrollments = db.relationship("Enrollment", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    marks = db.relationship("Mark", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "semester": self.semester,
            "course": self.course,
            "college": self.college,
            "is_onboarded": self.is_onboarded,
            "is_blocked": self.is_blocked,
        }


class Subject(db.Model):
    __tablename__ = "subjects"

    subject_id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(255), nullable=False)
    semester = db.Column(db.Integer, nullable=False, index=True)
    credit = db.Column(db.Float, nullable=False)
    is_elective = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    elective_group = db.Column(db.String(100), nullable=True)

    enrollments = db.relationship("Enrollment", back_populates="subject")
    marks = db.relationship("Mark", back_populates="subject")

    __table_args__ = (
        db.Index("ix_subjects_sem_elective", "semester", "is_elective", "is_active"),
    )

    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "semester": self.semester,
            "credit": self.credit,
            "is_elective": self.is_elective,
            "elective_group": self.elective_group,
        }


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    creator = db.relationship("User", backref="announcements")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.subject_id"), nullable=False, index=True)
    semester = db.Column(db.Integer, nullable=False)

    user = db.relationship("User", back_populates="enrollments")
    subject = db.relationship("Subject", back_populates="enrollments")

    __table_args__ = (
        db.UniqueConstraint("user_id", "subject_id", name="uq_enrollment"),
        db.Index("ix_enrollments_user_semester", "user_id", "semester"),
    )


class Mark(db.Model):
    __tablename__ = "marks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.subject_id"), nullable=False, index=True)

    isa = db.Column(db.Float, nullable=True)
    cp = db.Column(db.Float, nullable=True)
    lb = db.Column(db.Float, nullable=True)
    ld = db.Column(db.Float, nullable=True)
    sea1 = db.Column(db.Float, nullable=True)
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


class AnnouncementRead(db.Model):
    __tablename__ = "announcement_reads"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("announcement_reads", cascade="all, delete-orphan", lazy="dynamic"))
    announcement = db.relationship("Announcement", backref=db.backref("reads", cascade="all, delete-orphan", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "announcement_id", name="uq_user_announcement_read"),
        db.Index("ix_announcement_reads_user_announcement", "user_id", "announcement_id"),
    )

