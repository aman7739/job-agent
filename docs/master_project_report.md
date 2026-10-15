# Job Digest Agent — Master Architecture & Project Report

> **Project:** Autonomous Career Intelligence Pipeline & Job Digest Agent  
> **Status:** Production v1.0.0 (Live on Render & GitHub Pages)  
> **Target Candidate:** B.Tech CSE (Batch 2027)  
> **Test Suite:** 194 passing automated tests (100% green)  
> **Live Production Run:** 2,558 raw postings scanned &bull; 14 high-conviction matches delivered to Telegram

---

## 1. Executive Summary & Core Candidate Profile

The **Job Digest Agent** is a private, production-grade autonomous career discovery system built specifically for a final-year **B.Tech Computer Science and Engineering (Batch 2027)** student. 

### Core Operating Rules
1. **Dual Priority Tracks:**
   - **Internships & Apprenticeships:** 3 to 6-month software engineering internships with stipends (immediate application target).
   - **Full-Time Fresher Roles:** Graduate Engineer Trainee (GET), Associate Software Engineer, and Junior Backend Engineer requiring 0–2 years of experience (immediate application target).
2. **Strict Seniority Exclusion:** Automatically filters out Senior, Lead, Principal, Staff, Architect, Manager, and Director positions.
3. **Target Locations:** Noida, Delhi NCR, Gurugram, Kolkata, Mumbai, Pune, Bengaluru, Indore, or Remote (India).
4. **Primary Skills Focus:** Python, FastAPI, PostgreSQL, Supabase, React, JavaScript, HTML/CSS, Git/GitHub, Linux, Docker, REST APIs, ML/AI foundations.
5. **Ethical Anti-Scraping Charter:** 100% compliant with platform terms of service. Zero DOM scraping or headless automation of LinkedIn, Naukri, or Indeed. Ingestion relies exclusively on official REST APIs, public ATS career endpoints, and authorized personal email alerts.

---

## 2. Complete Technology Stack Matrix

| Layer | Technology | Version | Purpose & Implementation |
|---|---|---|---|
| **Language & Runtime** | Python | 3.12.1+ | Primary language, async/await concurrency, type hinting (`typing`, `Pydantic v2`) |
| **Web Framework** | FastAPI | 0.115+ | High-speed async REST API, dashboard routes, session authentication |
| **ASGI Web Server** | Uvicorn | 0.30+ | Production ASGI server running behind Render reverse proxy |
| **Template Engine** | Jinja2 | 3.1+ | Renders HTML email digests, web dashboard templates, and static showcase |
| **Database Engine** | PostgreSQL | 16 (Neon Serverless) | Production relational database hosted in AWS Singapore (`ap-southeast-1`) |
| **ORM & Query Builder**| SQLAlchemy | 2.0+ | Connection engine, declarative base, raw SQL execution, schema management |
| **DB Driver** | psycopg3 (`psycopg`) | 3.2+ | Modern binary driver with native PostgreSQL type adapters |
| **Connection Pool** | NullPool | Built-in | Disables idle pooling to prevent serverless PgBouncer pool exhaustion |
| **Scheduler** | APScheduler | 3.10+ | In-app `AsyncIOScheduler` firing at 08:00 AM & 07:00 PM IST with misfire grace |
| **HTTP Client** | httpx | 0.27+ | Asynchronous non-blocking HTTP requests for ATS and aggregator feeds |
| **Email Ingestion** | imaplib | Python stdlib (SSL)| Connects to Mailbox A over Port 993 in `readonly=True` mode |
| **Email Delivery** | smtplib | Python stdlib (STARTTLS)| Dispatches multipart HTML digests to Mailbox B over Port 587 |
| **Instant Alerts** | Telegram Bot API | HTTPS REST | Formatted markdown digest delivery & urgent deadline alerts |
| **Password Hashing** | Argon2id (`argon2-cffi`)| 23.1+ | Cryptographic memory-hard hashing for private dashboard authentication |
| **Uptime Monitor** | Cron-Job.org | External Cron | Pings `/health` every 10 min to keep Render awake 24/7 |
| **Containerization** | Docker | Multi-stage | Lightweight Debian-slim production container running as non-root `appuser` |
| **Cloud Hosting** | Render | Docker Web Service | Hosts private dashboard, background scheduler, and API endpoints |
| **Public Showcase** | GitHub Pages | Static HTML | Zero-JS static portfolio deployed via GitHub Actions |
| **Testing** | pytest & pytest-asyncio | 9.1+ / 1.4+ | 194 unit, integration, security, and reliability tests |

---

## 3. All Websites & Data Ingestion Sources (10 Sources)

The system ingests job data from **10 distinct, fully compliant sources**:

```
[10 Permitted Ingestion Feeds]
 ├── 1. Greenhouse API (Public JSON API &bull; 24 Verified Companies)
 ├── 2. Lever API (Public JSON API &bull; 8 Verified Companies)
 ├── 3. Ashby API (Public JSON API &bull; 4 Verified Companies)
 ├── 4. SmartRecruiters API (Public REST API &bull; 14 Verified Companies)
 ├── 5. Workable API (v3 API & v1 Widget &bull; 7 Verified Companies)
 ├── 6. Jooble API (Official Aggregator REST API &bull; India Fresher Queries)
 ├── 7. Arbeitnow API (Zero-Auth Remote Developer JSON Feed)
 ├── 8. Remotive API (Remote Developer JSON API &bull; Capped <= 4/day)
 ├── 9. Adzuna Search API (Official Job Search REST API &bull; 6 Query Groups)
 └── 10. Email Alerts (SSL IMAP Port 993 &bull; Mailbox A Platform & ATS Alerts)
```

### Detailed Source Breakdown

#### 1. Greenhouse (`job_digest/sources/greenhouse.py`)
- **API Endpoint:** `https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true`
- **Method:** Public HTTP GET (Zero auth required; respectful 0.3s slug pacing)
- **Verified Indian & Global Tech Companies (24 boards):**
  `groww`, `inmobi`, `druva`, `twilio`, `rubrik`, `samsara`, `databricks`, `okta`, `stripe`, `affirm`, `airbnb`, `gusto`, `dropbox`, `hashicorp`, `elastic`, `mongodb`, `cloudflare`, `github`, `reddit`, `pinterest`, `brex`, `carta`, `plaid`, `instacart`.

#### 2. Lever (`job_digest/sources/lever.py`)
- **API Endpoint:** `https://api.lever.co/v0/postings/{company_slug}?mode=json`
- **Method:** Public HTTP GET
- **Verified Companies (8 boards):**
  `cred`, `meesho`, `atlan`, `postman`, `hotstar`, `urbancompany`, `browserstack`, `razorpay`.

#### 3. Ashby (`job_digest/sources/ashby.py`)
- **API Endpoint:** `https://api.ashbyhq.com/posting-api/job-board/{company_slug}`
- **Method:** Public HTTP GET (Filters for `isListed=True`)
- **Verified Companies (4 boards):**
  `snowflake`, `linear`, `replit`, `vercel`.

#### 4. SmartRecruiters (`job_digest/sources/smartrecruiters.py`)
- **API Endpoint:** `https://api.smartrecruiters.com/v1/companies/{company_slug}/postings`
- **Method:** Public REST API
- **Verified Companies (14 boards):**
  `swiggy`, `freshworks`, `cars24`, `grab`, `visa`, `square`, `spotify`, `zalando`, `bosch`, `ikea`, `ubisoft`, `epicgames`, `redbull`, `volvo`.

#### 5. Workable (`job_digest/sources/workable.py`)
- **API Endpoint:** `https://apply.workable.com/api/v3/accounts/{company_slug}/jobs` (with fallback to `https://apply.workable.com/api/v1/widget/accounts/{company_slug}`)
- **Method:** Public REST / Widget API
- **Verified Companies (7 boards):**
  `hasura`, `invideo`, `browserstack`, `postman`, `curefit`, `cultfit`, `scaler`.

#### 6. Jooble Aggregator (`job_digest/sources/jooble.py`)
- **API Endpoint:** `https://jooble.org/api/{JOOBLE_API_KEY}`
- **Method:** Authenticated POST with JSON payload (Country: `in`)
- **Targeted Queries:**
  1. `python developer fresher`
  2. `backend developer intern`
  3. `software engineer trainee`
  4. `junior software engineer`
  5. `machine learning intern`
- **Fault-Tolerant:** Safely skips with zero crash if key is absent. Verified live with 75 jobs returned.

#### 7. Arbeitnow Remote Feed (`job_digest/sources/arbeitnow.py`)
- **API Endpoint:** `https://www.arbeitnow.com/api/job-board-api`
- **Method:** Public HTTP GET (Zero API key required)
- **Filtering:** Automatically captures India-eligible and global Remote software roles. Verified live with 45 jobs returned.

#### 8. Remotive (`job_digest/sources/remote.py`)
- **API Endpoint:** `https://remotive.com/api/remote-jobs?category=software-dev`
- **Method:** Public HTTP GET (Rate-capped at $\le 4$ items per run to prevent international job dilution).

#### 9. Adzuna Search API (`job_digest/sources/adzuna.py`)
- **API Endpoint:** `https://api.adzuna.com/v1/api/jobs/in/search/{page}?app_id={ID}&app_key={KEY}`
- **Method:** Authenticated REST API across 6 Boolean query groups:
  1. `python developer (fresher OR entry level OR junior)`
  2. `backend developer (fresher OR entry level OR junior)`
  3. `software engineer trainee OR graduate engineer trainee OR GET`
  4. `software developer intern OR full stack intern OR web developer intern`
  5. `AI intern OR ML intern OR machine learning intern OR data science intern`
  6. `associate software engineer OR junior software engineer`

#### 10. Email Alerts Ingestion (`job_digest/sources/email_alerts.py`)
- **Host / Protocol:** Gmail SSL IMAP on Port 993 (`readonly=True` mode)
- **Whitelisted Platforms:** LinkedIn, Naukri, Indeed, Internshala, Unstop, Instahyre, Wellfound, Cutshort, Foundit, Glassdoor, Hirist.
- **Whitelisted Direct ATS Domains:** `greenhouse.io`, `lever.co`, `smartrecruiters.com`, `ashbyhq.com`, `myworkdayjobs.com`, `amazon.jobs`.
- **Privacy Firewall:** Rejects non-job emails (banking, OTPs, personal) in < 1 ms without downloading message bodies.

---

## 4. Complete Project Directory Structure & File Inventory

```
AI AGENT/
├── .github/
│   └── workflows/
│       ├── ci.yml                     # Runs pytest & ruff on every push and PR
│       ├── daily-digest.yml           # Secondary backup runner workflow
│       ├── keepalive.yml              # GitHub-native 10-minute keepalive workflow
│       └── pages.yml                  # Builds and deploys static showcase to GitHub Pages
├── database/
│   └── schema.sql                     # Complete PostgreSQL DDL (tables, indexes, foreign keys)
├── docs/
│   ├── decisions.md                   # 20 Architecture Decision Records (ADRs 001 to 020)
│   ├── deployment.md                  # Comprehensive Render & Neon deployment runbook
│   ├── master_project_report.md       # Full master report of all tech, websites, and code paths
│   └── portfolio_summary.md           # Professional executive summary for recruiters
├── job_digest/
│   ├── __init__.py                    # Module export definitions
│   ├── config.py                      # Pydantic v2 profile models, env loaders, hard constraints
│   ├── db.py                          # SQLAlchemy engine, NullPool, session context, DDL runner
│   ├── dedup.py                       # Normalization, SHA-256 fingerprinting, sightings attribution
│   ├── digest.py                      # Digest builder, Jinja2 template renderer, partitioning
│   ├── models.py                      # Core dataclasses: Job, ScoredJob, DigestOutput, DeduplicationResult
│   ├── notify.py                      # TelegramBotNotifier, EmailNotifier, urgent alert dispatcher
│   ├── run.py                         # Master orchestrator, CLI entrypoint, local scheduler
│   ├── scoring.py                     # Deterministic 10-point scoring algorithm & hard filters
│   ├── urgency.py                     # Deadline extractor and <= 4 hour urgent detector
│   ├── web.py                         # FastAPI web dashboard, Argon2id auth, APScheduler lifespan
│   ├── sources/
│   │   ├── __init__.py                # BaseSource abstract base class
│   │   ├── adzuna.py                  # Adzuna job search API adapter
│   │   ├── arbeitnow.py               # Arbeitnow public remote developer feed
│   │   ├── ashby.py                   # Ashby ATS posting API client
│   │   ├── email_alerts.py            # IMAP SSL email alert parser
│   │   ├── greenhouse.py              # Greenhouse public boards API client
│   │   ├── jooble.py                  # Jooble REST search API client
│   │   ├── lever.py                   # Lever public postings API client
│   │   ├── remote.py                  # Remotive remote developer feed adapter
│   │   ├── smartrecruiters.py         # SmartRecruiters public REST client
│   │   └── workable.py                # Workable v3 API / v1 widget adapter
│   └── templates/
│       ├── digest.html                # Responsive HTML email digest template
│       ├── digest.txt                 # Clean plain-text digest template
│       └── web/
│           ├── base.html              # Dashboard base layout, dark mode, responsive nav
│           ├── dashboard.html         # Main dashboard: statistics, runs, interactive actions
│           ├── history.html           # Historical digest viewer with search
│           ├── jobs.html              # Master job table with status actions (saved, applied)
│           ├── login.html             # Argon2id password-protected login screen
│           ├── profile.html           # Candidate profile and skills editor
│           ├── settings.html          # Notification settings and threshold sliders
│           └── sources.html           # Live source health & 7-Day Attribution Analytics
├── reports/
│   └── ats_slug_report.csv            # Automated verification results of 50 ATS company slugs
├── scripts/
│   └── check_ats_slugs.py             # CLI scanner verifying candidate company slugs across ATSs
├── site/
│   ├── build.py                       # Static site generator for public GitHub Pages showcase
│   └── index.html                     # Public showcase HTML with Schema.org JSON-LD
├── tests/
│   ├── __init__.py                    # Test suite package
│   ├── conftest.py                    # Pytest fixtures, in-memory SQLite engine, mock data
│   ├── test_arbeitnow.py              # Tests for Arbeitnow remote feed adapter
│   ├── test_auth.py                   # Tests for Argon2id hashing and session cookie auth
│   ├── test_dedup.py                  # Tests for deduplication, normalization, and fingerprinting
│   ├── test_digest.py                 # Tests for Jinja2 rendering and partitioning
│   ├── test_email_source.py           # Tests for IMAP email alert parsing and whitelisting
│   ├── test_jooble.py                 # Tests for Jooble API adapter and fault tolerance
│   ├── test_models.py                 # Tests for Pydantic profile validation
│   ├── test_notify.py                 # Tests for Telegram chunking and SMTP multipart delivery
│   ├── test_run.py                    # Tests for master pipeline runner and source loading
│   ├── test_s13_profile_and_status.py # Tests for profile and job status transitions
│   ├── test_s14_web_and_auth.py       # Tests for web routes and dashboard endpoints
│   ├── test_s15_actions_and_settings.py# Tests for settings updates and job actions
│   ├── test_s21_audit_and_release.py  # Tests for release readiness, documentation, and security
│   ├── test_s22_final_wrapup.py       # Comprehensive end-to-end milestone audit test
│   ├── test_scoring.py                # Tests for 10-point scoring engine and hard knockouts
│   ├── test_sightings.py              # Tests for multi-source attribution and 7-day metrics
│   ├── test_slug_checker.py           # Tests for automated ATS slug scanner script
│   ├── test_sources.py                # Tests for Greenhouse, Lever, Ashby, SmartRecruiters, Workable
│   └── test_urgency_and_schedule.py   # Tests for deadline detection and cron schedule syntax
├── .env.example                       # Documented environment variable template (zero secrets)
├── .gitignore                         # Strict exclusion of .env, credentials, logs, cache
├── Dockerfile                         # Production multi-stage Docker build running as appuser
├── memory.md                          # Comprehensive persistent system memory (14 sections)
├── profile.yaml                       # Candidate profile configuration
├── README.md                          # Full GitHub project documentation and badges
├── requirements.txt                   # Frozen production dependencies
└── sources.yaml                       # 57 verified company ATS slugs and configurations
```

---

## 5. Complete Database Architecture & Schema DDL

The database schema is hosted on **Neon Serverless PostgreSQL** and executed via [`database/schema.sql`](file:///C:/Users/KRAMA/OneDrive/Desktop/AI%20AGENT/database/schema.sql):

```sql
-- 1. Seen Jobs: Deduplication and state registry
CREATE TABLE IF NOT EXISTS seen_jobs (
    fingerprint VARCHAR(64) PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) NOT NULL DEFAULT 'seen',
    user_status VARCHAR(32) NOT NULL DEFAULT 'new',
    user_action_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_seen_jobs_status ON seen_jobs(status);
CREATE INDEX IF NOT EXISTS idx_seen_jobs_last_seen ON seen_jobs(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_seen_jobs_user_status ON seen_jobs(user_status);

-- 2. Jobs: Master postings table
CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    fingerprint VARCHAR(64) NOT NULL REFERENCES seen_jobs(fingerprint) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    canonical_url TEXT NOT NULL,
    description_text TEXT,
    posted_at TIMESTAMPTZ,
    source VARCHAR(64) NOT NULL,
    is_intern BOOLEAN NOT NULL DEFAULT FALSE,
    is_apprentice BOOLEAN NOT NULL DEFAULT FALSE,
    min_years NUMERIC(3, 1),
    salary_lpa NUMERIC(6, 2),
    stipend NUMERIC(10, 2),
    batch_years TEXT[],
    matched_skills TEXT[],
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);

-- 3. Digests: History of generated and sent digests
CREATE TABLE IF NOT EXISTS digests (
    id BIGSERIAL PRIMARY KEY,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_jobs INT NOT NULL DEFAULT 0,
    internships_count INT NOT NULL DEFAULT 0,
    fulltime_count INT NOT NULL DEFAULT 0,
    new_jobs_count INT NOT NULL DEFAULT 0,
    seen_jobs_count INT NOT NULL DEFAULT 0,
    channels_notified TEXT[],
    content_html TEXT NOT NULL,
    content_text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_digests_sent_at ON digests(sent_at DESC);

-- 4. Source Runs: Health and execution monitoring
CREATE TABLE IF NOT EXISTS source_runs (
    id BIGSERIAL PRIMARY KEY,
    source_name VARCHAR(64) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    jobs_found INT NOT NULL DEFAULT 0,
    jobs_new INT NOT NULL DEFAULT 0,
    is_success BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_source_runs_source ON source_runs(source_name, started_at DESC);

-- 5. Email Messages: Idempotency log for email alerts
CREATE TABLE IF NOT EXISTS email_messages (
    message_id VARCHAR(255) PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    subject TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    jobs_extracted INT NOT NULL DEFAULT 0
);

-- 6. Job Sightings: Multi-source attribution and yield analytics (Stage 4)
CREATE TABLE IF NOT EXISTS job_sightings (
    id BIGSERIAL PRIMARY KEY,
    fingerprint VARCHAR(64) NOT NULL REFERENCES seen_jobs(fingerprint) ON DELETE CASCADE,
    source VARCHAR(64) NOT NULL,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_job_sightings_source_seen_at ON job_sightings(source, seen_at);
CREATE INDEX IF NOT EXISTS idx_job_sightings_fingerprint ON job_sightings(fingerprint);
```

---

## 6. Ingestion, Processing & 10-Point Scoring Engine

### 1. Normalization & Deduplication
- **HTML Sanitization:** Strips markup, script tags, decodes HTML entities into clean Unicode text.
- **Location Canonicalization:** Maps variations to standards (e.g., `Gurgaon` $\rightarrow$ `Gurugram`, `Calcutta` $\rightarrow$ `Kolkata`, `Bangalore` $\rightarrow$ `Bengaluru`).
- **URL Tracker Stripping:** Removes tracking parameters (`utm_*`, `ref`, `source`, `fbclid`) to obtain clean canonical application URLs.
- **Anti-Trap Word Boundary Regex:** Detects short keywords like `C`, `Go`, `REST API`, `SQL` without false-positive matching on words like *Company*, *Good*, or *Rest*.
- **Deterministic Fingerprinting:** Generates SHA-256 fingerprint:
  $$\text{SHA-256}\Big(\text{clean}(\text{company}) \parallel \text{clean}(\text{title}) \parallel \text{clean}(\text{location})\Big)$$
- **48-Hour Freshness Window:** Any posting older than 48 hours is discarded to prevent stale notifications.

### 2. Hard Knockout Filters
A job is immediately discarded if:
1. It contains senior keywords: `Senior`, `Lead`, `Principal`, `Staff`, `Architect`, `Director`, `Manager`, `Head of`.
2. Experience requirement exceeds 2 years ($> 2.0\text{ YOE}$).
3. Explicit graduation batch does not include 2027 (e.g. *Batch 2024 only*).

### 3. Deterministic 10-Point Scoring Algorithm

Postings surviving the hard filters are scored deterministically out of 10.0 points:

| Component | Max Points | Evaluation Logic |
|---|:---:|---|
| **1. Skills Overlap** | **4.0 pts** | Matches candidate skills (Python, FastAPI, SQL/PostgreSQL, React, Linux, Docker, REST APIs, Git).<br>&bull; 4+ matches = 4.0 pts<br>&bull; 3 matches = 3.0 pts<br>&bull; 2 matches = 2.0 pts<br>&bull; 1 match = 1.0 pt |
| **2. Role Alignment** | **3.0 pts** | Matches title: Software Engineer, Software Developer, Backend Developer, Systems Engineer, Full Stack Engineer. |
| **3. Experience Level** | **2.0 pts** | 2.0 pts awarded for Internships, Apprenticeships, Graduate Engineer Trainee (GET), Associate Software Engineer, or 0-year Fresher roles. |
| **4. Location Preference** | **1.0 pt** | Noida, Delhi NCR, Gurugram, Kolkata, Mumbai, Pune, Bengaluru, Indore, or Remote (India). |
| **Total Score** | **10.0 pts** | **Default Notification Threshold: $\ge 7.0$ points.** |

---

## 7. Dual-Channel Notification & Fast-Track Urgency

1. **Delivery Cadence:** Twice daily at **08:00 AM IST** (morning review) and **07:00 PM IST** (evening review).
2. **Telegram Bot Dispatch:**
   - Markdown-formatted digest split courteously into 4,096-character chunks.
   - Guaranteed preservation of markdown links across chunk boundaries.
3. **SMTP Email Dispatch:**
   - Delivers multipart HTML and plain-text emails via TLS Port 587.
   - Fully isolated: Mailbox A (read-only alerts) $\ne$ Mailbox B (notifications inbox).
4. **Fast-Track Urgency Detection ($\le 4$ Hours):**
   - The urgency engine extracts closing dates and phrases (*"applications close today"*, *"closing in 3 hours"*).
   - If an eligible job closes in $\le 4$ hours, the agent **bypasses the scheduled batch** and sends an instant high-priority alert to Telegram and Email.

---

## 8. Web Dashboard & 7-Day Attribution Analytics

The private web dashboard is accessible at **`https://job-agent-sg20.onrender.com`**:

- **Authentication:** Protected by single-user **Argon2id** password hashing with secure HTTP-only session cookies.
- **Sources & Health (`/sources`):** Displays real-time status and error messages across all 10 adapters.
- **7-Day Attribution Analytics Table:**
  - **7d Sightings:** Total times jobs were ingested by this source.
  - **Unique Jobs:** Distinct SHA-256 fingerprints found.
  - **Incremental (Exclusive) Jobs:** Jobs found **only** by this source (`HAVING count(DISTINCT source) = 1`).
  - **Saved & Applied Yield:** Velocity tracking of jobs resulting in actual candidate applications.
- **Interactive Controls:** Includes the **⚡ Check & Notify Now** button for on-demand scans.

---

## 9. 24/7 Container Keepalive & Precision Scheduling

- **Render Sleep Prevention:** Configured **Cron-Job.org** monitor sending a lightweight `GET /health` request every 10 minutes (`*/10 * * * *`).
- **Uptime Guarantee:** Prevents Render free-tier containers from spinning down after 15 minutes of inactivity.
- **Zero Delay Execution:** The warm in-app `AsyncIOScheduler` triggers crawls at **exactly 08:00:00 AM & 07:00:00 PM IST** with zero runner queue delay.
- **Startup Catch-Up:** If the container ever restarts during a run window, it checks `digests` sent timestamps and executes immediately if $> 14$ hours have elapsed.

---

## 10. Live Production Evidence & Test Summary

### 1. Test Suite Verification
- **Total Tests:** **194 passed, 0 failed (100% green)** in 9.14 seconds.
- **Test Categories:** Unit tests, integration tests, mock API adapters, security audits, schema validators, release gatekeepers.

### 2. Live Production Ingestion Run (15 October 2026)
- **Raw Roles Scanned:** **2,558 postings** across all 10 sources:
  - Greenhouse: 1,990 roles
  - SmartRecruiters: 167 roles
  - Ashby: 163 roles
  - Lever: 96 roles
  - Jooble (Brand New): 75 roles
  - Arbeitnow (Brand New): 45 roles
  - Email Alerts: 12 roles
  - Remotive: 10 roles
  - Workable & Adzuna: 0 roles
- **Deduplication:** 425 previously tracked roles recognized; 125 fresh postings identified.
- **Scoring Results:** **14 high-conviction matches ($\ge 7.0/10$)** selected:
  - **3 Internships & Apprenticeships**
  - **11 Full-Time Fresher Roles**
- **Delivery:** Delivered successfully to Telegram.
- **Noise Reduction Rate:** **99.45%** (2,558 raw postings filtered down to 14 actionable, high-quality jobs).
