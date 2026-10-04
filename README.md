# Job Digest Agent &bull; Autonomous Career Intelligence Pipeline

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-158%20passing-success.svg)](https://pytest.org/)
[![Status](https://img.shields.io/badge/status-production--v1.0.0-emerald.svg)]()
[![Compliance](https://img.shields.io/badge/compliance-zero--scraping%20charter-blue.svg)]()

An autonomous, fault-isolated job intelligence system designed for a final-year B.Tech CSE (Batch 2027) graduate. The agent actively discovers and tracks opportunities across two parallel priority tracks:
1. **Internships & Apprenticeships:** 3 to 6-month engineering internships with stipends.
2. **Full-Time Fresher Roles:** Graduate Engineer Trainee (GET), Associate Software Engineer, and Junior Backend roles requiring 0 to 1 years experience.

The pipeline monitors 8 permitted ATS and search feeds twice daily (08:00 AM & 07:00 PM IST), cleans and deduplicates listings, evaluates opportunities using a deterministic 10-point scoring algorithm, delivers digests via Telegram and SMTP Email, and dispatches immediate high-priority alerts for urgent roles closing in $\le 4$ hours.

---

## Architecture & Data Flow

```
[8 Permitted Sources]
 ├── Greenhouse API (slug pacing)
 ├── Lever API (slug pacing)
 ├── Ashby API (isListed=True)
 ├── SmartRecruiters API (public REST)
 ├── Workable (v3 API / v1 Widget fallback)
 ├── Adzuna Search API (5 batches per run)
 ├── Remotive API (remote feed <= 4/day)
 └── IMAP Email Alerts (Mailbox A, SSL Port 993)
        │
        ▼
[Fault-Isolated Runner] ──> Logs metrics to `source_runs` table
        │
        ▼
[Normalization Engine]
 ├── HTML tag stripping & whitespace sanitization
 ├── Location canonicalization (Gurgaon -> Gurugram, Calcutta -> Kolkata)
 ├── URL tracker removal (strips UTMs, ref tokens)
 ├── Anti-Trap regex extractors: 'C', 'Go', 'REST API'
 └── Salary/Stipend parser (LPA range, monthly INR stipend)
        │
        ▼
[Deduplication & Freshness Cutoff]
 ├── Corporate suffix normalization (Inc., Pvt. Ltd., Corp)
 ├── Deterministic SHA-256 fingerprint: sha256(company | title | location)
 └── 48-Hour Freshness Window: Discards stale listings (> 48h old)
        │
        ▼
[10-Point Scoring Algorithm]
 ├── Hard Filters: Drop Senior, Staff, Lead; drop > 2 yrs exp; match 2027 batch
 ├── Skills Overlap (4.0 pts): Python, FastAPI, PostgreSQL, React, Linux, Docker
 ├── Role Match (3.0 pts): Backend, Software Engineer, Full Stack
 ├── Level Match (2.0 pts): Internships / 0-year Fresher roles
 └── Location Match (1.0 pt): Delhi NCR, Bengaluru, Mumbai, Pune, Kolkata, Remote
        │
        ▼
[Dual-Channel Delivery & Fast-Track Urgency]
 ├── Twice-Daily Cadence: 08:00 AM & 07:00 PM IST
 ├── Urgent Alerts (<= 4h left): Instant dispatch via Telegram & Email
 ├── Telegram Bot: 4,096 char safe chunking (preserves Markdown links)
 └── SMTP Email: STARTTLS Port 587 (isolated Mailbox B)
        │
        ▼
[Private Web Dashboard & Public Showcase]
 ├── Private Dashboard: FastAPI + Argon2id + PWA + 'Run & Notify Now' button
 └── Public Showcase: Static Jinja2 + Schema.org JSON-LD + GitHub Pages
```

---

## 8 Permitted Sources & Anti-Scraping Charter

The project maintains an ethical compliance boundary:
- **Zero Headless Automation:** No Selenium, Playwright, or Puppeteer DOM scraping.
- **No Direct Platform Scraping:** LinkedIn, Naukri, and Indeed are never directly crawled.
- **Dual-Mailbox Separation:**
  - **Mailbox A (Alerts Inbox):** Receives official forwarded email alerts from job platforms; read via SSL IMAP (Port 993) using an App Password.
  - **Mailbox B (Notifications Inbox):** Receives the final daily digests via SMTP (Port 587 STARTTLS) to prevent circular loops.
- **Rate-Limited Official APIs:** Sequential pacing across public ATS endpoints (Greenhouse, Lever, Ashby, SmartRecruiters, Workable) and official search APIs (Adzuna, Remotive).

---

## 10-Point Scoring Algorithm

Postings surviving the hard filters (excluding Senior/Lead roles, experience $> 2$ years, or incompatible batches) are scored deterministically:

| Component | Max Points | Evaluation Logic |
|---|---|---|
| **Skills Overlap** | **4.0 pts** | Matches candidate stack (Python, FastAPI, SQL, React, Linux, Docker). 4+ matches = 4.0; 3 matches = 3.0; 2 matches = 2.0; 1 match = 1.0. |
| **Role Match** | **3.0 pts** | Title match for Software Engineer, Backend Engineer, Systems Engineer, or Full Stack. |
| **Experience Level** | **2.0 pts** | 2.0 pts for Internships, Apprenticeships, GET, or 0-year Fresher roles. |
| **Preferred Location** | **1.0 pt** | Delhi NCR, Bengaluru, Mumbai, Pune, Kolkata, Indore, or Remote. |

The candidate sets a minimum score threshold (default: $\ge 7.0 / 10$) to receive notifications.

---

## Delivery Cadence & Urgent Expiring Alerts

- **Twice-Daily Automated Delivery:** Scheduled at **08:00 AM IST** (morning review) and **07:00 PM IST** (evening review) via GitHub Actions cron and local APScheduler.
- **Immediate Urgent Alerts:** When an eligible posting has a deadline closing in $\le 4$ hours, the agent bypasses the daily batch schedule and sends an instant high-priority notification to Telegram and Email.
- **On-Demand Web Button:** The private dashboard provides a **⚡ Check & Notify Now** button (`POST /jobs/run-now`) allowing manual ad-hoc scans on demand.

---

## Local Development & Setup

### 1. Prerequisites
- Python 3.12+
- PostgreSQL or Supabase account
- Git

### 2. Environment Installation
```bash
# Clone the repository
git clone https://github.com/KRAMA/AI-AGENT.git
cd "AI AGENT"

# Create virtual environment
py -3.12 -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables Configuration
Copy `.env.example` to `.env` and configure your credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | Supabase / PostgreSQL connection pooler string (Port 6543 for IPv4 compatibility). |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot token from @BotFather. |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for delivery alerts. |
| `SMTP_HOST` | Outgoing SMTP host (e.g. `smtp.gmail.com`). |
| `SMTP_PORT` | SMTP port (587 STARTTLS). |
| `SMTP_USER` | Sending mailbox username (Mailbox B). |
| `SMTP_PASSWORD` | App Password for Mailbox B. |
| `NOTIFICATION_EMAIL` | Destination email address receiving the digests. |
| `IMAP_HOST` | Incoming IMAP server for alert forwarding (Mailbox A). |
| `IMAP_PORT` | IMAP SSL port (993). |
| `IMAP_USER` | Alerts mailbox username (Mailbox A). |
| `IMAP_PASSWORD` | App Password for Mailbox A. |
| `ADZUNA_APP_ID` | Adzuna API application ID. |
| `ADZUNA_APP_KEY` | Adzuna API application key. |
| `DASHBOARD_PASSWORD_HASH` | Argon2id password hash for single-user dashboard login. |
| `SESSION_SECRET` | 32-byte secret for signing cryptographic session cookies. |
| `WEBHOOK_TOKEN` | Secret token protecting the `POST /api/trigger` endpoint. |
| `PORT` | Local web port (default: 8000). |

To generate an Argon2 password hash:
```bash
python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('your_password'))"
```

### 4. Running Tests
Run the complete test suite across all sessions:
```bash
pytest -v
```

### 5. Running the Pipeline Manually
```bash
python -m job_digest.main
```

### 6. Starting the Web Dashboard
```bash
uvicorn job_digest.web:app --host 0.0.0.0 --port 8000 --reload
```
Navigate to `http://localhost:8000/login` in your browser.

### 7. Building the Static Showcase Site
```bash
python site/build.py
```
Compiled HTML, CSS, visual assets, `sitemap.xml`, `robots.txt`, and `llms.txt` will be written into `dist/`.

---

## Cloud Deployment Architecture

- **Autonomous Crawler:** GitHub Actions cron (`.github/workflows/daily-digest.yml`) triggers twice daily (`30 2,13 * * *` UTC) on GitHub's infrastructure and pushes to Supabase PostgreSQL.
- **Private Web Dashboard:** Deployed as a secure container (`Dockerfile`, non-root `appuser`) on a free host (Render Blueprint: `render.yaml`). A 10-minute external ping (UptimeRobot) to `GET /health` prevents sleep mode.
- **Public Showcase Site:** Compiled and deployed to GitHub Pages via `.github/workflows/pages.yml` on push to `main`. Custom domain DNS setup is documented in `docs/domain_setup.md`.

---

## Operational Limitations & Security Boundaries

1. **Strictly Single-User:** Built exclusively for one candidate. No multi-tenant accounts or public user registrations exist.
2. **Air-Gap Privacy:** The public showcase site never exposes candidate profiles, application statuses, personal notes, or internal digest records.
3. **Manual Submissions:** The agent curates and scores opportunities; the user always clicks the direct link to review and submit applications themselves on employer sites.
4. **Third-Party Rate Limits:** Free-tier ATS and search feeds operate under modest rate limits; sequential delays and caching safeguards prevent aggressive polling.
5. **Database Connection Pool:** Serverless tasks use `NullPool` to prevent hanging connection exhaustion.

---

## License

This project is licensed under the MIT License for educational and personal career discovery use.
