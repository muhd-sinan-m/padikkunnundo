"""
grading.py — Core academic grading engine.

This module implements Section 3 of the PRD exactly.
Every constant, formula, and classification rule traces directly back to
the document.  Nothing is invented here.

Public API
──────────
  get_mark_structure(credit)          → dict of max marks per component
  compute_grade_requirements(credit, isa, cp, lb, ld, sea1)
                                      → full grade requirement result
  compute_focus_priority(subjects)    → ranked list + no-data list
"""

from __future__ import annotations
from typing import Optional

# ── Section 3.2: Credit-Based Mark Distribution ───────────────────────────────
# Source: Table 3 in the PRD.
# Key is the credit value; value is the maximum mark for every component.

CREDIT_STRUCTURE: dict[int, dict[str, float]] = {
    5: {"total": 125, "cca": 50, "isa": 10, "cp": 10, "lb": 15, "ld": 15, "sea1": 15, "sea2": 60},
    4: {"total": 100, "cca": 40, "isa": 10, "cp": 10, "lb": 10, "ld": 10, "sea1": 20, "sea2": 40},
    3: {"total": 75,  "cca": 30, "isa": 7.5, "cp": 7.5, "lb": 7.5, "ld": 7.5, "sea1": 15, "sea2": 30},
    2: {"total": 50,  "cca": 20, "isa": 5,   "cp": 5,   "lb": 5,   "ld": 5,   "sea1": 10, "sea2": 20},
}

# ── Section 3.3: Grade Thresholds ────────────────────────────────────────────
# Grades are awarded as a percentage of the subject's total mark.

GRADE_THRESHOLDS: dict[str, float] = {
    "A+":   0.90,
    "A":    0.80,
    "B+":   0.70,
    "Pass": 0.40,
}

# Order matters for display: best grade first.
GRADE_ORDER: list[str] = ["A+", "A", "B+", "Pass"]

# ── Section 3.5: Focus Priority / Difficulty Classification ──────────────────
# Percentage = SEA2 marks needed ÷ SEA2 maximum.
# Bands are left-inclusive, right-exclusive.
# Note: "Not achievable" applies only when sea2_needed > sea2_max (literally
# impossible). The PRD's worked example (57.5 / 60 = 95.8%) shows "very hard"
# rather than "not achievable" — this is the authoritative interpretation.

DIFFICULTY_BANDS: list[tuple] = [
    # (lower_bound_inclusive, upper_bound_exclusive, key, label, css_class)
    (0.00, 0.40, "easy",        "On track",                 "status-green"),
    (0.40, 0.65, "attention",   "Needs attention",           "status-yellow"),
    (0.65, 0.90, "critical",    "Critical — focus here",     "status-red"),
    (0.90, None, "very_hard",   "Very hard",                 "status-red"),
]


# ── Public helpers ────────────────────────────────────────────────────────────

def get_mark_structure(credit: int) -> dict[str, float]:
    """Return the maximum marks for every component for a given credit value."""
    if credit not in CREDIT_STRUCTURE:
        raise ValueError(f"Unknown credit value: {credit}. Must be 2, 3, 4, or 5.")
    return CREDIT_STRUCTURE[credit]


def _classify_difficulty(sea2_needed: float, sea2_max: float) -> tuple[str, str, str]:
    """
    Classify how hard it is to achieve a grade by what fraction of SEA2 is needed.

    Returns (key, label, css_class).
    """
    if sea2_max == 0:
        return ("impossible", "Not mathematically achievable", "status-grey")

    pct = sea2_needed / sea2_max
    for lo, hi, key, label, css in DIFFICULTY_BANDS:
        if hi is None or pct < hi:
            return key, label, css

    # Fallback (should not be reached if bands are exhaustive)
    return ("impossible", "Not mathematically achievable", "status-grey")


def compute_grade_requirements(
    credit: int,
    isa: Optional[float] = None,
    cp: Optional[float] = None,
    lb: Optional[float] = None,
    ld: Optional[float] = None,
    sea1: Optional[float] = None,
) -> dict:
    """
    Section 3.4 — A+ Calculator core formula.

    Given a subject's credit value and any marks the student has entered so far,
    compute how many SEA2 marks are needed for each grade.

    Returns a dict:
      {
        "secured": float,          # sum of marks entered so far
        "sea2_max": float,         # maximum possible SEA2 mark
        "total": float,            # maximum possible total mark
        "structure": dict,         # full mark structure for this credit
        "grades": {
          "A+": {
            "sea2_needed": float,
            "sea2_max": float,
            "status": "secured" | "achievable" | "not_achievable",
            "difficulty_key": str,
            "difficulty_label": str,
            "css_class": str,
          },
          ...
        }
      }
    """
    structure = get_mark_structure(credit)
    total: float = structure["total"]
    sea2_max: float = structure["sea2"]

    # Section 3.4: Secured So Far = ISA + CP + LB + LD + SEA1 (null = 0)
    secured: float = sum(
        v for v in (isa, cp, lb, ld, sea1) if v is not None
    )

    grades: dict = {}
    for grade in GRADE_ORDER:
        threshold_pct = GRADE_THRESHOLDS[grade]
        target: float = total * threshold_pct
        sea2_needed: float = target - secured

        if sea2_needed <= 0:
            # Grade is already secured regardless of SEA2 performance.
            grades[grade] = {
                "sea2_needed": 0.0,
                "sea2_max": sea2_max,
                "status": "secured",
                "difficulty_key": "easy",
                "difficulty_label": "Already secured",
                "css_class": "status-green",
            }
        elif sea2_needed > sea2_max:
            # Grade is mathematically not achievable.
            grades[grade] = {
                "sea2_needed": sea2_needed,
                "sea2_max": sea2_max,
                "status": "not_achievable",
                "difficulty_key": "impossible",
                "difficulty_label": "Not mathematically achievable",
                "css_class": "status-red" if grade == "A+" else "status-grey",
            }
        else:
            diff_key, diff_label, css = _classify_difficulty(sea2_needed, sea2_max)
            grades[grade] = {
                "sea2_needed": sea2_needed,
                "sea2_max": sea2_max,
                "status": "achievable",
                "difficulty_key": diff_key,
                "difficulty_label": diff_label,
                "css_class": "status-green" if grade == "A+" else css,
            }

    return {
        "secured": secured,
        "sea2_max": sea2_max,
        "total": total,
        "structure": structure,
        "grades": grades,
    }


def compute_focus_priority(subjects_with_marks: list[dict]) -> tuple[list, list]:
    """
    Section 3.5 / 7.4 — Focus Priority ranking.

    Given a list of subjects (each with 'credit' and 'marks' keys), rank them
    by descending A+ difficulty so the most urgent subject appears first.

    Subjects with no marks entered are excluded from the ranking and returned
    separately with a neutral 'no data' state.

    Parameters
    ----------
    subjects_with_marks : list of dicts, each with at minimum:
        {
          "subject_id": int,
          "subject_name": str,
          "credit": int,
          "marks": {
            "isa": float | None, "cp": ..., "lb": ..., "ld": ..., "sea1": ...
          }
        }

    Returns
    -------
    ranked : list sorted by descending urgency
    no_data : list of subjects with zero marks entered
    """
    ranked: list[dict] = []
    no_data: list[dict] = []

    for subject in subjects_with_marks:
        marks = subject.get("marks") or {}
        has_any_mark = any(
            marks.get(k) is not None
            for k in ("isa", "cp", "lb", "ld", "sea1")
        )

        if not has_any_mark:
            no_data.append({**subject, "priority_pct": None, "status": "no_data"})
            continue

        result = compute_grade_requirements(
            credit=int(subject["credit"]),
            isa=marks.get("isa"),
            cp=marks.get("cp"),
            lb=marks.get("lb"),
            ld=marks.get("ld"),
            sea1=marks.get("sea1"),
        )

        aplus = result["grades"]["A+"]

        # Assign a sortable priority percentage:
        #   • Already secured  → -1   (lowest urgency, shown at the bottom)
        #   • Not achievable   → 1.1  (special, shown separately but ranked)
        #   • Achievable       → actual fraction of SEA2 needed
        if aplus["status"] == "secured":
            priority_pct = -1.0
        elif aplus["status"] == "not_achievable":
            priority_pct = 1.1
        else:
            priority_pct = aplus["sea2_needed"] / aplus["sea2_max"]

        ranked.append({
            **subject,
            "priority_pct": priority_pct,
            "sea2_needed_aplus": aplus["sea2_needed"],
            "sea2_max": aplus["sea2_max"],
            "status": aplus["status"],
            "difficulty_key": aplus["difficulty_key"],
            "difficulty_label": aplus["difficulty_label"],
            "css_class": aplus["css_class"],
            "secured": result["secured"],
        })

    # Sort: most urgent (highest priority_pct) first.
    ranked.sort(key=lambda x: x["priority_pct"], reverse=True)
    return ranked, no_data
