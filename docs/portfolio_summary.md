# Job Digest Agent &bull; Portfolio Technical Briefing

> **Project:** Job Digest Agent (Autonomous Career Intelligence Pipeline)  
> **Candidate:** B.Tech Computer Science & Engineering (Batch 2027)  
> **Status:** Production v1.0.0 &bull; 162 Automated Tests &bull; 100% Green Test Suite  
> **Target Roles:** Software Engineer, Backend Engineer, Distributed Systems Engineer (Internship & Full-Time Fresher)

---

## 1. Executive Summary

The **Job Digest Agent** is an autonomous, production-grade career discovery pipeline built to solve real-world signal-to-noise problems in early-career tech hiring. Built by a final-year B.Tech CSE student (Batch 2027), the agent autonomously aggregates, cleans, deduplicates, scores, and delivers opportunities across two immediate priority tracks:
1. **Internships & Apprenticeships** (3 to 6-month industry immersion with competitive stipends)
2. **Full-Time Fresher Software Roles** (GET, Associate Software Engineer, Junior Backend Engineer requiring 0–1 years experience)

Operating strictly within an ethical, zero-scraping charter, the agent queries 8 permitted ATS and search APIs, eliminates senior/lead experience traps, evaluates roles with a deterministic 10-point scoring rubric, delivers twice-daily digests to Telegram and Email (08:00 AM & 07:00 PM IST), and sends immediate high-priority alerts for urgent roles closing in $\le 4$ hours.

---

## 2. Key Architectural Highlights & Engineering Decisions

### 1. Multi-Source Fault Isolation
- Integrates 8 distinct sources: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Adzuna, Remotive, and SSL IMAP Email.
- Each source adapter runs inside an isolated fault domain. Network timeouts, rate limits, or schema changes in one source are logged to `source_runs` but never terminate the pipeline. Remaining sources complete normally.

### 2. Normalization & Anti-Trap Text Mining
- Strips HTML artifacts, canonicalizes geographic locations (e.g. *Calcutta &rarr; Kolkata*, *Gurgaon &rarr; Gurugram*), and strips marketing tracking parameters (UTMs, ref tokens).
- Regex extractors with strict word-boundary matching ensure single-letter languages like **C** and short tokens like **Go** are never mistakenly matched inside ordinary English words like *CSS*, *Google*, or *Ongoing*.

### 3. SHA-256 Deduplication & 48-Hour Freshness
- Strips legal corporate suffixes (*Inc.*, *Pvt. Ltd.*, *Corporation*) to create canonical company names.
- Computes deterministic SHA-256 fingerprints `sha256(company | title | location)` stored in PostgreSQL to eliminate duplicate alerts across aggregators and company boards.

### 4. Deterministic 10-Point Scoring Algorithm
- Eliminates experience bloat via hard filters (senior/staff/lead exclusion, experience $> 2$ years filtered, batch year verified).
- Evaluates surviving postings across:
  - **Skills Overlap (4.0 pts):** Python, FastAPI, PostgreSQL, React, Linux, Docker, REST APIs.
  - **Role Match (3.0 pts):** Software Engineer, Backend Developer, Full Stack Engineer.
  - **Level Match (2.0 pts):** Internships and 0-year fresher roles receive full points.
  - **Location Match (1.0 pt):** Preferred metros (Delhi NCR, Bengaluru, Mumbai, Pune, Kolkata, Remote).

### 5. Delivery Resilience & Fast-Track Urgency
- Dispatched twice daily (08:00 AM & 07:00 PM IST) across two independent channels: Telegram Bot API and SMTP Email (Port 587 STARTTLS).
- Instant urgent dispatcher bypasses scheduled batch windows for postings with deadlines closing in $\le 4$ hours.
- Telegram message chunker splits payloads at 4,000 characters along paragraph boundaries to prevent Markdown link truncation.

### 6. Single-User Private Dashboard & Security Hardening
- Built with FastAPI, Jinja2, and Argon2id password hashing with HMAC-SHA256 session cookies and IP rate limiting.
- Protected by enterprise HTTP security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) and search engine blocking (`X-Robots-Tag: noindex, nofollow`, `/robots.txt: Disallow: /`).
- Features a **⚡ Check & Notify Now** button for on-demand execution, profile versioning with validation on save, and PWA mobile installation.

### 7. Semantic Showcase Site & Anti-Slop Discipline
- Public portfolio showcase compiled statically into `dist/` via custom Jinja2 builder (`site/build.py`).
- Strict semantic SEO: exactly one `<h1>` per page, unique titles and descriptions, self-referential canonical tags, and Schema.org JSON-LD structured data (`SoftwareApplication`, `WebSite`, `BreadcrumbList`).
- Zero JavaScript, zero source maps, ~6 KB unminified stylesheet, and zero raw emoji icons (all semantic inline SVGs).
- Air-gapped privacy guarantee: zero personal candidate profiles, private digests, or applicant notes are ever exposed to the public site.

---

## 3. Technology Stack Summary

| Layer | Technologies Used |
|---|---|
| **Backend & Core Engine** | Python 3.12, Pydantic v2, SQLAlchemy 2.0, PostgreSQL (Supabase pooler), `httpx` async |
| **Web Framework & Auth** | FastAPI, Starlette, Jinja2, Argon2-cffi, itsdangerous |
| **Delivery & Automation** | Telegram Bot API, SMTP (STARTTLS), IMAP SSL, APScheduler, GitHub Actions |
| **Public Showcase & SEO** | Static Jinja2, Schema.org JSON-LD, XML Sitemap, Sitemaps 0.9, robots.txt, llms.txt |
| **Visuals & Assets** | Hand-crafted SVG diagrams, Pillow (1200x630 OG image generation) |
| **Testing & Quality** | Pytest, pytest-asyncio, BeautifulSoup4, Pillow, PyYAML (162 tests passing) |
| **Deployment & Infra** | Docker (non-root `appuser`), Render Blueprint, GitHub Actions CI/CD, GitHub Pages |

---

## 4. Key Metrics & Verification

- **162 Automated Tests:** 100% green across all 21 development sessions.
- **8 Permitted Sources:** Ingested in parallel with individual fault isolation.
- **0 Scraping Traps:** 100% compliant with platform terms of service.
- **0 Bytes JS in Showcase:** Instant static loading with zero console errors.
- **100% Air Gap:** Personal candidate data completely isolated from the public domain.
