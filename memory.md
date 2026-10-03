# Job Digest Agent — Project Memory & Context

> **Last Updated:** Session 12 (Milestone 1 Completed)  
> **Target Audience:** Agent context persistence across sessions and long-term project reference.

---

## 1. Project Vision & User Profile

- **Project Purpose:** A private, autonomous, high-reliability personal Job Digest Agent running daily at 08:00 IST. It aggregates postings from 8 permitted sources, normalizes and deduplicates them, scores eligibility against a personal profile, and delivers formatted morning digests via Telegram and SMTP Email.
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

---

## 6. Technical Gotchas & Environment Rules

1. **PowerShell on Windows:** Does not support `&&` for chaining commands; always use semicolon `;` (e.g. `git add . ; git commit -m "..."`).
2. **GitHub Actions YAML Syntax:** In `.github/workflows/*.yml`, the trigger key `"on":` must be enclosed in quotes because PyYAML parses bare `on:` as boolean `True`.
3. **Telegram Message Limits:** Strictly enforced at 4,096 characters per message. `split_telegram_message` partitions messages at a 4,000-character ceiling along paragraph and line boundaries so markdown links are never severed.
4. **Company Legal Suffix Normalization:** Companies appear as "Stripe", "Stripe, Inc.", "Stripe India Private Limited". `normalize_company` in `job_digest/dedup.py` removes corporate suffixes before computing the SHA-256 fingerprint to prevent duplicate listings.
5. **Database Pools for Serverless/CLI:** Use `NullPool` in `job_digest/db.py` to prevent hanging connection pools when running ephemeral CLI pipelines or GitHub Actions workflows.

---

## 7. Road Ahead: Remaining Phases

### Phase 2: Private Single-User Web App (Sessions 13 to 17)
- **Session 13:** Move profile from YAML to database table `user_profiles` with versioning; add `job_status` tracking (`saved`, `applied`, `not_interested`, `archived`) with timestamps.
- **Session 14:** FastAPI backend + Jinja2 HTML dashboard. Single-user session authentication (cookie-based password protection). Responsive UI with Tailwind/custom CSS.
- **Session 15:** Dashboard actions: one-click status updates (`Save`, `Applied`, `Not Interested`), notes field, and web-based profile settings editor.
- **Session 16:** Hosting deployment (Render / Railway / Fly.io / VPS free-tier), persistent database connection, environment configuration.
- **Session 17:** Security hardening: `robots.txt` (`Disallow: /`), `X-Robots-Tag: noindex, nofollow`, strict rate limiting on auth endpoints, HTTPS enforcement.

### Phase 3: Public Showcase Site (Sessions 18 to 21)
- **Session 18:** Static Jinja2 generator (`site/build.py`), clean semantic markup, page metadata, unique titles, OpenGraph tags, and responsive design.
- **Session 19:** Schema.org JSON-LD structured data (`SoftwareSourceCode`, `Project`), social preview assets, privacy & terms pages.
- **Session 20:** GitHub Pages deployment, custom domain setup, `sitemap.xml`, `robots.txt`, `llms.txt`.
- **Session 21:** Anti-slop content audit, performance optimization (zero console errors, small CSS/JS bundles), pre-launch checklist verification.

### Phase 4: Project Wrap-Up
- **Session 22:** Comprehensive documentation, portfolio integration, live walkthrough verification, and final handoff.
