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
 ├── 1. Greenhouse API (Public JSON API • 26 Verified Companies)
 ├── 2. Lever API (Public JSON API • 9 Verified Companies)
 ├── 3. Ashby API (Public JSON API • 9 Verified Companies)
 ├── 4. SmartRecruiters API (Public REST API • 8 Verified Companies)
 ├── 5. Workable API (v3 API & v1 Widget • 4 Verified Companies)
 ├── 6. Jooble API (Official Aggregator REST API • India Fresher Queries)
 ├── 7. Arbeitnow API (Zero-Auth Remote Developer JSON Feed)
 ├── 8. Remotive API (Remote Developer JSON API • Max 4 fetches/day)
 ├── 9. Adzuna Search API (Official Job Search REST API • 6 Query Groups)
 └── 10. Email Alerts (SSL IMAP Port 993 • Mailbox A Platform & ATS Alerts)
```

### Detailed Source Breakdown

#### 1. Greenhouse (`job_digest/sources/greenhouse.py`)
- **API Endpoint:** `https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true`
- **Method:** Public HTTP GET (Zero auth required; respectful 0.3s slug pacing)
- **Verified Indian & Global Tech Companies (26 boards):**
  `cloudflare`, `stripe`, `hashicorp`, `datadog`, `instacart`, `reddit`, `gitlab`, `automattic`, `elastic`, `affirm`, `gusto`, `pagerduty`, `confluent`, `mongodb`, `cockroachlabs`, `airbnb`, `pinterest`, `dropbox`, `groww`, `inmobi`, `druva`, `twilio`, `rubrik`, `samsara`, `databricks`, `okta`.

#### 2. Lever (`job_digest/sources/lever.py`)
- **API Endpoint:** `https://api.lever.co/v0/postings/{company_slug}?mode=json`
- **Method:** Public HTTP GET
- **Verified Companies (9 boards):**
  `palantir`, `spotify`, `lever`, `canonical`, `postman`, `docker`, `browserstack`, `cred`, `meesho`. *(Note: `linear` was audited and confirmed to be active on Ashby, not Lever).*

#### 3. Ashby (`job_digest/sources/ashby.py`)
- **API Endpoint:** `https://api.ashbyhq.com/posting-api/job-board/{company_slug}`
- **Method:** Public HTTP GET (Filters for `isListed=True`)
- **Verified Companies (9 boards):**
  `openai`, `retool`, `ramp`, `anthropic`, `notion`, `figma`, `linear`, `monzo`, `snowflake`. *(Linear verified with 30 live roles on Ashby).*

#### 4. SmartRecruiters (`job_digest/sources/smartrecruiters.py`)
- **API Endpoint:** `https://api.smartrecruiters.com/v1/companies/{company_slug}/postings`
- **Method:** Public REST API
- **Verified Companies (8 boards):**
  `BoschGroup`, `IKEA`, `Ubisoft`, `visa`, `swiggy`, `cars24`, `freshworks`, `grab`.

#### 5. Workable (`job_digest/sources/workable.py`)
- **API Endpoint:** `https://apply.workable.com/api/v3/accounts/{company_slug}/jobs` (with fallback to `https://apply.workable.com/api/v1/widget/accounts/{company_slug}`)
- **Method:** Public REST / Widget API
- **Verified Companies (4 boards):**
  `transferwise`, `harness`, `testgorilla`, `farfetch`. *(All 4 are international tech employers whose current postings are outside India, returning 0 India roles as expected).*

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
- **API Endpoint:** `https://remotive.com/api/remote-jobs?category=software-dev&limit=50`
- **Method:** Public HTTP GET (Strictly obeys API terms with max 4 API fetches per calendar day, tracked via `.remotive_fetch_state.json`).

#### 9. Adzuna Search API (`job_digest/sources/adzuna.py`)
- **API Endpoint:** `https://api.adzuna.com/v1/api/jobs/in/search/{page}?app_id={ID}&app_key={KEY}`
- **Method:** Authenticated REST API across 6 clean keyword query groups (avoiding unsupported nested Boolean syntax):
  1. `python developer fresher`
  2. `backend developer fresher`
  3. `software engineer trainee`
  4. `graduate engineer trainee`
  5. `software developer intern`
  6. `AI ML intern`

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
│   └── schema.sql                     # Complete PostgreSQL DDL (8 tables, indexes, foreign keys)
├── docs/
│   ├── decisions.md                   # 20 Architecture Decision Records (ADRs 001 to 020)
│   ├── deployment.md                  # Comprehensive Render & Neon deployment runbook
│   ├── master_project_report.md       # Full master report of all tech, websites, and code paths
│   └── portfolio_summary.md           # Professional executive summary for recruiters
├── job_digest/
│   ├── __init__.py                    # Module export definitions
│   ├── auth.py                        # Argon2id password hashing and session cookie verification
│   ├── config.py                      # Pydantic v2 profile models, env loaders, hard constraints
│   ├── db.py                          # SQLAlchemy engine, NullPool, session context, DDL runner
│   ├── dedup.py                       # Normalization, SHA-256 fingerprinting, sightings attribution
│   ├── digest.py                      # Digest builder, Jinja2 template renderer, partitioning
│   ├── match.py                       # 10-point scoring algorithm, hard filters, fresher exceptions
│   ├── models.py                      # Core dataclasses: Job, RawJob, ScoredJob, DigestOutput, etc.
│   ├── normalize.py                   # Normalization: HTML stripping, location canonicalization, regex
│   ├── notify.py                      # TelegramBotNotifier, EmailNotifier, urgent alert dispatcher
│   ├── profile.py                     # Profile schema, skills models, and YAML loader
│   ├── profile_service.py             # Active profile manager and ADR 007 database versioning
│   ├── run.py                         # Master orchestrator, CLI entrypoint, local scheduler
│   ├── status.py                      # Job tracking: saved, applied, not_interested transitions
│   ├── urgency.py                     # Deadline extractor and <= 4 hour urgent detector
│   ├── web.py                         # FastAPI web dashboard, Argon2id auth, APScheduler lifespan
│   ├── sources/
│   │   ├── __init__.py                # Sources package export
│   │   ├── base.py                    # BaseSource abstract protocol and location helpers
│   │   ├── runner.py                  # Fault-isolated concurrent source execution engine
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
│   ├── check_ats_slugs.py             # CLI scanner verifying candidate company slugs across ATSs
│   ├── generate_master_docx.py        # Generates styled Word (.docx) master architecture report
│   └── run_sources_check.py           # Quick CLI diagnostic for ATS sources
├── site/
│   ├── build.py                       # Static site generator for public GitHub Pages showcase
│   └── index.html                     # Public showcase HTML with Schema.org JSON-LD
├── tests/                             # 194 automated unit and integration tests (21 files)
├── .env.example                       # Documented environment variable template (zero secrets)
├── .gitignore                         # Strict exclusion of .env, credentials, logs, cache, profile.yaml
├── Dockerfile                         # Production multi-stage Docker build running as appuser
├── memory.md                          # Comprehensive persistent system memory (14 sections)
├── profile.example.yaml               # Tracked candidate profile template (profile.yaml is git-ignored)
├── README.md                          # Full GitHub project documentation and badges
├── requirements.txt                   # Frozen production dependencies
└── sources.yaml                       # 56 verified company ATS slugs (26 Greenhouse, 9 Lever, 9 Ashby, 8 SmartRecruiters, 4 Workable)
```

---

## 5. Complete Database Architecture & Schema DDL

The database schema is hosted on **Neon Serverless PostgreSQL** and executed via [`database/schema.sql`](../database/schema.sql), comprising **8 relational tables**:

```sql
-- 1. Permitted Source Configuration & Active Status
CREATE TABLE IF NOT EXISTS job_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,
    source_type VARCHAR(32) NOT NULL, -- 'ats', 'search_api', 'feed', 'imap', 'manual'
    config JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Master Tracking & Fingerprint Store (Prevents Re-Alerting & Powers Yield Analytics)
CREATE TABLE IF NOT EXISTS seen_jobs (
    fingerprint VARCHAR(64) PRIMARY KEY, -- sha256(company | title | location)
    canonical_url TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notified_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'seen', -- 'seen', 'saved', 'applied', 'not_interested'
    saved_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ,
    not_interested_at TIMESTAMPTZ,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_seen_jobs_canonical_url ON seen_jobs(canonical_url);
CREATE INDEX IF NOT EXISTS idx_seen_jobs_status ON seen_jobs(status);

-- 3. Versioned User Profile Store (ADR 007 Profile Versioning)
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    version INT NOT NULL,
    profile_yaml TEXT NOT NULL,
    profile_data JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_profiles_active ON user_profiles(is_active, version DESC);

-- 4. Jobs: Master postings table
CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    fingerprint VARCHAR(64) UNIQUE NOT NULL REFERENCES seen_jobs(fingerprint) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    canonical_url TEXT NOT NULL,
    description_text TEXT,
    posted_at TIMESTAMPTZ,
    source VARCHAR(64) NOT NULL,
    is_intern BOOLEAN NOT NULL DEFAULT FALSE,
    is_apprentice BOOLEAN NOT NULL DEFAULT FALSE,
    min_years NUMERIC(3, 1),
    salary_lpa NUMERIC(6, 2),
    stipend NUMERIC(8, 2),
    batch_years INT[],
    matched_skills TEXT[],
    missing_skills TEXT[],
    score NUMERIC(4, 2),
    score_breakdown JSONB DEFAULT '{}'::jsonb,
    raw_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_intern ON jobs(is_intern, is_apprentice);

-- 5. Digests: History of generated and sent digests
CREATE TABLE IF NOT EXISTS digests (
    id BIGSERIAL PRIMARY KEY,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_jobs INT NOT NULL DEFAULT 0,
    internships_count INT NOT NULL DEFAULT 0,
    fulltime_count INT NOT NULL DEFAULT 0,
    channels_notified TEXT[] NOT NULL DEFAULT '{}',
    failed_sources TEXT[] DEFAULT '{}',
    content_html TEXT,
    content_text TEXT
);
CREATE INDEX IF NOT EXISTS idx_digests_sent_at ON digests(sent_at DESC);

-- 6. Source Runs: Health and execution monitoring (Renders /sources page)
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

-- 7. Email Messages: Idempotency log for email alerts
CREATE TABLE IF NOT EXISTS email_messages (
    message_id VARCHAR(255) PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    subject TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    jobs_extracted INT NOT NULL DEFAULT 0
);

-- 8. Job Sightings: Multi-source attribution and yield analytics (Stage 4)
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

### 2. Seniority Filtering & Built-In Fresher Exception Guard
The eligibility engine evaluates candidate eligibility using hard knockout rules with an intelligent false-positive guard:
1. **Hard Senior Knockout:** Strictly drops any title containing: `Senior`, `Sr`, `Sr.`, `Principal`, `Director`, `Architect`, `VP`, `Chief`, `Head`, `Expert`.
2. **Role-Level Words & The Intern/Trainee Exception Guard:**
   - Role-level words like `Lead`, `Leader`, `Manager`, `Staff`, `Experienced` are normally dropped for standard full-time postings.
   - **False-Positive Exception Guard:** If a role's title explicitly indicates a fresher, intern, or apprentice role (e.g. contains `intern`, `internship`, `apprentice`, `apprenticeship`, `trainee`, `graduate trainee`, `co-op`, `fresher`), **it is NOT dropped on role-level words**! This correctly preserves titles like *Product Manager Intern*, *Staffing Intern*, or *Lead Generation Trainee*.
3. **Experience Requirement:** Roles requiring $> 2.0\text{ YOE}$ are rejected.
4. **Graduation Batch:** Rejects explicit batches other than 2027 (when batch restrictions are stated).

### 3. Deterministic 10-Point Scoring Algorithm

Postings surviving the hard filters are scored deterministically out of 10.0 points:

| Component | Max Points | Evaluation & Graduated Scoring Logic |
|---|:---:|---|
| **1. Skills Overlap** | **4.0 pts** | Matches candidate skills (Python, FastAPI, SQL/PostgreSQL, React, Linux, Docker, REST APIs, Git).<br>&bull; **4+ matches:** $1.0 \times 4.0 =$ **4.0 pts**<br>&bull; **3 matches:** $0.8 \times 4.0 =$ **3.2 pts**<br>&bull; **2 matches:** $0.6 \times 4.0 =$ **2.4 pts**<br>&bull; **1 match:** $0.4 \times 4.0 =$ **1.6 pts** |
| **2. Role Alignment** | **3.0 pts** | Matches title: Software Engineer, Software Developer, Backend Developer, Systems Engineer, Full Stack Engineer. |
| **3. Experience Level** | **2.0 pts** | 2.0 pts awarded for Internships, Apprenticeships, Graduate Engineer Trainee (GET), Associate Software Engineer, or 0-year Fresher roles. |
| **4. Location Preference** | **1.0 pt** | Noida, Delhi NCR, Gurugram, Kolkata, Mumbai, Pune, Bengaluru, Indore, or Remote (India). |
| **Total Score** | **10.0 pts** | **Digest Thresholds:**<br>&bull; **Strong Matches ($\ge 7.0$ pts):** Immediate high-conviction delivery.<br>&bull; **Maybe Matches ($4.0 - 6.9$ pts):** Secondary curated bucket in digest.<br>&bull; Roles with score $< 4.0$ are discarded. |

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
