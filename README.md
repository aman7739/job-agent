# Job Digest Agent &bull; Autonomous Career Intelligence Pipeline

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-194%20passing-success.svg)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An autonomous job discovery and delivery pipeline built with Python 3.12, FastAPI, and PostgreSQL. It tracks both **Internships** and **Full-Time** fresher software engineering opportunities for Batch 2027 graduates.

The pipeline monitors **10 Permitted Sources** twice daily (**08:00 AM** & **07:00 PM** IST), cleans and deduplicates postings, scores matches against candidate preferences, and dispatches formatted digests via Telegram and Email.

---

## Architecture & Data Flow

```
[10 Permitted Sources]
 ├── ATS APIs: Greenhouse, Lever, Ashby, SmartRecruiters, Workable
 ├── Search & Aggregator APIs: Adzuna, Jooble, Remotive, Arbeitnow
 └── Email Alerts: IMAP header-first parser (Mailbox A)
        │
        ▼
[Fault-Isolated Runner] ──> Logs execution health to `source_runs`
        │
        ▼
[Normalization & Deduplication] ──> Deterministic SHA-256 fingerprinting
        │
        ▼
[10-Point Scoring Algorithm] ──> Strong Match (≥7.0) & Maybe Match (4.0–6.9)
        │
        ▼
[Dual-Channel Delivery]
 ├── Telegram Bot (4,096 char safe chunking)
 └── SMTP Email (STARTTLS, isolated Mailbox B)
        │
        ▼
[FastAPI Web Dashboard & In-App APScheduler]
```

---

## Key Features

- **10 Permitted Sources:** Ingests jobs via ATS APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workable), search APIs (Adzuna, Jooble, Remotive, Arbeitnow), and inbound email alerts.
- **Zero Web Scraping:** Strictly complies with platform terms—no Selenium, Playwright, or DOM scraping of LinkedIn/Naukri.
- **Deduplication:** Computes deterministic SHA-256 fingerprints across normalized company, title, and URL fields.
- **10-Point Scoring Algorithm:** Evaluates opportunities against roles, skills, experience level, and preferred locations with hard knockout guards for senior roles.
- **Urgent Deadline Detection:** Dispatches instant alerts for opportunities expiring in $\le 4$ hours.
- **Private Web Dashboard:** Authenticated FastAPI interface with Argon2id password hashing, weekly application counters, dynamic profile editor, and manual job entry.

---

## Quickstart

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/aman7739/job-agent.git
cd job-agent

# Create and activate virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Key environment variables:
- `DATABASE_URL`: PostgreSQL connection string (Neon Serverless with `sslmode=require`).
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: Telegram bot credentials for delivery alerts.
- `SMTP_*`: Outgoing credentials for digest delivery (Mailbox B).
- `IMAP_*`: Incoming credentials for email alert ingestion (Mailbox A).
- `ADZUNA_*`: Optional Adzuna API credentials.
- `DASHBOARD_PASSWORD_HASH`: Argon2id password hash for dashboard login.
- `SESSION_SECRET`: 32-byte secret for signed session cookies.

### 3. Running the Application

```bash
# Run the ingestion and scoring pipeline manually
python -m job_digest.run

# Start the web dashboard and in-app scheduler
uvicorn job_digest.web:app --host 0.0.0.0 --port 8000 --reload

# Build the public showcase site
python site/build.py
```

### 4. Running Tests

```bash
pytest -v
```

---

## Cloud Deployment

- **Web Dashboard & Scheduler:** Hosted on Render using container deployment (`Dockerfile`), with in-app APScheduler triggering digests at 08:00 AM & 07:00 PM IST. A 10-minute keepalive heartbeat prevents sleep mode.
- **Database:** Neon Serverless PostgreSQL with connection pooling.
- **Backup Runner:** GitHub Actions workflow (`.github/workflows/daily-digest.yml`) retained as secondary fallback.
- **Public Showcase:** Hosted on GitHub Pages via `.github/workflows/pages.yml`.

---

## Operational Limitations & Security

1. **Single-User Scope:** Designed strictly for personal career tracking; no public registration or multi-tenant complexity.
2. **Data Privacy:** Public showcase site is completely decoupled and never exposes candidate notes, profiles, or job application data.
3. **Manual Submissions:** The agent identifies and scores opportunities; applications are submitted manually by the candidate.
4. **Rate Limits:** Respects third-party API rate limits with backoff and sequential pacing.

---

## Documentation

- **[Architecture Decision Records](docs/decisions.md):** Core architecture decisions (ADR 001 to ADR 010).
- **[Operational Runbook](docs/runbook.md):** Daily routine, troubleshooting, and manual triggers.
- **[Deployment Guide](docs/deployment.md):** Cloud deployment on Render, Neon, and GitHub Pages.
- **[Backup & Recovery](docs/backup_plan.md):** Snapshot and recovery procedures.

---

## License

This project is licensed under the MIT License.
