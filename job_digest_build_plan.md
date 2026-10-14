# Job Digest Agent: Source Expansion Build Plan

_Personal single-user project | Plan date: 14 Oct 2026_

## 1. Goal and scope

Increase the number of relevant fresher and internship jobs reaching the daily digest, without adding noise. The agent is built for one user (AK) only, so every decision favours low effort, low noise and low risk over audience-facing polish.

- Target: B.Tech CSE 2027 batch, internships/apprenticeships and full-time fresher roles (0-2 years).
- Preferred places: Noida, Delhi NCR, Gurugram, Kolkata, Mumbai, Pune, Bengaluru, Indore, Remote (India).
- Goal: move toward a product-based company role, so company-board coverage matters most.
- Existing 8 sources stay as they are: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Adzuna, Remotive, IMAP email alerts.
- Matching rules and the 08:00 / 19:00 IST schedule are not changed by this plan.

## 2. Rules that stay fixed

- No scraping of LinkedIn, Naukri or Indeed. Official APIs, public ATS feeds and personal email alerts only.
- Every new adapter uses the existing JobSource protocol, the 45 s timeout and fault isolation.
- No auto-applying. The agent finds and scores; AK clicks and applies.
- No secrets in git or .env.example. API keys go in Render environment variables.
- Prefer 3 or 4 good sources over 10 mediocre ones; extra feeds only add digest noise.

## 3. Cleanup before building (small, do first or alongside)

| Item | Problem | Fix |
|---|---|---|
| Doc inconsistencies | ADR 017 says 166 tests / 17 ADRs, file now has 180 tests / 20 ADRs. Supabase and Neon both named as the DB. ADR 011 says GitHub Actions runs crawls, later gotcha moves scheduling in-app. | Update counts, state one DB (Neon), mark ADR 011 as superseded by the in-app scheduler. |
| Seniority filter | Substring match on manager, lead, head, staff can drop good roles such as 'Product Manager Intern' or 'Lead Generation'. | Use word-boundary regex. Do not auto-reject when the title also contains intern, trainee or associate. |
| Scheduler misfire | In-app APScheduler on a free Render container can miss a run if the container restarts at 08:00 or 19:00. | Set misfire_grace_time and add a catch-up check: if last digest is older than about 14 h, run now. |
| Test vs production DB | Tests use SQLite; production uses Postgres with JSONB and ARRAY columns. | Add a few integration tests against a Postgres container. |

## 4. Build order

| Stage | What | Why this order |
|---|---|---|
| 1 | Slug-checking script, then expand Greenhouse / Lever / Ashby with Indian product companies and startups | Cheapest change, highest expected yield; reuses existing adapters. |
| 2 | Improve Adzuna query groups; activate missing email alerts on platforms already whitelisted | No new code paths, only configuration and queries. |
| 3 | Add ONE aggregator: Jooble or Careerjet | Adds India volume next to Adzuna; trial one, keep it only if it adds eligible jobs. |
| 4 | Lightweight per-source 7-day metric using a job_sightings table | Shows which sources are worth keeping; small /sources addition. |
| 5 | Optional: one remote feed, extra ATS adapters, NCS / AICTE / IndianAPI checks | Only if the metric or a specific target employer justifies it. |

## 5. Stage 1: slug checker and ATS expansion

Goal: grow sources.yaml with verified company boards. Do not assume which ATS a company uses; verify each one.

1. Make a plain list of target companies (Indian product companies, startups, and Indian offices of global firms).
2. For each company, try its likely slug against the Greenhouse, Lever and Ashby public endpoints already used by the adapters.
3. A board counts as valid only if the response parses as the expected structure (for example a jobs list) and the company name or job locations make sense. An HTTP 200 alone is not proof.
4. Record per company: name, ATS, slug, status (valid / not found / empty), job count, India job count, checked-at date.
5. Add only valid boards that have India or Remote-India roles to sources.yaml.
6. Be polite: reuse the 0.3 s delay between requests and the JobDigestAgent User-Agent.
7. Re-run the checker monthly, since boards appear and disappear.

Output of the script: a CSV or YAML report plus a ready-to-paste block for sources.yaml. Companies that use another ATS (for example Workday, Recruitee, Personio, Teamtailor) are listed separately so you can decide later whether an extra adapter is worth it.

## 6. Stage 2: Adzuna queries and email alerts

Adzuna currently runs 5 role query groups. Split and extend them so fresher titles are not missed:

- Python Developer (fresher / entry level)
- Backend Developer (fresher)
- Software Engineer Trainee
- Graduate Engineer Trainee
- AI / ML Intern
- Software Development Intern / Full Stack Intern
- Keep results_per_page and the 0.5 s delay; watch the API quota before adding more groups.

Email alerts (Mailbox A, read-only IMAP): create saved searches on platforms that are already on the whitelist but not yet sending alerts. Suggested alert themes per platform:

- Internshala: internships for CSE, Python, web development, ML.
- Unstop: internships, graduate hiring programs, company challenges.
- Naukri / LinkedIn / Indeed: fresher and internship alerts for Python, backend, full stack, AI/ML in the preferred cities.
- Instahyre, Wellfound, Cutshort, Foundit, Glassdoor, Hirist: one fresher/intern alert each.
- Company career alerts (for example big product firms with India offices) if their sender domain can be whitelisted safely.

## 7. Stage 3: one aggregator (Jooble or Careerjet)

- Both are API-key based and offer India search. Check current terms, free quota, freshness and attribution rules before building.
- Pick one first; run it for 1 to 2 weeks and compare against the Adzuna baseline: how many extra eligible jobs does it add that no other source found?
- Implement as a normal adapter (httpx, JobSource protocol, 45 s timeout), feeding the existing normalize, dedup, match and digest steps unchanged.
- Keep it only if it adds meaningful incremental eligible jobs; otherwise remove it.
- IndianAPI Jobs API: evaluate only after confirming where its data comes from. If it is built on scraped LinkedIn / Naukri / Indeed data, it conflicts with the project's compliance rule.

## 8. Stage 4: lightweight metric (job_sightings)

Why a new table: the jobs table stores one source per job, and dedup drops duplicates before persisting, so it cannot tell you which sources found the same job. Record each sighting when it happens.

```sql
CREATE TABLE IF NOT EXISTS job_sightings (
    id BIGSERIAL PRIMARY KEY,
    fingerprint VARCHAR(64) NOT NULL REFERENCES seen_jobs(fingerprint)
        ON DELETE CASCADE,
    source VARCHAR(64) NOT NULL,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sightings_source
    ON job_sightings(source, seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_sightings_fp
    ON job_sightings(fingerprint);
```

- Write one sighting per source per job in the dedup step, next to fingerprinting.
- Primary source = earliest sighting. All contributing sources stay queryable.
- 7-day view on /sources, computed at query time from timestamps: jobs per source that reached the digest, and jobs that only that source found.
- Application yield comes free by joining to seen_jobs.applied_at and saved_at. Treat it as a long-run signal; it is noisy at first.
- Digest has a 40-item cap: later, also record which fingerprints actually made the final 40.
- Migration: auto-migrate in db.py with CREATE TABLE IF NOT EXISTS. SQLite does not support ADD COLUMN IF NOT EXISTS, so guard column additions in code and test both engines.

| Metric | Meaning | Priority |
|---|---|---|
| Jobs in digest per source (7 days) | Which sources actually feed the digest | Start here |
| Incremental jobs | Eligible jobs only this source found | Start here |
| Eligibility yield | Eligible unique / normalized unique jobs | Later |
| Application yield | Discovered jobs that led to an application | Long-run |

## 9. Stage 5: optional additions

| Option | Verdict |
|---|---|
| One remote feed (Arbeitnow, Himalayas, We Work Remotely, RemoteOK, Jobicy) | At most one, and only after the metric shows a gap. Mostly global and senior-leaning; expect low yield like Remotive (10 jobs). |
| JSearch (RapidAPI) | Small free tier; use for a few targeted queries only if needed. |
| Recruitee / Personio / Teamtailor / BambooHR adapters | Build only for specific target employers that use them. |
| Workday career sites | Unofficial JSON endpoints; check each company's terms first. Low priority. |
| NCS and AICTE Internship Portal | No public API known. Look for a feed or alerts; AICTE overlaps with Internshala. |
| Hacker News 'Who is hiring' | Low yield for freshers. Skip unless bored. |

## 10. Files needed to start coding

Upload the repository ZIP, or at least these files, so changes match the real function signatures:

- job_digest/sources/runner.py, job_digest/sources/base.py, job_digest/sources/adzuna.py
- job_digest/run.py, job_digest/dedup.py, job_digest/models.py, job_digest/match.py, job_digest/digest.py
- job_digest/web.py and job_digest/templates/web/sources.html
- database/schema.sql, sources.yaml
- tests/test_run.py

The slug-checking script needs no uploads, only the list of company names you are interested in.

## 11. Done checklist

- [ ] Doc inconsistencies fixed (test count, ADR count, DB name, ADR 011 superseded)
- [ ] Seniority filter uses word boundaries
- [ ] Scheduler misfire grace and catch-up run added
- [ ] Slug checker written and run; verified boards added to sources.yaml
- [ ] Adzuna query groups expanded
- [ ] Missing email alerts activated
- [ ] One aggregator (Jooble or Careerjet) trialled and kept or dropped
- [ ] job_sightings table and 7-day per-source view on /sources
- [ ] All tests still passing; production schedule unchanged
