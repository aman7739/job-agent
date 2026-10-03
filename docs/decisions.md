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
