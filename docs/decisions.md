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
