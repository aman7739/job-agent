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

## ADR 010: Twice-Daily Notification Cadence, Urgent Expiring Alerts & On-Demand Trigger
- **Status:** Accepted
- **Decision:** Enhance pipeline notification triggers:
  1. Increase automated execution frequency to twice daily at 08:00 AM IST (02:30 UTC) and 07:00 PM IST (13:30 UTC) in GitHub Actions (`.github/workflows/daily-digest.yml`) and local APScheduler.
  2. Implement an urgent deadline detector (`job_digest/urgency.py`) to catch postings closing within <= 4 hours. Deliver immediate high-priority alerts (`deliver_urgent_alert` in `job_digest/notify.py`) via Telegram and Email without waiting for the scheduled digest window.
  3. Provide an authenticated on-demand button (`POST /jobs/run-now`) in the web dashboard header allowing the candidate to scan all sources, score new roles, and receive an instant delivery update anytime from browser.
- **Rationale:** Prevents missing rapid-closing tech opportunities (e.g. 24-hour flash application windows) while giving candidate instant manual control from mobile or desktop.

## ADR 011: Cloud Deployment Architecture, Containerization & Health Monitoring (Session 16)
- **Status:** Accepted
- **Decision:** Deploy the personal system using a decoupled cloud topology:
  1. The automated job pipeline runs via GitHub Actions cron twice daily (08:00 AM & 07:00 PM IST) and pushes to Supabase PostgreSQL, remaining completely independent of web server state.
  2. The web dashboard is packaged as a secure production container (`Dockerfile` running as non-root `appuser`) and deployed to a free cloud host (Render / Railway / Fly.io) with Infrastructure-as-Code definitions (`render.yaml`, `Procfile`).
  3. A public, unauthenticated health check endpoint (`GET /health`) verifies process uptime, application status, and database connectivity (`SELECT 1`). If the database fails, it returns HTTP 503 degraded.
  4. Free external uptime monitoring (e.g. UptimeRobot) pings `/health` at 10-minute intervals, simultaneously monitoring system liveness and preventing free-tier server hibernation.
- **Rationale:** Delivers zero-cost 24/7 reliability, immediate mobile access, and operational independence between daily notification delivery and interactive web viewing.

## ADR 012: Production Hardening, Security Headers, Privacy & PWA Support (Session 17)
- **Status:** Accepted
- **Decision:** Implement comprehensive hardening controls across the web dashboard:
  1. Attach enterprise HTTP security headers via middleware (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Content-Security-Policy`, `Referrer-Policy`, and `Permissions-Policy`).
  2. Enforce strict privacy against web scrapers and search indexing with `X-Robots-Tag: noindex, nofollow, noarchive, nosnippet`, HTML `<meta name="robots" content="noindex, nofollow">`, and `GET /robots.txt` (`Disallow: /`).
  3. Ensure all private routes (`/`, `/history`, `/settings`, `/sources`, `/jobs/*`) reject unauthenticated traffic with immediate 303 redirection to `/login`.
  4. Provide a Web App Manifest (`/manifest.json`) and mobile viewport optimization enabling install-to-home-screen PWA experience on iOS and Android.
  5. Add token-protected webhook endpoint (`POST /api/trigger`) for secure external automations.
  6. Provide an application-level disaster recovery backup script (`scripts/backup_db.py`) capturing candidate profiles, job statuses, and digest history into structured JSON snapshots.
- **Rationale:** Protects personal candidate data, prevents search indexing, hardens against OWASP web vulnerabilities, and delivers a mobile-native application feel.

## ADR 013: Static Showcase Site Generator & Semantic SEO Architecture (Session 18)
- **Status:** Accepted
- **Decision:** Build a dedicated static portfolio site generator (`site/build.py`) compiling Jinja2 templates into static HTML in `dist/`:
  1. The public site operates under strict air-gap separation from the private application: it describes the architecture, permitted sources, and technical safeguards without ever revealing the candidate's personal profile, job notes, or actual digest opportunities.
  2. Enforce strict semantic SEO constraints across all pages: exactly one `<h1>` per page, unique title per page, unique meta description per page, and explicit canonical `<link rel="canonical">` tags.
  3. Clean directory-based slug structure (`/how-it-works/index.html`, `/sources/index.html`, `/privacy/index.html`, `/terms/index.html`) with breadcrumb navigation.
- **Rationale:** Provides an impressive public showcase for portfolio review and technical interviews while keeping personal job searches and candidate data 100% private.

## ADR 014: Structured Data (JSON-LD), Social Graph & Accessible Visual Assets (Session 19)
- **Status:** Accepted
- **Decision:** Enhance the public portfolio showcase with authentic technical content, structured metadata, and accessible visual assets:
  1. Embed Schema.org JSON-LD graph structures across all rendered pages: `WebSite` describing site hierarchy, `SoftwareApplication` declaring application categorization, operating system, zero cost, and developer attribution, and `BreadcrumbList` providing search-engine-readable navigational context on all subpages.
  2. Implement complete Open Graph and Twitter Card tags (`og:title`, `og:description`, `og:image`, `og:url`, `og:type`, `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`) backed by a high-resolution 1200x630 social share preview card (`site/static/images/og-image.png`).
  3. Author hand-crafted vector visual assets (`architecture.svg` and `telegram-mockup.svg`) providing crisp, zoomable, dark-mode-styled illustrations with accessible `<title>`, `<desc>`, and descriptive `alt` tags.
  4. Enforce strict content integrity: zero placeholder tokens (`lorem`, `TODO`, `placeholder`), explicit candidate context (final-year B.Tech CSE Batch 2027 targeting both Internships and Full-Time fresher roles immediately), and transparent Privacy/Terms guaranteeing zero publication of personal candidate data.
- **Rationale:** Establishes professional technical portfolio credibility, rich search engine snippet readiness, and social share polish while respecting privacy and accessibility standards.

## ADR 015: Domain Deployment, Crawl Files (Sitemap, Robots, LLMs.txt) & GitHub Pages Automation (Session 20)
- **Status:** Accepted
- **Decision:** Automate static deployment and web crawler discovery files:
  1. Generate `sitemap.xml` at build time adhering to the Sitemaps 0.9 protocol, listing all indexable canonical pages (`/`, `/how-it-works/`, `/sources/`, `/privacy/`, `/terms/`) with `<lastmod>`, `<changefreq>`, and `<priority>`, while strictly excluding error pages like `/404.html`.
  2. Generate a permissive public `robots.txt` allowing search crawlers (`Allow: /`, `Disallow: /404.html`) and referencing the sitemap index.
  3. Generate `llms.txt` adhering to the llmstxt.org standard to provide markdown summaries and structured documentation links for AI search crawlers and LLM agents.
  4. Provide a GitHub Actions deployment workflow (`.github/workflows/pages.yml`) deploying compiled `dist/` directly to GitHub Pages on push to `main` with proper deployment permissions (`pages: write`, `id-token: write`).
  5. Provide complete custom domain DNS instructions (`docs/domain_setup.md`) covering apex domain `A` records (185.199.108.153 series), subdomain `CNAME`, automatic Let's Encrypt TLS provisioning, and HTTPS enforcement.
- **Rationale:** Delivers automated zero-cost hosting, rapid deployment turnaround, rich indexing across search engines and AI assistants, and complete SSL protection.
