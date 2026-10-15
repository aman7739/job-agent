# Architecture Decision Records (ADRs)

This document records the key architectural and design decisions for the Job Digest Agent.

---

## ADR 001: Personal Single-User Scope & Technology Stack
- **Status:** Accepted
- **Decision:** Build a single-tenant personal automation pipeline using Python 3.12, FastAPI, SQLAlchemy 2.0 (async), and PostgreSQL.
- **Rationale:** Keeps infrastructure overhead minimal, avoids complex multi-tenant IAM, and optimizes for rapid iteration and personal job search tracking.

---

## ADR 002: Permitted Sources Policy & Zero Web Scraping
- **Status:** Accepted
- **Decision:** Ingest jobs strictly through public career board APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workable), authorized aggregator APIs (Adzuna, Jooble, Remotive, Arbeitnow), and inbound email parsing. Zero DOM scraping of LinkedIn, Naukri, or Indeed.
- **Rationale:** Ensures long-term pipeline resilience without fragile HTML selectors, avoids bot-detection blocks, and strictly complies with platform Terms of Service.

---

## ADR 003: Dual-Mailbox Separation for Email Operations
- **Status:** Accepted
- **Decision:** Split email into two distinct accounts:
  1. **Mailbox A (Ingestion):** Receives automated alerts from LinkedIn and Naukri; parsed via IMAP.
  2. **Mailbox B (Delivery):** Dedicated sender account delivering formatted morning/evening HTML digests via SMTP.
- **Rationale:** Prevents credential overlap, isolates read permissions from send permissions, and avoids infinite mail loops.

---

## ADR 004: Database Storage & Connection Pooling
- **Status:** Accepted
- **Decision:** Production PostgreSQL 16 hosted on Neon Serverless (AWS `ap-southeast-1`) accessed via connection pooling with `NullPool` in asyncpg.
- **Rationale:** Serverless PostgreSQL scales to zero during idle hours, while connection pooling prevents connection starvation during high-concurrency pipeline bursts.

---

## ADR 005: Pipeline Fault Isolation & SHA-256 Deduplication
- **Status:** Accepted
- **Decision:**
  1. Every job source adapter executes inside an independent try/except block; a failed source logs to `source_runs` and reports in the digest header without terminating the run.
  2. Deduplication computes a deterministic SHA-256 fingerprint: `sha256(lowercase(company) + "|" + lowercase(title) + "|" + canonical_url)`.
  3. Source attribution is recorded in `job_sightings` to measure source yield over time.
- **Rationale:** Prevents single-adapter outages from halting daily deliveries and eliminates duplicate job alerts across platforms.

---

## ADR 006: Graduated 10-Point Scoring Engine & Seniority Guards
- **Status:** Accepted
- **Decision:**
  - **Knockouts:** Hard exclusions for strict senior titles (Sr., Staff, VP, Director, Chief) unless counter-balanced by intern/trainee guards.
  - **Graduated Scoring:** Title match (3.0 pts), Skills match (up to 4.0 pts graduated), Location match (1.5 pts), Recency bonus (1.0 pt), Fast-response source bonus (0.5 pt).
  - **Buckets:** Strong Match (>= 7.0 pts) and Maybe Match (4.0 - 6.9 pts).
- **Rationale:** Maximizes precision for entry-level and fresher software engineering roles while maintaining visibility into promising adjacent opportunities.

---

## ADR 007: Dynamic Profile Versioning & Job Status Tracking
- **Status:** Accepted
- **Decision:** Store the candidate's active profile in the `user_profiles` table with monotonic versioning. Application statuses (`saved`, `applied`, `not_interested`) are tracked in `seen_jobs` with explicit timestamp columns (`saved_at`, `applied_at`, `not_interested_at`).
- **Rationale:** Enables live adjustments to keywords and blocklists from the web dashboard without redeploying code or risking configuration corruption.

---

## ADR 008: Web Dashboard Security, Argon2 & Signed Sessions
- **Status:** Accepted
- **Decision:** Secure the private dashboard with Argon2id password hashing, HMAC-SHA256 signed session cookies (`HttpOnly`, `SameSite=Lax`), and in-memory IP rate limiting on login attempts.
- **Rationale:** Provides strong protection for personal data without the complexity of third-party OAuth providers.

---

## ADR 009: Scheduling Topology & Keepalive Heartbeat
- **Status:** Accepted
- **Decision:**
  1. Schedule daily digests twice daily at 08:00 AM IST and 07:00 PM IST via in-app APScheduler.
  2. Urgent expiring postings (<= 4h deadline) trigger instant push alerts.
  3. External cron heartbeat pings `/health` every 10 minutes to maintain container warmth and prevent cold-start latency.
- **Rationale:** Eliminates queue latency from free-tier external runners and ensures on-time notification delivery.

---

## ADR 010: Non-Blocking Header-First IMAP Ingestion
- **Status:** Accepted
- **Decision:** Offload IMAP socket operations to `asyncio.to_thread` with a 15-second timeout. Pre-filter incoming messages using header-only queries (`FROM`, `MESSAGE-ID`) to skip non-whitelisted senders before downloading full message bodies.
- **Rationale:** Reduces IMAP ingestion time from minutes to seconds and avoids blocking FastAPI's async event loop.
