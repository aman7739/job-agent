# Architectural Decision Records (ADRs)

## ADR 001: Personal Single-User Scope
- **Status:** Accepted
- **Decision:** The system is strictly personal (single user, single profile, no multi-tenant accounts).
- **Rationale:** Minimizes complexity and operational overhead while maximizing relevance to the user's specific career trajectory (B.Tech CSE Batch 2027).

## ADR 002: Tech Stack
- **Status:** Accepted
- **Decision:** Python 3.12, strict Pydantic models, SQLAlchemy 2.0 + psycopg 3, httpx for asynchronous requests, Jinja2 for templates, FastAPI for the private dashboard.
- **Rationale:** Robust typing, excellent async I/O performance, maintainable and predictable without overhead.

## ADR 003: Permitted Sources & Anti-Scraping
- **Status:** Accepted
- **Decision:** Collect only via public ATS APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workable), official job search APIs (Adzuna), and personal email alerts over IMAP. No scraping of LinkedIn, Naukri, or Indeed.
- **Rationale:** Compliance with terms of service, high reliability, zero IP ban risk.

## ADR 004: Dual-Mailbox Separation
- **Status:** Accepted
- **Decision:** Read incoming alert emails from Mailbox A (alerts inbox) over IMAP with an app password. Send daily digests to Mailbox B (notifications inbox) via SMTP.
- **Rationale:** Prevents circular processing or email clutter; eliminates OAuth token expiry issues in testing mode.

## ADR 005: Database Selection
- **Status:** Accepted
- **Decision:** Supabase PostgreSQL using transaction/session pooler connection string (IPv4 compatible).
- **Rationale:** Free tier, hosted cloud database, reliable access from GitHub Actions runners which often lack IPv6.

## ADR 006: Pipeline Fault Isolation, Rate Limiting & Delivery Resilience (Milestone 1)
- **Status:** Accepted
- **Decision:** All 8 sources and both notification channels (Telegram, SMTP Email) operate with full fault isolation:
  1. Failed sources are captured, logged to `source_runs`, and prominently reported in the digest header notice without halting the pipeline.
  2. Rate limiting safeguards (e.g. Remotive max 4 fetches/calendar day) prevent quota exhaustion and API bans.
  3. Notification channels are independent: if Telegram fails, Email still delivers, and vice-versa. Jobs are marked notified only after at least one channel succeeds. If all channels fail, jobs remain unnotified for retry.
- **Rationale:** Guarantees reliable daily morning deliveries at 08:00 IST without silent dropouts or repeated duplicate spam.

## ADR 007: Database Profile Versioning & Job Application Status Tracking (Session 13)
- **Status:** Accepted
- **Decision:** Move the profile from static environment files into the database (`user_profiles` table) with monotonic versioning and validation on save:
  1. Every profile save is strictly validated against `UserProfile` (`extra="forbid"`) before commit.
  2. Invalid edits are rejected loudly and do not overwrite the active configuration.
  3. Corrupted active versions in the database automatically fall back to the most recent valid version in history.
  4. Application statuses (`saved`, `applied`, `not_interested`) and notes are tracked on `seen_jobs` with explicit timestamp columns (`saved_at`, `applied_at`, `not_interested_at`).
- **Rationale:** Allows dynamic profile updates and application tracking from any device (web dashboard in Phase 2) while safeguarding daily runs against corrupted configurations.

## ADR 008: Single-User Web Dashboard, Argon2 Authentication & Session Protection (Session 14)
- **Status:** Accepted
- **Decision:** Private web access is built with FastAPI and Jinja2 templates:
  1. Single-user master password verified with Argon2id (`argon2-cffi`).
  2. Tamper-proof session tokens signed with HMAC-SHA256, set as `HttpOnly`, `SameSite=Lax` cookies with 7-day expiration.
  3. In-memory IP rate limiter restricts failed login attempts (max 5 failures per 5-minute window returning HTTP 429).
  4. All read pages (`/` for today's digest, `/history` for job history with multi-criteria filters) strictly require an authenticated session; unauthenticated traffic is redirected to `/login`.
- **Rationale:** Prevents unauthorized external access without overhead of multi-user authentication providers.

## ADR 009: Interactive Actions, Settings Editor, Source Health & Manual Entry (Session 15)
- **Status:** Accepted
- **Decision:** Provide interactive write actions and settings controls on the web dashboard:
  1. Quick actions (`POST /jobs/{fingerprint}/status`) allow immediate status transitions (`saved`, `applied`, `not_interested`, `seen`) with automatic return to referer.
  2. Weekly application progress counter (`get_weekly_applied_count`) queries the last 7 days of `applied_at` timestamps and displays a badge across all navigation views (`🎯 Applied this week: X`).
  3. Dynamic profile editor (`/settings`) allows updating the company blocklist, roles, scoring thresholds, and notification channels with validation on save (`extra="forbid"`), immediately taking effect on the next autonomous pipeline run.
  4. Real-time source health monitor (`/sources`) inspects recent `source_runs` across all 8 adapters to provide visual green/yellow/red status indicators, error logs, and freshness tracking.
  5. Manual job ingestion (`/jobs/add`) allows candidate to enter ad-hoc job listings, automatically computes SHA-256 fingerprint, extracts candidate skills, scores against the active profile, and saves to the database for tracking.
- **Rationale:** Empowers the candidate to manage daily application workflows and fine-tune filtering parameters from any device (including mobile) while maintaining strict schema integrity.
