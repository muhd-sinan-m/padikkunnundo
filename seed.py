"""
seed.py — Populate the subjects table from the PRD (Section 4).

Run once after creating the database:
    python seed.py

Subject and credit data is taken directly from Tables 7–10 in the document.
Semesters 5 and 6 are omitted — they are not yet finalized (Section 4.4 note).
"""

from app import create_app
from models import db, Subject


# ── Section 4: Subjects, Credits, and Electives ───────────────────────────────
# Format: (subject_name, semester, credit, is_elective, elective_group)

SUBJECTS: list[tuple] = [
    # ── Semester 1 (Table 7) ─────────────────────────────────────────────────
    ("Discrete Mathematics",                    1, 4, False, None),
    ("Digital Fundamentals",                    1, 4, False, None),
    ("Fundamentals of Programming Using C++",   1, 4, False, None),
    ("English for Science",                     1, 3, False, None),
    ("Cyber Laws and Security",                 1, 3, False, None),
    ("Software Lab in C++",                     1, 2, False, None),
    # Language elective group — spans Sem 1 and Sem 2.
    # Only 2 of 6 options are confirmed; 4 are pending.
    ("Spanish 1",                               1, 3, True,  "lang_1_2"),
    ("French 1",                                1, 3, True,  "lang_1_2"),

    # ── Semester 2 (Table 8) ─────────────────────────────────────────────────
    # Note (Section 4.2): Language elective carries over — not re-selected.
    ("Indian Constitution: Legal and Ethical Perspectives", 2, 2, False, None),
    ("Web Technology",                          2, 2, False, None),
    ("Operating Systems",                       2, 4, False, None),
    ("Data Structures",                         2, 5, False, None),
    ("Mathematics Foundations to Computer Science ",2, 4, False, None),
    ("AEC — English",                           2, 3, False, None),
    # Language elective continues (same group as Sem 1; Sem 2 counterparts).
    ("Spanish 2",                               2, 3, True,  "lang_1_2"),
    ("French 2",                                2, 3, True,  "lang_1_2"),

    # ── Semester 3 (Table 9) ─────────────────────────────────────────────────
    ("Python Programming",                                  3, 4, False, None),
    ("Database Management Systems",                                    3, 5, False, None),
    ("Design and Analysis of Algorithms",                    3, 3, False, None),
    ("Software Engineering",                    3, 3, False, None),
    ("Quantitative Techniques",                 3, 4, False, None),
    # Specialization elective group — spans Sem 3 and Sem 4.
    # Only 1 of 4 options confirmed; 3 are pending.
    ("Feature Engineering",                     3, 3, True,  "spec_3_4"),
    ("Introduction to Cyber Security",          3, 3, True,  "spec_3_4"),
    ("Interactive Web Application Development Using PHP and MySQL ", 3, 3, True,  "spec_3_4"),
    ("Basics of Data Analytics Using Spreadsheet ",  3, 3, True,  "spec_3_4"),



    # ── Semester 4 (Table 10) ────────────────────────────────────────────────
    # Note (Section 4.3): Specialization elective carries over from Sem 3.
    ("Object Oriented Programming Using Java",  4, 5, False, None),
    ("Design Thinking and Innovation",          4, 3, False, None),
    ("Entrepreneurship and Startup Ecosystem",  4, 2, False, None),
    ("Probability Distributions and Statistical Inference", 4, 4, False, None),
    ("Artificial Intelligence",                 4, 5, False, None),
    # Specialization elective continues (same group; Sem 4 counterparts).
    ("Network Simulation",                      4, 3, True,  "spec_3_4"),
    ("Intro to ML",                             4, 3, True,  "spec_3_4"),
    ("Data Visualization ",                     4, 3, True,  "spec_3_4"),
    ("Web Application Development Using Node.js and Express.js ",                             4, 3, True,  "spec_3_4"),


]


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        existing = {s.subject_name for s in Subject.query.all()}
        added = 0

        for name, sem, credit, is_elective, group in SUBJECTS:
            if name in existing:
                print(f"  skip (already exists): {name}")
                continue
            subject = Subject(
                subject_name=name,
                semester=sem,
                credit=credit,
                is_elective=is_elective,
                elective_group=group,
            )
            db.session.add(subject)
            added += 1
            print(f"  added: {name} (Sem {sem}, {credit} credits)")

        db.session.commit()
        print(f"\nDone — {added} subject(s) added.")


if __name__ == "__main__":
    seed()
