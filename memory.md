# Job Digest Agent — Project Memory & Context

> **Last Updated:** Post-Launch Production Milestone (All 8 Sources 100% Healthy & Live on Render!)  
> **Target Audience:** Agent context persistence across sessions and long-term project reference.

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

## 3. Architecture & Data Flow

```
[8 Permitted Sources]
 ├── Greenhouse API (18 company slugs, e.g. Cloudflare, Stripe, Datadog)
 ├── Lever API (8 company slugs, e.g. Palantir, Spotify, Canonical)
 ├── Ashby API (8 company slugs, e.g. OpenAI, Figma, Notion, Linear)
 ├── SmartRecruiters API (4 company slugs, e.g. Bosch, IKEA, Ubisoft, Visa)
 ├── Workable API / Widget (4 company slugs, e.g. Transferwise, Harness)
 ├── Adzuna Search API (Live Indian tech jobs: Python, ML/AI, QA, Web, Internships)
 ├── Remotive API (Remote tech vacancies in India / Worldwide)
 └── IMAP Email Alerts (Header-First, Non-Blocking Thread, 11 Whitelisted Platforms)
        │
        ▼
[Fault-Isolated Runner (45s Timeout per Source)] ──> Logs metrics to `source_runs`
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
 │    ├── Strict title exclusion: senior, lead, manager, principal, staff, director, architect, head, VP, leadership
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

## 4. Completed Sessions & Milestone History

| Session | Focus | Deliverables & Key Files | Commit Hash / Tag |
|---|---|---|---|
| **Session 0** | Setup & Skeleton | Git repo, `.venv` (Python 3.12), `requirements.txt`, `.env.example`, `docs/decisions.md`, `.github/workflows/ci.yml` | `day0` |
| **Session 1** | Profile & Database Schema | `profile.example.yaml`, `job_digest/profile.py` (strict Pydantic), `database/schema.sql` (6 tables), `job_digest/db.py` (NullPool) | `day1` |
| **Session 2** | Greenhouse & Lever Sources | `job_digest/models.py` (`RawJob`), `job_digest/sources/base.py`, `greenhouse.py`, `lever.py`, `sources.yaml` | `day2` |
| **Session 3** | Ashby, SmartRecruiters, Workable | `ashby.py` (`isListed=True`), `smartrecruiters.py`, `workable.py` (v3 API + v1 widget fallback), test fixtures | `day3` |
| **Session 4** | Adzuna, Remotive & Runner | `adzuna.py`, `remote.py` (max 4 fetches/day), `job_digest/sources/runner.py` (fault-isolated `run_all_sources`) | `day4` |
| **Session 5** | IMAP Email Alerts | `job_digest/sources/email_alerts.py` (read-only SSL IMAP, sender whitelist, HTML sanitizer, Message-ID deduplication) | `day5` |
| **Session 6** | Normalization & Anti-Traps | `job_digest/normalize.py` (anti-traps for C, Go, REST; 4 salary parsers; location & URL cleaners), `Job` model | `day6` |
| **Session 7** | Deduplication & Freshness | `job_digest/dedup.py` (SHA-256 fingerprint, company legal suffix stripper, 48h freshness threshold, DB upserts) | `day7` |
| **Session 8** | Eligibility & 10-Point Score | `job_digest/match.py` (hard filters, 10-point scoring algorithm, tracked gap visibility without penalty) | `day8` |
| **Session 9** | Jinja2 Digest Builder | `job_digest/templates/digest.html`, `digest.txt`, `job_digest/digest.py` (dual apply-now sections, 40 cap, DB persistence) | `day9` |
| **Session 10** | Telegram & Email Delivery | `job_digest/notify.py` (`TelegramNotifier`, `EmailNotifier`, paragraph chunking, fault-isolated delivery) | `day10` |
| **Session 11** | Master Runner & Scheduler | `job_digest/run.py` (CLI `--dry-run`, `--schedule`), `.github/workflows/daily-digest.yml` (`30 2 * * *` cron), APScheduler | `day11` |
| **Session 12** | Tests, Tuning & Reliability | `tests/test_reliability_s12.py` (101 tests green, mocked-network pipeline, rate limits, source failure notices, channel fault isolation), ADR 006 | `day12` |
| **Session 13** | Profile in DB + Job Status | `job_digest/profile_service.py` (validation, versioning, fallback), `job_digest/status.py` (`saved`, `applied`, `not_interested` with timestamps & notes), `user_profiles` schema, ADR 007 | `day13` |
| **Session 14** | App, Login & Read Pages | `job_digest/auth.py` (Argon2, signed session cookie, login rate limit), `job_digest/web.py` (FastAPI app, today's digest, history filters), templates, ADR 008 | `day14` |
| **Session 15** | Actions & Settings | Quick status buttons (`POST /jobs/{fp}/status`), weekly counter (`get_weekly_applied_count`), settings editor (`/settings`), source health (`/sources`), manual job entry (`/jobs/add`), ADR 009 | `day15` |
| **Urgency & Cadence** | Twice-Daily & Fast Alerts | Twice-daily schedule (08:00 AM & 07:00 PM IST), immediate alerts for jobs closing in ≤ 4h (`job_digest/urgency.py`), on-demand dashboard button (`POST /jobs/run-now`), ADR 010 | `b8507a0` |
| **Session 16** | Deploy | `Dockerfile` (non-root `appuser`), `render.yaml`, `Procfile`, `.dockerignore`, public `/health` endpoint with DB ping, `docs/deployment.md`, ADR 011 | `day16` |
| **Session 17** | Hardening (Milestone 2) | Security headers middleware, robots.txt (`Disallow: /`), PWA `manifest.json`, webhook trigger (`/api/trigger`), backup script (`scripts/backup_db.py`), `docs/backup_plan.md`, ADR 012 | `day17` |
| **Session 18** | Site Foundation | Static generator (`site/build.py`), clean semantic templates (index, how-it-works, sources, privacy, terms, 404), SEO validation, ADR 013 | `day18` |
| **Session 19** | Content & Structured Data | Schema.org JSON-LD (`SoftwareApplication`, `WebSite`, `BreadcrumbList`), OpenGraph/Twitter cards (1200x630 OG image), vector assets (`architecture.svg`, `telegram-mockup.svg`), zero-placeholder audit, ADR 014 | `day19` |
| **Session 20** | Domain & Crawl Files | Build-time `sitemap.xml`, permissive `robots.txt`, `llms.txt`, custom `404.html`, GitHub Pages workflow (`pages.yml`), `docs/domain_setup.md`, ADR 015 | `day20` |
| **Session 21** | Pre-Launch Audit & Release | Bundle hygiene (0 KB JS, ~6 KB CSS), anti-slop design audit, production `README.md`, all 20 pre-launch checklist items verified, tagged `v1.0.0`, ADR 016 | `day21` |
| **Session 22** | Wrap-Up & Handoff | Operational runbook (`docs/runbook.md`), portfolio briefing (`docs/portfolio_summary.md`), all 17 ADRs verified, 166 tests passing, ADR 017 | `day22` |
| **Session 23+ (Post-Launch)** | High-Speed IMAP & Sources | IMAP header-first inspection, `asyncio.to_thread` worker offloading, 15s socket timeout, single-query `/sources` batching (sub-100ms load), button loading state, 45s source runner safety timeout | `5b65337` |
| **Session 24+ (Multi-Platform)** | 11-Platform Email Expansion | Added Internshala, Unstop, Instahyre, Wellfound, Cutshort, Foundit, Glassdoor, Hirist to IMAP engine; universal job parser; fallback aria/title tag parsing | `e22c0ef` |
| **Session 25+ (Live Adzuna)** | Adzuna API Production Live | Live integration of `ADZUNA_APP_ID` & `ADZUNA_APP_KEY`, verified 20 live Indian tech jobs, achieved 100% Green (8/8 sources Healthy) | Live on Render |

---

## 5. Architectural Decisions (ADR Summary)

- **ADR 001 (Single-User Scope):** Built strictly for one personal user to minimize maintenance and avoid multi-tenant complexity.
- **ADR 002 (Tech Stack):** Python 3.12, strict Pydantic (`extra="forbid"` on profile, `"ignore"` on models), SQLAlchemy 2.0 + psycopg 3, `httpx` async client, Jinja2, FastAPI.
- **ADR 003 (Permitted Sources & Anti-Scraping):** Strict use of public ATS APIs, official search APIs (Adzuna), and personal IMAP email alerts. Zero scraping of LinkedIn/Naukri/Indeed.
- **ADR 004 (Dual-Mailbox Separation):** Mailbox A for incoming alert emails (read-only IMAP with App Password); Mailbox B for outgoing digest notifications via SMTP.
- **ADR 005 (Database Engine):** Supabase/Neon PostgreSQL accessed via Transaction/Session pooler string with `NullPool` to prevent idle connection exhaustion.
- **ADR 006 (Fault Isolation & Delivery Resilience):** Sources run in isolated try-except blocks, recording metrics to `source_runs`. Unreachable sources are highlighted in digest notices. Notifiers run independently; jobs are marked notified if $\ge 1$ channel succeeds.
- **ADR 007 (Database Profile Versioning & Job Status Tracking):** Monotonic versions stored in `user_profiles` with validation on save. Corrupted configs fall back to last good version. Status (`saved`, `applied`, `not_interested`) tracked with dedicated timestamps.
- **ADR 008 (Single-User Web Dashboard, Argon2 & Session Protection):** FastAPI app with Argon2id password hash, HMAC-SHA256 session cookie, login IP rate limiter, protected digest view and filtered job history.
- **ADR 009 (Interactive Actions, Settings Editor, Source Health & Manual Entry):** One-click status updates, weekly applied counter, web profile & blocklist editor with validation on save, live source health monitoring, and manual ad-hoc job submission.
- **ADR 010 (Twice-Daily Notification Cadence, Urgent Expiring Alerts & On-Demand Trigger):** Twice-daily scheduled runs (08:00 AM & 07:00 PM IST), urgent deadline detector (`≤ 4 hours left`) dispatching instant high-priority alerts to Telegram and Email, and an authenticated on-demand button (`POST /jobs/run-now`) on the dashboard header.
- **ADR 011 (Cloud Deployment Architecture, Containerization & Health Monitoring):** Decoupled architecture where GitHub Actions runs automated crawls and pushes to Supabase, web dashboard runs on Render in production container (`Dockerfile`), and public `/health` endpoint is kept alive 24/7 with free 10-minute pings.
- **ADR 012 (Production Hardening, Security Headers, Privacy & PWA Support):** Comprehensive enterprise security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options), strict crawler blocking via `X-Robots-Tag` and `/robots.txt`, authentication guard on all dashboard routes, mobile PWA manifest, token-protected webhook API, and JSON database backup snapshot utility.
- **ADR 013 (Static Showcase Site Generator & Semantic SEO Architecture):** Custom Jinja2 static site compiler (`site/build.py`) outputting cleanly formatted HTML to `dist/` with directory-based clean URLs, strict semantic SEO constraints, and zero personal candidate data leakage.
- **ADR 014 (Structured Data, Social Meta Graph & Accessible Visual Asset Architecture):** Schema.org JSON-LD graph (`SoftwareApplication`, `WebSite`, `BreadcrumbList`), complete OpenGraph and Twitter card metadata (1200x630 social share preview card), accessible hand-crafted vector visual assets (`architecture.svg`, `telegram-mockup.svg`), and zero-placeholder content audit across all public pages.
- **ADR 015 (Domain Deployment, Crawl Files & GitHub Pages Automation):** Automated generation of Sitemaps 0.9 protocol `sitemap.xml`, permissive `robots.txt`, structured `llms.txt` for AI crawlers, custom recovery `404.html`, automated `.github/workflows/pages.yml` deployment on push, and DNS/HTTPS custom domain guide (`docs/domain_setup.md`).
- **ADR 016 (Production Pre-Launch Audit, Anti-Slop Enforcement & Release Baseline):** Distribution hygiene (0 source maps, 0 KB JS, ~6 KB unminified CSS, 0 console errors), strict anti-slop rules compliance, comprehensive production `README.md`, verified 20-point pre-launch checklist, and release tagging `v1.0.0`.
- **ADR 017 (Project Wrap-Up, Operational Runbook & Final Production Handoff):** Complete operational runbook (`docs/runbook.md`), portfolio briefing (`docs/portfolio_summary.md`), all 17 ADRs verified, 166 tests passing, and production-ready handoff.
- **ADR 018 (Non-Blocking Header-First IMAP Architecture):** Offloads synchronous IMAP fetching to `asyncio.to_thread` with strict 15s socket timeout, filters emails by header fields (`FROM`, `MESSAGE-ID`) under 1 KB, skips unauthorized senders and cached Message-IDs in 1ms, and searches only past 3 days (`SINCE`). Eliminates event-loop blocking and cuts crawl duration from 5 minutes to 3 seconds.
- **ADR 019 (Single-Query Dashboard Source Health Architecture):** Replaces 8 individual sequential database roundtrips with a single batch query (`ORDER BY started_at DESC LIMIT 200`) grouped in memory, achieving sub-100ms `/sources` page load times even during remote Singapore-to-client network latency.
- **ADR 020 (Multi-Platform Job Alert Ingestion & Universal Parser):** Extends IMAP whitelisting from 3 to 11 major platforms (Internshala, Unstop, Instahyre, Wellfound, Cutshort, Foundit, Glassdoor, Hirist) with domain pattern matching, specialized internship extractors, and a universal job link parser for untrusted email HTML.

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

---

## 7. Live Production Deployment & Verification (Active & Verified)

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
- **Total Reach:** Over **1,410+ raw roles** scanned and normalized across both Indian and global tech markets.
- **Test Suite Status:** **180 passing unit and integration tests (100% green).**
