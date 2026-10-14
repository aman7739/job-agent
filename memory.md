# Job Digest Agent — Master Project Memory & Context

> **Last Updated:** Post-Launch Production Milestone (All 8 Sources 100% Healthy & Live on Render!)  
> **Target Audience:** Agent context persistence across sessions, architectural documentation, and complete operational reference.

---

## 1. Project Vision & User Profile

- **Project Purpose:** A private, autonomous, high-reliability personal Job Digest Agent running twice daily at 08:00 AM & 07:00 PM IST (and on-demand via the dashboard). It aggregates postings from 8 permitted sources, normalizes and deduplicates them, scores eligibility against a personal profile, delivers formatted digests via Telegram and SMTP Email, and dispatches immediate high-priority alerts for urgent jobs closing in ≤ 4 hours.
- **Candidate Context:**
  - **Degree & Branch:** B.Tech Computer Science and Engineering (CSE).
  - **Graduating Batch:** 2027.
  - **Current Standing:** Final Year Student.
  - **Core Application Rule:** **Actively applying to BOTH Internships/Apprenticeships and Full-Time fresher roles.** Both categories are immediate, top-priority application targets. In digests and dashboards, both categories must always be presented as active "Apply Now" opportunities.
  - **Seniority Constraint:** **Strictly NO senior, lead, principal, manager, director, or staff roles.** Only fresher, entry-level (0–2 years), internships, and apprenticeships are eligible.
  - **Preferred Cities:** Noida, Delhi NCR, Gurugram, Kolkata, Mumbai, Pune, Bengaluru, Indore, or Remote (India).
  - **Core Skills:** Python, FastAPI, Supabase, PostgreSQL, React, JavaScript, HTML/CSS, Git/GitHub, Linux, REST APIs, ML/AI foundations.
  - **Tracked Gaps:** Java, Spring Boot, Angular, Node.js, scikit-learn, PyTorch (monitored and displayed in digests, but never penalized with negative points).

---

## 2. Hard Boundaries & Compliance Rules

1. **Strictly Single-User:** Built exclusively for one person. No multi-tenant accounts, complex auth systems, or public registrations.
2. **No Unofficial Scraping:** Absolutely zero web scraping or DOM crawling of LinkedIn, Naukri, or Indeed. No Selenium, Playwright, or headless browsers for scraping (avoids Cloudflare/Akamai bot-blocks and OOM crashes on 512MB RAM containers).
3. **No Auto-Applying:** The agent curates and scores opportunities; the user always clicks the direct link to review and submit applications themselves.
4. **Dual Mailbox Separation:**
   - **Mailbox A (Alerts Inbox):** Receives job alert notifications from job boards. Read-only access via SSL IMAP with an App Password.
   - **Mailbox B (Notifications Inbox):** Receives the final daily digest via SMTP (Port 587 STARTTLS). Prevents circular digest loops.
5. **Strict Privacy Firewall on Mailbox A:**
   - Only authorized job platforms (LinkedIn, Naukri, Indeed, Internshala, Unstop, Instahyre, Wellfound, Cutshort, Foundit, Glassdoor, Hirist) are inspected.
   - All personal emails, banking statements, OTPs, and promotional spam from non-whitelisted senders are rejected in 1 millisecond without downloading bodies.
6. **Zero Credential Leakage:**
   - Real passwords, tokens, and API keys are NEVER written to git, `.env.example`, or logs.
   - Secrets persist strictly in Render's encrypted environment variables.
7. **Fault Isolation:**
   - Any individual source failure must never crash the pipeline; failed sources are logged to `source_runs` and named in the digest header.
   - Any delivery channel failure (Telegram vs Email) must not block the other. Jobs are marked notified if at least one channel succeeds.

---

## 3. Comprehensive Technology Stack Matrix

| Category | Technology | Version / Spec | Role in Project |
|---|---|---|---|
| **Language & Runtime** | **Python** | `3.12.1+` | Core backend language, asynchronous concurrency, script execution |
| **Web Framework** | **FastAPI** | `0.115+` | High-performance asynchronous REST API and web dashboard |
| **ASGI Server** | **Uvicorn** | `0.30+` | Production ASGI web server running behind Render reverse proxy |
| **Data Validation** | **Pydantic** | `v2.8+` | Strict profile validation (`extra="forbid"`), data model validation |
| **Database Engine** | **PostgreSQL** | `16` (Neon Serverless) | Production relational database hosted in AWS Singapore (`ap-southeast-1`) |
| **ORM & SQL Tool** | **SQLAlchemy** | `2.0+` | Query builder, schema migrations, and connection management |
| **DB Driver** | **psycopg3** | `3.2+` | Modern asynchronous/synchronous PostgreSQL database driver |
| **Connection Pooling** | **NullPool** | Built-in SQLAlchemy | Disables idle connection pooling to prevent PgBouncer pool exhaustion |
| **HTTP Client** | **httpx** | `0.27+` | Asynchronous non-blocking HTTP requests for ATS and REST job feeds |
| **HTML Parsing** | **html.parser** | Python stdlib | Safe, lightweight parsing of untrusted email HTML without C-bindings |
| **Email Ingestion** | **imaplib** | Python stdlib (SSL) | Connects to Gmail over Port 993 in `readonly=True` mode |
| **Email Delivery** | **smtplib** | Python stdlib (STARTTLS)| Dispatches digest emails to Mailbox B over Port 587 |
| **Instant Messaging** | **Telegram Bot API** | HTTPS REST | Instant markdown digest delivery & urgent deadline alerts |
| **Authentication** | **Argon2id** (`argon2-cffi`)| `23.1+` | Memory-hard cryptographic hashing for dashboard single-user password |
| **Session Security** | **itsdangerous** / HMAC | `2.2+` | Cryptographically signed, HTTP-only, SameSite session cookies |
| **Scheduling** | **APScheduler** | `3.10+` | In-app `AsyncIOScheduler` executing crawls at 08:00 AM & 07:00 PM IST |
| **Keepalive Automation**| **GitHub Actions** | Hosted Runners | 10-minute cron workflow pinging `/health` to eliminate cold-start sleep |
| **Templating Engine** | **Jinja2** | `3.1+` | Renders Telegram markdown, HTML digest emails, and web pages |
| **Containerization** | **Docker** | Multi-stage build | Lightweight Linux production image running as non-root `appuser` |
| **Cloud Hosting** | **Render** | Web Service (Docker) | Production host for dashboard, webhooks, and scheduler |
| **Showcase Hosting** | **GitHub Pages** | Static Site | Zero-JS public portfolio site deployed via `pages.yml` |
| **Test Suite** | **pytest** | `9.1+` | Test runner executing 187 unit, integration, and reliability tests |
| **Async Testing** | **pytest-asyncio** / `anyio`| `1.4+` / `4.15+` | Strict mode event loop management for async source tests |

---

## 4. Complete Repository & File Directory Tree

```
AI AGENT/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Continuous Integration: runs pytest on every push/PR
│       ├── daily-digest.yml       # Backup scheduled crawl workflow on GitHub Actions
│       ├── keepalive.yml          # Zero-sleep keepalive: pings /health every 10 minutes
│       └── pages.yml              # Static portfolio deployment to GitHub Pages
├── database/
│   └── schema.sql                 # Complete PostgreSQL DDL (7 tables, indexes, constraints)
├── dist/                          # Compiled static portfolio site output (generated by site/build.py)
├── docs/
│   ├── backup_plan.md             # Disaster recovery backup and restore procedures
│   ├── decisions.md               # Historical architectural decision records log
│   ├── deployment.md              # Cloud deployment guide for Render and Neon
│   ├── domain_setup.md            # Custom domain and DNS configuration guide
│   ├── portfolio_summary.md       # High-level technical summary for portfolio presentation
│   └── runbook.md                 # Production incident response and maintenance runbook
├── job_digest/                    # Core Python application package
│   ├── __init__.py                # Package initialization
│   ├── auth.py                    # Argon2id password verification, session cookies, rate limiting
│   ├── config.py                  # Sources YAML loader and environment configuration
│   ├── db.py                      # SQLAlchemy engine, session maker, schema auto-migration
│   ├── dedup.py                   # Company name normalizer, SHA-256 fingerprinting, 48h freshness
│   ├── digest.py                  # Jinja2 digest builder, dual section grouping, DB persistence
│   ├── match.py                   # Hard filters (senior exclusions, batch year), 10-point scoring
│   ├── models.py                  # Pydantic & SQLAlchemy data models (RawJob, Job, SourceRunResult)
│   ├── normalize.py               # Text cleaning, anti-traps (C, Go, REST), salary/stipend parsing
│   ├── notify.py                  # TelegramNotifier (4000-char chunking) and EmailNotifier (SMTP)
│   ├── profile.py                 # Strict Pydantic UserProfile model and schema
│   ├── profile_service.py         # DB profile versioning, fallback, and validation service
│   ├── run.py                     # Master pipeline orchestrator, CLI runner, and local scheduler
│   ├── status.py                  # Application status transitions (saved, applied, not_interested)
│   ├── urgency.py                 # Urgent deadline detector (jobs closing in <= 4 hours)
│   ├── web.py                     # FastAPI dashboard routes, auth middleware, health endpoint
│   ├── sources/                   # Source adapter package (Protocol: JobSource)
│   │   ├── __init__.py            # Sources package root
│   │   ├── adzuna.py              # Adzuna search API adapter (5 role query groups in India)
│   │   ├── ashby.py               # Ashby public postings API adapter
│   │   ├── base.py                # JobSource protocol, Indian location matcher, default User-Agent
│   │   ├── email_alerts.py        # IMAP email alert parser (header-first, 11 platforms, non-blocking)
│   │   ├── greenhouse.py          # Greenhouse public board API adapter
│   │   ├── lever.py               # Lever public postings API adapter
│   │   ├── remote.py              # Remotive remote developer feed adapter (rate-limited)
│   │   ├── runner.py              # Fault-isolated source runner with 45s safety timeout
│   │   ├── smartrecruiters.py     # SmartRecruiters postings API adapter
│   │   └── workable.py            # Workable v3 API and v1 widget fallback adapter
│   └── templates/                 # Jinja2 template directory
│       ├── digest.html            # Multipart HTML email digest template
│       ├── digest.txt             # Plain text and Telegram markdown digest template
│       └── web/                   # Web dashboard templates
│           ├── add_job.html       # Manual ad-hoc job entry form
│           ├── base.html          # Dashboard master layout with navigation and security headers
│           ├── digest_view.html   # Today's live digest view with on-demand trigger button
│           ├── history.html       # Searchable, filterable historical jobs table
│           ├── login.html         # Argon2 protected single-user login interface
│           ├── settings.html      # Interactive profile, skills, and blocklist YAML editor
│           └── sources.html       # Real-time source health and execution metrics dashboard
├── scripts/
│   ├── backup_db.py               # Standalone JSON snapshot backup script for database tables
│   └── keepalive.py              # Lightweight HTTP ping script executed by keepalive workflow
├── site/                          # Public portfolio showcase static site generator
│   ├── build.py                   # Standalone Jinja2 static compiler generating dist/
│   ├── static/                    # CSS stylesheets, favicon, manifest, and SVG diagrams
│   └── templates/                 # Semantic SEO templates (index, how-it-works, sources, privacy, 404)
├── tests/                         # Comprehensive automated test suite
│   ├── fixtures/                  # Raw EML files, JSON responses, and mock data
│   ├── test_db.py                 # Database connectivity, transaction handling, and schema tests
│   ├── test_dedup.py              # SHA-256 fingerprinting, legal suffix stripping, freshness tests
│   ├── test_digest.py             # Digest rendering, 40-item cap, empty state tests
│   ├── test_email_source.py       # IMAP parsing, header-first inspection, 11-platform tests
│   ├── test_keepalive.py          # Render keepalive monitoring tests
│   ├── test_match.py              # 10-point scoring algorithm, hard filters, senior exclusion tests
│   ├── test_normalize.py          # Anti-traps (C, Go), location cleaner, salary parser tests
│   ├── test_notify.py             # Telegram chunking and Email SMTP delivery tests
│   ├── test_profile.py            # Strict Pydantic profile validation tests
│   ├── test_reliability_s12.py   # Fault isolation, source crash recovery, rate limit tests
│   ├── test_run.py                # Master pipeline end-to-end integration tests
│   ├── test_s13_profile_and_status.py # Profile versioning and job status transition tests
│   ├── test_s14_web_and_auth.py   # FastAPI web routes, Argon2 login, and session cookie tests
│   ├── test_s15_actions_and_settings.py # Interactive status actions and settings editor tests
│   ├── test_s16_deploy.py         # Deployment configuration and health endpoint tests
│   ├── test_s17_hardening.py      # Enterprise security headers, robots.txt, PWA tests
│   ├── test_s18_site_foundation.py # Static site generator and semantic SEO tests
│   ├── test_s19_content_and_schema.py # Schema.org JSON-LD and visual asset tests
│   ├── test_s20_crawl_files_and_deployment.py # Sitemap, llms.txt, and Pages deployment tests
│   ├── test_s21_audit_and_release.py # Pre-launch checklist, bundle hygiene, README tests
│   ├── test_s22_final_wrapup.py   # Operational runbook and portfolio briefing tests
│   ├── test_smoke.py              # Basic sanity and import verification tests
│   ├── test_sources.py            # Greenhouse and Lever adapter tests
│   ├── test_sources_s3.py         # Ashby, SmartRecruiters, Workable adapter tests
│   ├── test_sources_s4.py         # Adzuna, Remotive, and fault-isolated runner tests
│   └── test_urgency_and_schedule.py # 4-hour urgency detector and twice-daily schedule tests
├── .dockerignore                  # Files excluded from production Docker image build
├── .env.example                   # Sanitized environment variable template with zero secrets
├── .gitignore                     # Git ignore rules (.env, .venv, pycache, dist)
├── Dockerfile                     # Multi-stage production container configuration
├── memory.md                      # Master project memory, architecture, and context document
├── Procfile                       # Process definition for cloud hosting (Render web process)
├── pyproject.toml                 # Build system configuration and pytest options
├── render.yaml                    # Infrastructure-as-code blueprint for Render deployment
├── requirements.txt               # Pinned Python package dependencies
└── sources.yaml                   # Verified company slugs for Greenhouse, Lever, Ashby, etc.
```

---

## 5. Data Ingestion Matrix — Where & How Every Single Source Fetches Data

| Source Name | Method | Exact URL / Protocol Pattern | Authentication | Request Parameters & Headers | Rate Limit / Delay | Payload Format | What Data is Extracted |
|---|---|---|---|---|---|---|---|
| **Greenhouse** | `GET` | `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | None (Public JSON) | `User-Agent: JobDigestAgent/1.0`, `Accept: application/json` | 0.3s between slugs | JSON Object (`jobs: [...]`) | Job ID, title, company slug, office location, apply URL, full HTML job description. (26 verified boards: Databricks, Okta, InMobi, Groww, Twilio, Rubrik, Samsara, Cloudflare, Stripe, etc.) |
| **Lever** | `GET` | `https://api.lever.co/v0/postings/{slug}?mode=json` | None (Public JSON) | `User-Agent: JobDigestAgent/1.0`, `Accept: application/json` | 0.3s between slugs | JSON Array of postings | Job ID, text (title), workplaceType, categories.location, apply URL, description. (10 verified boards: CRED, Meesho, Palantir, Spotify, Postman, BrowserStack, etc.) |
| **Ashby** | `GET` | `https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` | None (Public JSON) | `User-Agent: JobDigestAgent/1.0`, `Accept: application/json` | 0.3s between slugs | JSON Object (`jobs: [...]`) | Job ID, title, location, isListed filter (`True`), compensation tiers, apply URL. (9 verified boards: OpenAI, Figma, Notion, Snowflake, Linear, etc.) |
| **SmartRecruiters** | `GET` | `https://api.smartrecruiters.com/v1/companies/{slug}/postings` | None (Public JSON) | `User-Agent: JobDigestAgent/1.0`, `Accept: application/json` | 0.3s between slugs | JSON Object (`content: [...]`) | Job ID, name (title), location.city, location.country, apply URL. (8 verified boards: Swiggy, Freshworks, Grab, Cars24, Bosch, Visa, IKEA, Ubisoft) |
| **Workable** | `POST` / `GET` | `https://apply.workable.com/api/v3/accounts/{slug}/jobs` (Fallback: `widget` v1) | None (Public API) | Payload: `{"query": ""}`, Headers: `Accept: application/json` | 0.3s between slugs | JSON Object (`results: [...]`) | Shortcode (ID), title, city, country, remote flag, apply URL. (4 slugs: Transferwise, Harness, TestGorilla, Farfetch) |
| **Adzuna** | `GET` | `https://api.adzuna.com/v1/api/jobs/in/search/{page}` | `app_id` & `app_key` query params | `what`: 6 focused fresher/intern queries, `country`: `in`, `results_per_page`: 15 | 0.5s between query batches | JSON Object (`results: [...]`) | Live Indian jobs across Gurgaon, Bangalore, Pune, Hyderabad, Remote. Extracts ID, title, company.display_name, location, salary min/max, apply URL. Focuses exclusively on Python fresher, backend fresher, SDE trainee, GET, and intern roles. |
| **Remotive** | `GET` | `https://remotive.com/api/remote-jobs?category=software-dev&limit=50` | None (Public Feed) | `category=software-dev`, `limit=50` | Max 4 requests / 24h (Cached) | JSON Object (`jobs: [...]`) | Global remote tech jobs filtered for candidate location: checks `candidate_required_location` for India, APAC, or Worldwide. |
| **IMAP Email Alerts** | `IMAP4_SSL` | `imap.gmail.com:993` (Port 993 SSL) | Google 16-char App Password (`readonly=True`) | **Step 1:** Fetch headers only (`BODY.PEEK[HEADER.FIELDS]`) under 1 KB. **Step 2:** Fetch body (`BODY.PEEK[]`) ONLY if sender is whitelisted & ID is new. | 15s socket timeout; runs in background worker thread | RFC-822 MIME (Multipart HTML) | Parses job links from **11 Whitelisted Platforms + Direct ATS Career Alerts:** LinkedIn, Naukri, Indeed, Internshala, Unstop, Instahyre, Wellfound, Cutshort, Foundit, Glassdoor, Hirist, Greenhouse, Lever, SmartRecruiters, Ashby, Workday, Amazon Jobs. |

---

## 6. Database Schema & Architectural Models (Neon PostgreSQL)

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

-- 2. Master Tracking & Fingerprint Store (Prevents Re-Alerting)
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

-- 3. Versioned User Profile Store
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    version INT NOT NULL,
    profile_yaml TEXT NOT NULL,
    profile_data JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_profiles_active ON user_profiles(is_active, version DESC);

-- 4. Scored & Normalized Jobs Store
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

-- 5. Sent Digests Archive
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

-- 6. Health & Execution Metrics Log (Renders /sources Page)
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

-- 7. IMAP Processed Message Store (Deduplicates Email Ingestion)
CREATE TABLE IF NOT EXISTS email_messages (
    message_id VARCHAR(255) PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    subject TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    jobs_extracted INT NOT NULL DEFAULT 0
);
```

---

## 7. End-to-End Pipeline Data Flow & Algorithms

```
[Trigger: APScheduler 08:00 AM / 07:00 PM IST or Manual POST /jobs/run-now]
                              │
                              ▼
1. INGESTION (run_all_sources)
   - Executes all 8 source adapters concurrently or sequentially with 45s safety timeout per source.
   - Fault isolation: If 1 source fails or times out, the other 7 continue uninterrupted.
   - Source metrics recorded to `source_runs`.
                              │
                              ▼
2. NORMALIZATION (normalize_raw_job)
   - Strips HTML tags, trims whitespace, standardizes casing.
   - Cleans tracking tokens: removes UTM parameters, `ref`, `gh_src`, session tokens from URLs.
   - Resolves location aliases: "Gurgaon" -> "Gurugram", "Calcutta" -> "Kolkata", "Bangalore" -> "Bengaluru".
   - Regex Anti-Traps: Prevents false skill matches (e.g. 'C' in 'CSS', 'Go' in 'Good', 'REST' in 'Restricted').
   - Parses compensation: Converts annual INR, monthly stipends, and USD rates into standardized LPA / monthly stipend.
                              │
                              ▼
3. DEDUPLICATION (process_and_upsert_jobs)
   - Strips legal corporate suffixes ("Pvt Ltd", "Inc.", "LLC") to identify the true company entity.
   - Computes SHA-256 fingerprint: sha256(normalized_company | normalized_title | canonical_location).
   - Drops canonical URL duplicates and identical fingerprints seen within the past 48 hours.
   - Upserts into `seen_jobs` and persists new jobs into `jobs`.
                              │
                              ▼
4. ELIGIBILITY & 10-POINT SCORING (rank_and_score_jobs)
   - Hard Exclusion Filters & Seniority Guards:
     * Hard Senior Exclusions: Strictly drops any role containing `senior`, `sr`, `sr.`, `principal`, `director`, `architect`, `vp`, `chief`, `head`, `expert`.
     * Composite Title Protection (False-Positive Guard): Role-level keywords (`lead`, `manager`, `staff`, `leadership`) exclude standard postings, but are safely permitted if the role is explicitly an intern/trainee/apprentice (e.g., "Product Manager Intern", "Lead Generation Trainee", "Staff Assistant Apprentice"), preventing false-positive rejections.
     * Experience Filter: Drops jobs explicitly requiring > 2.0 years of experience.
     * Batch Year Filter: Drops jobs restricted to graduating batches other than 2027.
     * Salary Floor: Drops full-time roles offering < 3.5 LPA (when salary is explicitly listed).
   - 10-Point Score Formula:
     * Skills Match (Max 4.0 pts): 4+ skills = 4.0, 3 = 3.2, 2 = 2.4, 1 = 1.6.
     * Role Relevance (Max 3.0 pts): Matches 41 target technical job title patterns.
     * Seniority / Level (Max 2.0 pts): Internships / Apprenticeships / 0-yr = 2.0, <= 1 yr = 1.8, <= 2 yr = 1.4.
     * Location Preference (Max 1.0 pt): Preferred cities = 1.0, India / Remote = 0.5, Abroad = 0.0.
   - Identifies candidate skill gaps (Java, Spring Boot, etc.) and tags them for visibility without penalty.
                              │
                              ▼
5. DIGEST CONSTRUCTION (build_digest)
   - Organizes jobs into two distinct "Apply Now" sections:
     * Section 1: Internships & Apprenticeships (Strong Matches >= 7.0 & Good Matches 4.0–6.9)
     * Section 2: Full-Time Fresher Roles (Strong Matches >= 7.0 & Good Matches 4.0–6.9)
   - Formats listings with Apply link first, compensation, match score, matched skills, and tracked gaps.
   - Imposes a strict 40-item digest cap to prevent notification fatigue.
                              │
                              ▼
6. DELIVERY (deliver_digest & deliver_urgent_alert)
   - Telegram: Dispatches formatted markdown message to private chat ID via Telegram Bot API. Partitions messages exceeding 4,000 characters along paragraph boundaries.
   - Email: Sends multipart HTML + plain text digest to Mailbox B via SMTP STARTTLS (Port 587).
   - Urgent Deadline Dispatch: If any unnotified role closes in <= 4 hours, dispatches an immediate high-priority alert.
                              │
                              ▼
7. PERSISTENCE & AUDIT
   - Saves rendered HTML and text digest to `digests` table.
   - Updates `notified_at = NOW()` on delivered jobs in `seen_jobs`.
   - Records execution metrics in `source_runs`.
```

---

## 8. Architectural Decisions (ADR Summary)

- **ADR 001 (Single-User Scope):** Built strictly for one personal user to minimize maintenance and avoid multi-tenant complexity.
- **ADR 002 (Tech Stack):** Python 3.12, strict Pydantic (`extra="forbid"` on profile, `"ignore"` on models), SQLAlchemy 2.0 + psycopg 3, `httpx` async client, Jinja2, FastAPI.
- **ADR 003 (Permitted Sources & Anti-Scraping):** Strict use of public ATS APIs, official search APIs (Adzuna), and personal IMAP email alerts. Zero scraping of LinkedIn/Naukri/Indeed.
- **ADR 004 (Dual-Mailbox Separation):** Mailbox A for incoming alert emails (read-only IMAP with App Password); Mailbox B for outgoing digest notifications via SMTP.
- **ADR 005 (Database Engine — Neon Serverless PostgreSQL):** Dedicated production PostgreSQL 16 hosted on Neon Serverless (AWS Singapore `ap-southeast-1`) accessed via connection pooling with `NullPool` to prevent idle connection exhaustion. (Supabase was evaluated during Session 1 prototyping only).
- **ADR 006 (Fault Isolation & Delivery Resilience):** Sources run in isolated try-except blocks, recording metrics to `source_runs`. Unreachable sources are highlighted in digest notices. Notifiers run independently; jobs are marked notified if $\ge 1$ channel succeeds.
- **ADR 007 (Database Profile Versioning & Job Status Tracking):** Monotonic versions stored in `user_profiles` with validation on save. Corrupted configs fall back to last good version. Status (`saved`, `applied`, `not_interested`) tracked with dedicated timestamps.
- **ADR 008 (Single-User Web Dashboard, Argon2 & Session Protection):** FastAPI app with Argon2id password hash, HMAC-SHA256 session cookie, login IP rate limiter, protected digest view and filtered job history.
- **ADR 009 (Interactive Actions, Settings Editor, Source Health & Manual Entry):** One-click status updates, weekly applied counter, web profile & blocklist editor with validation on save, live source health monitoring, and manual ad-hoc job submission.
- **ADR 010 (Twice-Daily Notification Cadence, Urgent Expiring Alerts & In-App Scheduler):** Twice-daily scheduled runs (08:00 AM & 07:00 PM IST) executed directly in-app by APScheduler with `misfire_grace_time=3600` and a 14-hour startup catch-up trigger; urgent deadline detector (`≤ 4 hours left`) dispatching instant high-priority alerts; and an authenticated on-demand button (`POST /jobs/run-now`).
- **ADR 011 (Cloud Deployment Architecture & GitHub Actions Backup):** Decoupled architecture where the web dashboard and scheduler run on Render in a production container (`Dockerfile`), kept alive 24/7 via 10-minute automated health pings (`keepalive.yml`). Scheduled crawling runs primarily in-app (ADR 010) to eliminate free runner queue latency, with `.github/workflows/daily-digest.yml` retained as a secondary backup.
- **ADR 012 (Production Hardening, Security Headers, Privacy & PWA Support):** Comprehensive enterprise security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options), strict crawler blocking via `X-Robots-Tag` and `/robots.txt`, authentication guard on all dashboard routes, mobile PWA manifest, token-protected webhook API, and JSON database backup snapshot utility.
- **ADR 013 (Static Showcase Site Generator & Semantic SEO Architecture):** Custom Jinja2 static site compiler (`site/build.py`) outputting cleanly formatted HTML to `dist/` with directory-based clean URLs, strict semantic SEO constraints, and zero personal candidate data leakage.
- **ADR 014 (Structured Data, Social Meta Graph & Accessible Visual Asset Architecture):** Schema.org JSON-LD graph (`SoftwareApplication`, `WebSite`, `BreadcrumbList`), complete OpenGraph and Twitter card metadata (1200x630 social share preview card), accessible hand-crafted vector visual assets (`architecture.svg`, `telegram-mockup.svg`), and zero-placeholder content audit across all public pages.
- **ADR 015 (Domain Deployment, Crawl Files & GitHub Pages Automation):** Automated generation of Sitemaps 0.9 protocol `sitemap.xml`, permissive `robots.txt`, structured `llms.txt` for AI crawlers, custom recovery `404.html`, automated `.github/workflows/pages.yml` deployment on push, and DNS/HTTPS custom domain guide (`docs/domain_setup.md`).
- **ADR 016 (Production Pre-Launch Audit, Anti-Slop Enforcement & Release Baseline):** Distribution hygiene (0 source maps, 0 KB JS, ~6 KB unminified CSS, 0 console errors), strict anti-slop rules compliance, comprehensive production `README.md`, verified 20-point pre-launch checklist, and release tagging `v1.0.0`.
- **ADR 017 (Project Wrap-Up, Operational Runbook & Final Production Handoff):** Complete operational runbook (`docs/runbook.md`), portfolio briefing (`docs/portfolio_summary.md`), 20 ADRs documented, 181 automated tests passing (100% green), and production-ready handoff.
- **ADR 018 (Non-Blocking Header-First IMAP Architecture):** Offloads synchronous IMAP fetching to `asyncio.to_thread` with strict 15s socket timeout, filters emails by header fields (`FROM`, `MESSAGE-ID`) under 1 KB, skips unauthorized senders and cached Message-IDs in 1ms, and searches only past 3 days (`SINCE`). Eliminates event-loop blocking and cuts crawl duration from 5 minutes to 3 seconds.
- **ADR 019 (Single-Query Dashboard Source Health Architecture):** Replaces 8 individual sequential database roundtrips with a single batch query (`ORDER BY started_at DESC LIMIT 200`) grouped in memory, achieving sub-100ms `/sources` page load times even during remote Singapore-to-client network latency.
- **ADR 020 (Multi-Platform Job Alert Ingestion & Universal Parser):** Extends IMAP whitelisting from 3 to 11 major platforms (Internshala, Unstop, Instahyre, Wellfound, Cutshort, Foundit, Glassdoor, Hirist) with domain pattern matching, specialized internship extractors, and a universal job link parser for untrusted email HTML.

---

## 9. Technical Gotchas & Environment Rules

1. **PowerShell on Windows:** Does not support `&&` for chaining commands; always use semicolon `;` (e.g. `git add . ; git commit -m "..."`).
2. **GitHub Actions YAML Syntax:** In `.github/workflows/*.yml`, the trigger key `"on":` must be enclosed in quotes because PyYAML parses bare `on:` as boolean `True`.
3. **Telegram Message Limits:** Strictly enforced at 4,096 characters per message. `split_telegram_message` partitions messages at a 4,000-character ceiling along paragraph and line boundaries so markdown links are never severed.
4. **Company Legal Suffix Normalization:** Companies appear as "Stripe", "Stripe, Inc.", "Stripe India Private Limited". `normalize_company` in `job_digest/dedup.py` removes corporate suffixes before computing the SHA-256 fingerprint to prevent duplicate listings.
5. **Database Pools for Serverless/CLI:** Use `NullPool` in `job_digest/db.py` to prevent hanging connection pools when running ephemeral CLI pipelines or GitHub Actions workflows.
6. **Starlette / FastAPI TemplateResponse Signature:** Modern Starlette requires keyword arguments: `templates.TemplateResponse(request=request, name="...", context={...})`. Passing positional arguments causes Jinja2 cache `TypeError: unhashable type: 'dict'`.
7. **SQLite In-Memory Multi-Threading in Tests:** In FastAPI TestClient tests with in-memory SQLite, always configure `engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)` to prevent thread collision errors.
8. **FastAPI Parameter Shadowing:** Never name route arguments `status: str` if referencing `from fastapi import status` for HTTP codes (e.g., `status.HTTP_303_SEE_OTHER`); use direct integer codes (`303`) or alias imports.
9. **Free Cloud Host Sleep Prevention:** Free PaaS hosts (Render) hibernate after 15 minutes of inactivity. Set up an external ping monitor (keepalive workflow) to query `/health` every 10 minutes to maintain 24/7 responsiveness.
10. **Python stdlib `site` Module Namespace Collision:** Python's standard library includes `site.py`. Avoid `import site.build` directly; invoke `python site/build.py` or use dynamic path imports via `importlib.util.spec_from_file_location`.
11. **GitHub Actions Empty String Secrets:** When optional secrets are not configured in GitHub Secrets, GitHub Actions exports them as empty strings (`""`). Direct conversion via `int(os.getenv("IMAP_PORT", ...))` throws `ValueError: invalid literal for int() with base 10: ''`. Always validate `val and val.strip()` before converting to integers.
12. **GitHub Pages Repository Subpath (`/repo-name/`):** GitHub project pages are hosted at `username.github.io/repo/` rather than the domain root. `site/build.py` dynamically extracts `site_root` from the configured base URL, prefixing all asset and navigation links.
13. **Strict XML Entities in SVG Assets:** Standalone SVG files rendered via `<img>` tags are parsed strictly as XML by browser rendering engines. Named entities like `&bull;` or `&le;` produce fatal XML parse errors. Always use numeric references (`&#8226;`, `&#8804;`) or literal UTF-8 symbols (`•`, `≤`).
14. **Precision In-App Scheduling vs GitHub Actions Queuing:** GitHub Actions scheduled cron runs suffer from hours of queue delay on free runners during peak UTC traffic. Moving scheduled execution into an in-app `AsyncIOScheduler` inside the 24/7 warm Render web container fires crawl runs at exactly 08:00:00 AM IST and 07:00:00 PM IST with 0-second queuing latency.
15. **IMAP Synchronous Blocking Gotcha:** Calling `imaplib.IMAP4_SSL` directly inside an `async def` route or pipeline blocks the single-threaded asyncio event loop. Always wrap IMAP in `asyncio.to_thread` and set `timeout=15.0` on the socket to prevent server freezes.
16. **IMAP Full Body Download Latency:** Fetching `(RFC822)` for 20 messages downloads multi-megabytes over SSL, causing 3–5 minute latency. Always fetch headers first (`BODY.PEEK[HEADER.FIELDS (FROM MESSAGE-ID SUBJECT DATE)]`) under 1 KB, verify the sender against the domain whitelist, and check if the Message-ID is already in `email_messages` before downloading the full body.
17. **Multi-Query Dashboard Bottleneck:** Querying health status for each source adapter in an iterative loop across remote database connections multiplies latency by $N$. Use a single batch query (`LIMIT 200`) and group latest runs in memory for sub-100ms dashboard rendering.
18. **Anti-Scraping Realities on Job Portals:** Indeed (Cloudflare 403 Forbidden) and Naukri (Akamai 406 Not Acceptable) aggressively block direct HTTP scrapers and cloud IPs. Reading their algorithmic recommendation emails over IMAP completely bypasses bot firewalls legally with 100% zero blocks.
19. **Seniority False Positives on Composite Titles:** Substring checking on keywords like `manager`, `lead`, or `staff` causes false rejections on valid fresher postings such as "Product Manager Intern", "Lead Generation Trainee", or "Staff Assistant Apprentice". `job_digest/match.py` defines `is_explicit_fresher_title`: when a title contains explicit fresher indicators (`intern`, `trainee`, `apprentice`, `co-op`), role-level words (`lead`, `manager`, `staff`) are removed from exclusion, while hard senior words (`senior`, `principal`, `director`, `architect`, `vp`) remain strictly excluded.
20. **Scheduler Misfire Grace Time & Startup Catch-Up:** In free PaaS containers, if a deploy or maintenance restart overlaps with the scheduled run (08:00 AM / 07:00 PM IST), default APScheduler settings drop missed jobs silently (`misfire_grace_time=None`). Setting `misfire_grace_time=3600` allows the job to trigger up to 1 hour after scheduled time. Additionally, on container startup, the background lifespan inspects the latest digest in the database; if the last crawl was > 14 hours ago, an immediate catch-up crawl is triggered in the background.

---

## 10. Live Production Deployment & Verification (Active & Verified)

- **GitHub Repository:** [https://github.com/aman7739/job-agent](https://github.com/aman7739/job-agent) (`main` branch tracked, tagged `v1.0.0`).
- **Live Public Showcase Site:** [https://aman7739.github.io/job-agent/](https://aman7739.github.io/job-agent/)
  - Deployed via `.github/workflows/pages.yml`.
  - Zero-JS static site with dynamic repository subpath (`site_root = "/job-agent"`).
- **Production Cloud Database:** Neon serverless PostgreSQL (AWS Singapore `ap-southeast-1`) hosting tables:
  - `job_sources`, `seen_jobs`, `user_profiles`, `jobs`, `digests`, `source_runs`, `email_messages`.
- **Live Private Web Dashboard:** [https://job-agent-sg20.onrender.com](https://job-agent-sg20.onrender.com)
  - Hosted on Render Free-Tier (Singapore region) running production Docker container.
  - Argon2id password-protected single-user authentication, job status controls (`Save`, `Applied`, `Ignore`), profile settings, and on-demand crawler trigger.
  - Public `/health` endpoint verified: `status: healthy`, `database: connected`, `scheduler: running`, HTTP 200 OK.
  - Kept awake 24/7 with zero cold starts via 10-minute automated GitHub Actions keepalive cron (`.github/workflows/keepalive.yml`).
- **Telegram Notification Bot:**
  - Registered via `@BotFather` with private chat notifications via `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- **Automated Crawl Schedule:**
  - In-app `AsyncIOScheduler` running in the 24/7 warm Render container at **08:00 AM IST & 07:00 PM IST** (`cron: hour=2,13, minute=30, timezone=UTC`).
- **All 8 Sources 100% Green & Verified:**
  1. `greenhouse`: 1,224 jobs (Healthy)
  2. `lever`: 29 jobs (Healthy)
  3. `ashby`: 108 jobs (Healthy)
  4. `smartrecruiters`: 21 jobs (Healthy)
  5. `workable`: 0 active Indian jobs (Healthy)
  6. `adzuna`: 20 live Indian tech jobs via developer API keys (Healthy)
  7. `remotive`: 10 remote jobs (Healthy)
  8. `email_alerts`: 15 jobs parsed & smart cached deduplication (Healthy)
- **Total Ingestion Reach:** Over **1,410+ raw roles** scanned and normalized across both Indian and global tech markets.
- **Test Suite Status:** **187 passing unit and integration tests (100% green).**

---

## 11. Job Relevance, Matching Accuracy & Outcome Funnel

Recruiter Readiness & Production Quality Metrics:

### 11.1 The Ingestion-to-Application Yield Funnel

The system deliberately separates raw ingestion throughput from actionable opportunities to avoid notification fatigue:

```
[Raw Ingestion Throughput]
1,410+ Total Postings Scanned across 8 Sources (Greenhouse, Ashby, Lever, SmartRecruiters, Workable, Adzuna, Remotive, Email Alerts)
     │
     ▼ (Deduplication & Recency Window)
~195 Unique Fresh Jobs
   - Fingerprint: sha256(canonical_company | normalized_title | location)
   - 48-Hour Recency Filter: Previously seen or notified roles dropped
     │
     ▼ (Strict Hard Eligibility Rules)
10–25 Eligible Fresher & Internship Postings
   - Experience Filter: Dropped if > 2.0 years
   - Graduating Batch: Restricted exclusively to 2027 eligible / open
   - Hard Senior Exclusion: Dropped if Senior / Principal / Director / Architect / VP
   - Title Protection: "Product Manager Intern" or "Lead Gen Trainee" safely retained
   - Salary Floor: Dropped if full-time < 3.5 LPA
     │
     ▼ (10-Point Profile Scoring & Dual-Group Presentation)
Curated Digest (Max 40 Items)
   - Section 1: Internships & Apprenticeships (Strong Matches >= 7.0 & Good Matches 4.0–6.9)
   - Section 2: Full-Time Fresher Roles (Strong Matches >= 7.0 & Good Matches 4.0–6.9)
   - Dispatched via Telegram Markdown & SMTP HTML Email
     │
     ▼ (Dashboard Outcome Tracking)
Target Applications Submitted
   - Candidate marks status directly in Dashboard: Saved -> Applied -> Not Interested
   - Outcome metrics tracked in Neon PostgreSQL: `saved_at`, `applied_at`, `not_interested_at`
```

### 11.2 Tuning Matching Accuracy & False-Positive Elimination

| Failure Mode | Root Cause | Solution Implemented | Test Coverage |
|---|---|---|---|
| **Senior Role Leakage** | Vague descriptions without explicit years | Strict multi-word exclusion regex: `senior`, `sr.`, `principal`, `director`, `vp`, `architect`, `lead` | `test_match.py` |
| **False-Positive Senior Rejection** | Composite titles like "Product Manager Intern" or "Lead Generation Trainee" containing `manager` or `lead` | Dual-tier classification: Hard senior words reject always; role words (`lead`, `manager`, `staff`) permitted if explicit intern/trainee indicator present | `test_fresher_roles_with_manager_or_lead_words_not_excluded` |
| **Broken / Expired Links** | Aggregators linking to intermediate redirect loops | Link extraction restricted to direct ATS canonical URLs (`greenhouse.io`, `lever.co`, `ashbyhq.com`) and validated platform deep-links | `test_sources.py`, `test_email_source.py` |
| **Language Keyword False Hits** | Short keywords (`C`, `Go`, `REST`) matching substrings | Regular expression word-boundary tokens (`\bC\b`, `\bGo\b`, `\bREST\b`) with negative lookaheads (preventing matches in `CSS`, `Good`, `Restricted`) | `test_normalize.py` |
| **Company Legal Variations** | "Stripe" vs "Stripe India Pvt Ltd" seen as distinct companies | Normalizer strips registered entity legal suffixes (`Pvt Ltd`, `LLC`, `Inc`, `Corp`) prior to fingerprinting | `test_dedup.py` |

### 11.3 Personal Candidate Outcome & Time Savings

- **Daily Time Saved:** ~90 minutes per day previously spent manually refreshing 6 job boards and opening spam emails.
- **Signal-to-Noise Ratio:** Raw volume (1,410+) is filtered down to ~15 highly targeted opportunities per run—delivering a ~98.8% noise reduction rate.
- **Application Tracking:** The dashboard's interactive weekly applied counter and status actions persist exact timestamps, providing clear visibility into application velocity and pipeline health.

---

## 12. Source Expansion Build Plan (Status: Stages 1 & 2 Completed)

Based on [`job_digest_build_plan.md`](file:///C:/Users/KRAMA/OneDrive/Desktop/AI%20AGENT/job_digest_build_plan.md):

- **Stage 1 (Completed): Automated ATS Slug Checker & sources.yaml Expansion:**
  - Created standalone scanner [`scripts/check_ats_slugs.py`](file:///C:/Users/KRAMA/OneDrive/Desktop/AI%20AGENT/scripts/check_ats_slugs.py) and test suite [`tests/test_slug_checker.py`](file:///C:/Users/KRAMA/OneDrive/Desktop/AI%20AGENT/tests/test_slug_checker.py).
  - Verified 50 target companies across Greenhouse, Lever, Ashby, and SmartRecruiters with polite 0.3s pacing.
  - Expanded `sources.yaml` from 42 to **57 company boards**, adding verified Indian tech companies:
    * `smartrecruiters`: `swiggy` (100 India roles), `cars24`, `freshworks` (32 India roles), `grab`
    * `lever`: `cred` (7 India roles), `meesho` (58 India roles)
    * `greenhouse`: `groww` (11 India roles), `inmobi` (46 India roles), `druva` (14 India roles), `twilio` (143 India/Remote roles), `rubrik` (50 India roles), `samsara` (221 India/Remote roles), `databricks` (164 India roles), `okta` (111 India roles)
    * `ashby`: `snowflake` (51 India roles)
  - Results logged to `reports/ats_slug_report.csv`.
- **Stage 2 (Completed): Adzuna Query Groups & Email Alert Expansion:**
  - Replaced generic broad queries with 6 targeted fresher/intern groups in [`job_digest/sources/adzuna.py`](file:///C:/Users/KRAMA/OneDrive/Desktop/AI%20AGENT/job_digest/sources/adzuna.py):
    1. `python developer (fresher OR entry level OR junior)`
    2. `backend developer (fresher OR entry level OR junior)`
    3. `software engineer trainee OR graduate engineer trainee OR GET`
    4. `software developer intern OR full stack intern OR web developer intern`
    5. `AI intern OR ML intern OR machine learning intern OR data science intern`
    6. `associate software engineer OR junior software engineer`
  - Expanded [`job_digest/sources/email_alerts.py`](file:///C:/Users/KRAMA/OneDrive/Desktop/AI%20AGENT/job_digest/sources/email_alerts.py) whitelisting to accept direct company ATS alert senders (`greenhouse.io`, `lever.co`, `smartrecruiters.com`, `ashbyhq.com`, `myworkdayjobs.com`, `amazon.jobs`).
  - Added unit test [`test_parse_direct_ats_career_alerts`](file:///C:/Users/KRAMA/OneDrive/Desktop/AI%20AGENT/tests/test_email_source.py).
- **Stage 3 (Next):** Trial one aggregator API (Jooble or Careerjet).
- **Stage 4:** Implement `job_sightings` metric table and 7-day per-source analytics on `/sources`.
