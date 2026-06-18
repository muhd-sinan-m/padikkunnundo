# padikkunnundo.in

Personal Academic Companion Platform for Marian College Kuttikkanam students.

Built as a BCA Capstone Project by **Muhammed Sinan M**.
Every grading rule implemented in this codebase traces back directly to the PRD (`padikkunnundo_PRD.docx`).

---

## What it does

- **A+ Grade Calculator** — tells a student exactly how many marks they need in SEA2 to reach A+, A, B+, or Pass, based on CCA and SEA1 marks already secured.
- **Focus Priority** — ranks enrolled subjects by urgency so students know where to spend limited study time before SEA2.
- **Exam Schedule** — upcoming SEA1/SEA2 dates with a day-countdown; exams within 7 days are flagged urgent.
- **Important Topics** — admin-curated topic lists per subject, each linking directly to PYQPortal.
- **Ecosystem access** — one-click links to PYQPortal, the MCQ quiz platform, and the Placement Prep portal.

---

## Local setup

### Prerequisites

- Python 3.10+
- A Google Cloud project with OAuth 2.0 credentials configured (for authentication)

### 1 — Clone and install

```bash
pip install Flask Flask-SQLAlchemy authlib requests PyJWT python-dotenv
```

### 2 — Configure environment

```bash
copy .env.example .env
```

Edit `.env` and fill in:
- `SECRET_KEY` — any long random string
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — from Google Cloud Console
- `COLLEGE_DOMAIN` — the college's email domain (e.g. `mariancollege.org`)

**Google OAuth setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials.
2. Create an OAuth 2.0 Client ID (Web application).
3. Add `http://localhost:5000/auth/google/callback` to Authorised redirect URIs.
4. Copy the Client ID and Secret into `.env`.

### 3 — Initialise the database and seed subjects

```bash
python seed.py
```

This creates `padikkunnundo.db` (SQLite) and inserts all subjects from Semesters 1–4 (Section 4 of the PRD).

### 4 — Run

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

---

## Project structure

```
padikkunnundo/
├── app.py               Flask application factory
├── config.py            Configuration (all values from .env)
├── grading.py           Section 3 grading engine — the core domain logic
├── models.py            Section 6 database schema (SQLAlchemy)
├── seed.py              Section 4 subject data — run once
├── requirements.txt
├── .env.example
│
├── routes/
│   ├── auth.py          Google OAuth flow, JWT issuing, login_required decorator
│   ├── api.py           REST API endpoints (/api/*)
│   └── pages.py         Page routes (HTML via Jinja2)
│
├── templates/
│   ├── base.html        Sidebar layout + notification panel
│   ├── login.html       Section 8.3 — single Google sign-in
│   ├── onboarding.html  Section 4.5 — semester + elective selection
│   ├── dashboard.html   Section 7.1 — stats, platforms, subject grid
│   ├── marks.html       Section 7.2 — per-subject mark entry + live A+ calc
│   ├── calculator.html  Section 7.3 — focused A+ calculator view
│   ├── schedule.html    Section 7.5 — exam dates + countdown
│   └── topics.html      Section 7.6 — important topics per subject
│
└── static/
    ├── css/styles.css   Section 8 design tokens (Table 18)
    └── js/
        ├── app.js       Shared utilities + notification panel
        ├── dashboard.js Dashboard page
        ├── marks.js     My Marks page (live calculation)
        └── calculator.js A+ Calculator page
```

---

## Production deployment (AWS)

- **Database**: Set `DATABASE_URL` to a PostgreSQL connection string (AWS RDS). Install `psycopg2-binary` separately (requires PostgreSQL client libraries).
- **Static files**: Serve via a CDN or directly from Flask.
- **Session security**: Set `SECRET_KEY` to a long random value and ensure `secure=True` on cookies (HTTPS required).
- **S3**: Reserved for future file storage (Section 9.3). Key structure: `college/course/semester/subject/file-type`.

---

## Grading logic reference (Section 3)

| Credit | Total | ISA | CP | LB | LD | SEA1 | SEA2 |
|--------|-------|-----|----|----|----|------|------|
| 5      | 125   | 10  | 10 | 15 | 15 | 15   | 60   |
| 4      | 100   | 10  | 10 | 10 | 10 | 20   | 40   |
| 3      | 75    | 7.5 | 7.5| 7.5| 7.5| 15  | 30   |
| 2      | 50    | 5   | 5  | 5  | 5  | 10   | 20   |

Grade thresholds: **A+ = 90%**, **A = 80%**, **B+ = 70%**, **Pass = 40%** of total.

SEA2 needed = (Total × Grade%) − Secured So Far (ISA + CP + LB + LD + SEA1)
