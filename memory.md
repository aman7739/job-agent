# Job Digest Agent — Project Memory & Context

> **Last Updated:** Session 19 (Real Content & Structured Data Completed)  
> **Target Audience:** Agent context persistence across sessions and long-term project reference.

---

## 1. Project Vision & User Profile

- **Project Purpose:** A private, autonomous, high-reliability personal Job Digest Agent running twice daily at 08:00 AM & 07:00 PM IST (and on-demand via the dashboard). It aggregates postings from 8 permitted sources, normalizes and deduplicates them, scores eligibility against a personal profile, delivers formatted digests via Telegram and SMTP Email, and dispatches immediate high-priority alerts for urgent jobs closing in ≤ 4 hours.
- **Candidate Context:**
  - **Degree & Branch:** B.Tech Computer Science and Engineering (CSE).
  - **Graduating Batch:** 2027.
  - **Current Standing:** Final Year Student.
  - **Core Application Rule:** **Actively applying to BOTH Internships/Apprenticeships and Full-Time fresher roles.** Both categories are immediate, top-priority application targets. In digests and dashboards, both categories must always be presented as active "Apply Now" opportunities.
  - **Preferred Cities:** Noida, Delhi NCR, Gurugram, Kolkata, Mumbai, Pune, Bengaluru, Indore, or Remote (India).
  - **Core Skills:** Python, FastAPI, Supabase, PostgreSQL, React, JavaScript, HTML/CSS, Git/GitHub, Linux, REST APIs, ML/AI foundations.
  - **Tracked Gaps:** Java, Spring Boot, Angular, Node.js, scikit-learn, PyTorch (monitored and displayed in digests, but never penalized with negative points).

---

## 2. Hard Boundaries & Compliance Rules

1. **Strictly Single-User:** Built exclusively for one person. No multi-tenant accounts, complex auth systems, or public registrations.
2. **No Unofficial Scraping:** Absolutely zero web scraping or DOM crawling of LinkedIn, Naukri, or Indeed. No Selenium, Playwright, or headless browsers for scraping.
3. **No Auto-Applying:** The agent curates and scores opportunities; the user always clicks the direct link to review and submit applications themselves.
4. **Dual Mailbox Separation:**
   - **Mailbox A (Alerts Inbox):** Receives job alert notifications from job boards. Read-only access via SSL IMAP with an App Password.
   - **Mailbox B (Notifications Inbox):** Receives the final daily digest via SMTP (Port 587 STARTTLS). Prevents circular digest loops.
5. **Fault Isolation:**
   - Any individual source failure must never crash the pipeline; failed sources are logged to `source_runs` and named in the digest header.
   - Any delivery channel failure (Telegram vs Email) must not block the other. Jobs are marked notified if at least one channel succeeds.

---

## 3. Architecture & Data Flow

```
[8 Permitted Sources]
 ├── Greenhouse API (slug-based)
 ├── Lever API (slug-based)
 ├── Ashby API (slug-based)
 ├── SmartRecruiters API (slug-based)
 ├── Workable API / Widget (slug-based)
 ├── Adzuna Search API (5 query batches)
 ├── Remotive API (remote feed, rate-limited <= 4/day)
 └── IMAP Email Alerts (Mailbox A, whitelisted senders)
        │
        ▼
[Fault-Isolated Runner] ──> Logs metrics to `source_runs` table
        │
        ▼
[Normalization Engine]
 ├── HTML tag stripping & whitespace cleaning
 ├── Location canonicalization (Gurgaon -> Gurugram, Calcutta -> Kolkata, etc.)
 ├── URL tracker cleaning (stripping UTM, ref, tracking tokens)
 ├── Anti-Trap regex extractors: 'C', 'Go', 'REST API'
 └── Salary/Stipend parser (LPA range, annual INR, monthly stipend, USD to LPA)
        │
        ▼
[Deduplication & Freshness Filter]
 ├── Legal suffix stripping (normalize_company)
 ├── SHA-256 fingerprint: sha256(company | title | location)
 ├── Canonical URL duplicate drop
 ├── 48-hour freshness cutoff
 └── Database upsert into `seen_jobs` and `jobs`
        │
        ▼
[Eligibility & 10-Point Scoring Engine]
 ├── Hard Filters:
 │    ├── Exclude titles: senior, lead, manager, principal, staff, director, architect
 │    ├── Max required experience <= 2 years
 │    ├── Allowed batch year: 2027 only (drops other named batches like 2024/2025)
 │    └── Full-time salary floor: >= 3.5 LPA when listed
 └── 10-Point Score Breakdown:
      ├── Skills overlap: 4.0 pts (4+ skills = 4.0, 3 = 3.2, 2 = 2.4, 1 = 1.6)
      ├── Role match: 3.0 pts (41 target roles)
      ├── Level match: 2.0 pts (intern/apprentice/0-yr = 2.0, <=1 yr = 1.8, <=2 yr = 1.4)
      └── Location match: 1.0 pt (Preferred city = 1.0, India/Remote = 0.5, Abroad = 0.0)
        │
        ▼
[Jinja2 Digest Builder]
 ├── Section 1: Internships & Apprenticeships (Strong >= 7.0 & Maybe 4.0-6.9)
 ├── Section 2: Full-Time Roles (Strong >= 7.0 & Maybe 4.0-6.9)
 ├── Apply link first, pay, score, matched skills, tracked gaps, source attribution
 └── Capped at 40 items total; graceful "nothing new" empty state
        │
        ▼
[Delivery & Notification Engine]
 ├── Telegram: BotFather bot token & chat ID, splits > 4000 chars along lines
 └── Email: SMTP port 587 STARTTLS multipart HTML + plain text to Mailbox B
        │
        ▼
[Database Persistence]
 ├── Save rendered digest to `digests` table
 └── Mark delivered jobs with `notified_at = NOW()` in `seen_jobs`
```

---

## 4. Completed Sessions (Milestone 1 History)

| Session | Focus | Deliverables & Key Files | Commit Hash / Tag |
|---|---|---|---|
| **Session 0** | Setup & Skeleton | Git repo, `.venv` (Python 3.12), `requirements.txt`, `.env.example`, `docs/decisions.md`, `.github/workflows/ci.yml` | `day0: setup and initial project skeleton` |
| **Session 1** | Profile & Database Schema | `profile.example.yaml`, `job_digest/profile.py` (strict Pydantic), `database/schema.sql` (6 tables), `job_digest/db.py` (NullPool) | `day1: profile and database schema` |
| **Session 2** | Greenhouse & Lever Sources | `job_digest/models.py` (`RawJob`), `job_digest/sources/base.py`, `greenhouse.py`, `lever.py`, `sources.yaml` | `day2: source interface + greenhouse and lever` |
| **Session 3** | Ashby, SmartRecruiters, Workable | `ashby.py` (`isListed=True`), `smartrecruiters.py`, `workable.py` (v3 API + v1 widget fallback), test fixtures | `day3: ashby, smartrecruiters, and workable adapters` |
| **Session 4** | Adzuna, Remotive & Runner | `adzuna.py`, `remote.py` (max 4 fetches/day), `job_digest/sources/runner.py` (fault-isolated `run_all_sources`) | `day4: adzuna, remotive feed, and source runner` |
| **Session 5** | IMAP Email Alerts | `job_digest/sources/email_alerts.py` (read-only SSL IMAP, sender whitelist, HTML sanitizer, Message-ID deduplication) | `day5: imap email alerts source and untrusted email parser` |
| **Session 6** | Normalization & Anti-Traps | `job_digest/normalize.py` (anti-traps for C, Go, REST; 4 salary parsers; location & URL cleaners), `Job` model | `day6: job normalization, text stripping, traps, and salary parsers` |
| **Session 7** | Deduplication & Freshness | `job_digest/dedup.py` (SHA-256 fingerprint, company legal suffix stripper, 48h freshness threshold, DB upserts) | `day7: dedup, sha256 fingerprinting, freshness filter, and upserts` |
| **Session 8** | Eligibility & 10-Point Score | `job_digest/match.py` (hard filters, 10-point scoring algorithm, tracked gap visibility without penalty) | `day8: eligibility + match score` |
| **Session 9** | Jinja2 Digest Builder | `job_digest/templates/digest.html`, `digest.txt`, `job_digest/digest.py` (dual apply-now sections, 40 cap, DB persistence) | `day9: jinja2 digest builder, dual section templates, and db persistence` |
| **Session 10** | Telegram & Email Delivery | `job_digest/notify.py` (`TelegramNotifier`, `EmailNotifier`, paragraph chunking, fault-isolated delivery) | `day10: delivery via telegram and smtp email with fault isolation` |
| **Session 11** | Master Runner & Scheduler | `job_digest/run.py` (CLI `--dry-run`, `--schedule`), `.github/workflows/daily-digest.yml` (`30 2 * * *` cron), APScheduler | `day11: master pipeline runner, local apscheduler, and daily digest workflow` |
| **Session 12** | Tests, Tuning & Reliability | `tests/test_reliability_s12.py` (101 tests green, mocked-network pipeline, rate limits, source failure notices, channel fault isolation), ADR 006 | `day12: end-to-end reliability tests and tuning` |
| **Session 13** | Profile in DB + Job Status | `job_digest/profile_service.py` (validation, versioning, fallback), `job_digest/status.py` (`saved`, `applied`, `not_interested` with timestamps & notes), `user_profiles` schema, ADR 007 | `day13: profile in database and job status tracking` |
| **Session 14** | App, Login & Read Pages | `job_digest/auth.py` (Argon2, signed session cookie, login rate limit), `job_digest/web.py` (FastAPI app, today's digest, history filters), templates, ADR 008 | `day14: fastapi web app with argon2 login and read pages` |
| **Session 15** | Actions & Settings | Quick status buttons (`POST /jobs/{fp}/status`), weekly counter (`get_weekly_applied_count`), settings editor (`/settings`), source health (`/sources`), manual job entry (`/jobs/add`), ADR 009 | `day15: interactive status actions, settings editor, source health, and manual job entry` |
| **Urgency & Cadence** | Twice-Daily & Fast Alerts | Twice-daily schedule (08:00 AM & 07:00 PM IST), immediate alerts for jobs closing in ≤ 4h (`job_digest/urgency.py`), on-demand dashboard button (`POST /jobs/run-now`), ADR 010 | `b8507a0` |
| **Session 16** | Deploy | `Dockerfile` (non-root `appuser`), `render.yaml`, `Procfile`, `.dockerignore`, public `/health` endpoint with DB ping, `docs/deployment.md`, ADR 011 | `day16: deployment configuration, health check endpoint, and render blueprint` |
| **Session 17** | Hardening (Milestone 2) | Security headers middleware, robots.txt (`Disallow: /`), PWA `manifest.json`, webhook trigger (`/api/trigger`), backup script (`scripts/backup_db.py`), `docs/backup_plan.md`, ADR 012 | `day17: enterprise hardening, security headers, robots disallow, pwa manifest, and disaster recovery backup` |
| **Session 18** | Site Foundation | Static generator (`site/build.py`), clean semantic templates (index, how-it-works, sources, privacy, terms, 404), SEO validation, ADR 013 | `day18: static portfolio site builder, semantic templates, and seo validation` |
| **Session 19** | Content & Structured Data | Schema.org JSON-LD (`SoftwareApplication`, `WebSite`, `BreadcrumbList`), OpenGraph/Twitter cards (1200x630 OG image), vector assets (`architecture.svg`, `telegram-mockup.svg`), zero-placeholder audit, ADR 014 | `day19: real content, json-ld structured data, social graph, and accessible visual assets` |

---

## 5. Architectural Decisions (ADR Summary)

- **ADR 001 (Single-User Scope):** Built strictly for one personal user to minimize maintenance and avoid multi-tenant complexity.
- **ADR 002 (Tech Stack):** Python 3.12, strict Pydantic (`extra="forbid"` on profile, `"ignore"` on models), SQLAlchemy 2.0 + psycopg 3, `httpx` async client, Jinja2, FastAPI.
- **ADR 003 (Permitted Sources & Anti-Scraping):** Strict use of public ATS APIs, official search APIs (Adzuna), and personal IMAP email alerts. Zero scraping of LinkedIn/Naukri/Indeed.
- **ADR 004 (Dual-Mailbox Separation):** Mailbox A for incoming alert emails (read-only IMAP with App Password); Mailbox B for outgoing digest notifications via SMTP.
- **ADR 005 (Database Engine):** Supabase PostgreSQL accessed via Transaction/Session pooler string for IPv4 compatibility on GitHub Actions runners.
- **ADR 006 (Fault Isolation & Delivery Resilience):** Sources run in isolated try-except blocks, recording metrics to `source_runs`. Unreachable sources are highlighted in digest notices. Notifiers run independently; jobs are marked notified if $\ge 1$ channel succeeds.
- **ADR 007 (Database Profile Versioning & Job Status Tracking):** Monotonic versions stored in `user_profiles` with validation on save. Corrupted configs fall back to last good version. Status (`saved`, `applied`, `not_interested`) tracked with dedicated timestamps.
- **ADR 008 (Single-User Web Dashboard, Argon2 & Session Protection):** FastAPI app with Argon2id password hash, HMAC-SHA256 session cookie, login IP rate limiter, protected digest view and filtered job history.
- **ADR 009 (Interactive Actions, Settings Editor, Source Health & Manual Entry):** One-click status updates, weekly applied counter, web profile & blocklist editor with validation on save (changes apply to next daily run), live source health monitoring, and manual ad-hoc job submission.
- **ADR 010 (Twice-Daily Notification Cadence, Urgent Expiring Alerts & On-Demand Trigger):** Twice-daily scheduled runs (08:00 AM & 07:00 PM IST), urgent deadline detector (`≤ 4 hours left`) dispatching instant high-priority alerts to Telegram and Email, and an authenticated on-demand button (`POST /jobs/run-now`) on the dashboard header.
- **ADR 011 (Cloud Deployment Architecture, Containerization & Health Monitoring):** Decoupled architecture where GitHub Actions runs automated crawls and pushes to Supabase, web dashboard runs on Render in production container (`Dockerfile`), and public `/health` endpoint is kept alive 24/7 with free 10-minute pings (UptimeRobot).
- **ADR 012 (Production Hardening, Security Headers, Privacy & PWA Support):** Comprehensive enterprise security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options), strict crawler blocking via `X-Robots-Tag` and `/robots.txt`, authentication guard on all dashboard routes, mobile PWA manifest, token-protected webhook API, and JSON database backup snapshot utility.
- **ADR 013 (Static Showcase Site Generator & Semantic SEO Architecture):** Custom Jinja2 static site compiler (`site/build.py`) outputting cleanly formatted, pre-rendered HTML to `dist/` with directory-based clean URLs, strict semantic SEO constraints (exactly one H1, unique title, unique description, self-referential canonical, breadcrumb trails), and zero personal candidate data leakage.
- **ADR 014 (Structured Data, Social Meta Graph & Accessible Visual Asset Architecture):** Schema.org JSON-LD graph (`SoftwareApplication`, `WebSite`, `BreadcrumbList`), complete OpenGraph and Twitter card metadata (1200x630 social share preview card), accessible hand-crafted vector visual assets (`architecture.svg`, `telegram-mockup.svg`), and zero-placeholder content audit across all public pages.

---

## 6. Technical Gotchas & Environment Rules

1. **PowerShell on Windows:** Does not support `&&` for chaining commands; always use semicolon `;` (e.g. `git add . ; git commit -m "..."`).
2. **GitHub Actions YAML Syntax:** In `.github/workflows/*.yml`, the trigger key `"on":` must be enclosed in quotes because PyYAML parses bare `on:` as boolean `True`.
3. **Telegram Message Limits:** Strictly enforced at 4,096 characters per message. `split_telegram_message` partitions messages at a 4,000-character ceiling along paragraph and line boundaries so markdown links are never severed.
4. **Company Legal Suffix Normalization:** Companies appear as "Stripe", "Stripe, Inc.", "Stripe India Private Limited". `normalize_company` in `job_digest/dedup.py` removes corporate suffixes before computing the SHA-256 fingerprint to prevent duplicate listings.
5. **Database Pools for Serverless/CLI:** Use `NullPool` in `job_digest/db.py` to prevent hanging connection pools when running ephemeral CLI pipelines or GitHub Actions workflows.
6. **Starlette / FastAPI TemplateResponse Signature:** Modern Starlette requires keyword arguments: `templates.TemplateResponse(request=request, name="...", context={...})`. Passing positional arguments causes Jinja2 cache `TypeError: unhashable type: 'dict'`.
7. **SQLite In-Memory Multi-Threading in Tests:** In FastAPI TestClient tests with in-memory SQLite, always configure `engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)` to prevent thread collision errors.
8. **FastAPI Parameter Shadowing:** Never name route arguments `status: str` if referencing `from fastapi import status` for HTTP codes (e.g., `status.HTTP_303_SEE_OTHER`); use direct integer codes (`303`) or alias imports.
9. **Free Cloud Host Sleep Prevention:** Free PaaS hosts (Render) hibernate after 15 minutes of inactivity. Set up an external ping monitor (UptimeRobot) to query `/health` every 10 minutes to maintain 24/7 responsiveness. Autonomous crawler runs (GitHub Actions) remain completely unaffected by web host state.
10. **Python stdlib `site` Module Namespace Collision:** Python's standard library includes `site.py`. Avoid `import site.build` directly; invoke `python site/build.py` or use dynamic path imports via `importlib.util.spec_from_file_location` in tests and build tools.

---

## 7. Road Ahead: Remaining Phases

### Phase 2: Private Single-User Web App (Sessions 13 to 17) — COMPLETED (Milestone 2 Achieved!)
- **Session 13:** Move profile to `user_profiles` table with versioning; job status tracking (`saved`, `applied`, `not_interested`, notes).
- **Session 14:** FastAPI app + Jinja2 dashboard, Argon2 single-user auth, session cookies, multi-criteria filters.
- **Session 15:** Quick status action buttons, weekly applied counter, profile & blocklist editor, source health, manual job entry.
- **Session 16:** Production deployment files (`Dockerfile`, `render.yaml`, `Procfile`), public `/health` endpoint, keepalive monitoring.
- **Session 17:** Enterprise hardening: security headers middleware (CSP, HSTS, X-Frame-Options), robots.txt (`Disallow: /`), PWA `manifest.json`, webhook trigger (`/api/trigger`), disaster recovery backup utility (`scripts/backup_db.py`).
- **Milestone 2 Result:** Verified personal mobile dashboard with 100% login protection, zero search engine indexation, and real-time application tracking.

### Phase 3: Public Showcase Site (Sessions 18 to 21)
- **Session 18 (Completed):** Static Jinja2 generator (`site/build.py`), clean semantic templates (index, how-it-works, sources, privacy, terms, 404), SEO validation tests (1 H1, unique title/description/canonical).
- **Session 19 (Completed):** Schema.org JSON-LD structured data (`SoftwareApplication`, `WebSite`, `BreadcrumbList`), social preview assets (1200x630 OG image), architecture diagram SVG, real Telegram mockup, zero placeholder audit.
- **Session 20:** GitHub Pages deployment, custom domain setup, `sitemap.xml`, `robots.txt`, `llms.txt`.
- **Session 21:** Anti-slop content audit, performance optimization (zero console errors, small CSS/JS bundles), pre-launch checklist verification.

### Phase 4: Project Wrap-Up
- **Session 22:** Comprehensive documentation, portfolio integration, live walkthrough verification, and final handoff.
