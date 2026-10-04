# Job Digest Agent &bull; Operational Runbook & Maintenance Guide

This operational runbook provides daily usage guidelines, administrative procedures, failure troubleshooting, and maintenance workflows for the Job Digest Agent.

---

## 1. System Overview & Architecture Topology

The Job Digest Agent operates across three distinct, decoupled execution environments:

```
+-------------------------------------------------------------------------+
|                           GitHub Actions (Cron)                         |
|   - Runs twice daily at 08:00 AM & 07:00 PM IST (30 2,13 * * * UTC)     |
|   - Executes fault-isolated crawl across 8 permitted sources            |
|   - Normalizes, deduplicates (SHA-256), and scores (10-pt algorithm)    |
|   - Dispatches Telegram & SMTP Email digests                            |
|   - Writes jobs & metrics directly to Supabase PostgreSQL               |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|                        Supabase PostgreSQL (Database)                   |
|   - Connection pooler on port 6543 (IPv4 compatible)                    |
|   - Tables: raw_jobs, seen_jobs, source_runs, user_profiles             |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|                          Render.com (Web Dashboard)                     |
|   - FastAPI application running in Docker container (non-root appuser)  |
|   - Single-user Argon2id login with encrypted HMAC session cookie       |
|   - Real-time job review, status tracker, profile editor, Run-Now button|
|   - Kept awake 24/7 via free UptimeRobot pings to /health               |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|                        GitHub Pages (Public Showcase)                   |
|   - Static HTML compiled by site/build.py into dist/                    |
|   - Deployed on push to main via .github/workflows/pages.yml            |
|   - Air-gapped: zero personal profile or private digest data exposed    |
+-------------------------------------------------------------------------+
```

---

## 2. Daily Workflow for Candidate

### 08:00 AM IST & 07:00 PM IST — Scheduled Digests
1. Check your **Telegram channel / bot chat** or **notifications email inbox** for the fresh digest.
2. The digest partitions opportunities into two active tracks:
   - **🎓 Internships & Apprenticeships:** High-stipend 3–6 month technical internships.
   - **🚀 Full-Time Fresher Roles:** GET, Associate Software Engineer, and Junior Backend roles.
3. Review matches scored $\ge 7.0 / 10$ with highlighted skill overlaps.
4. Click direct employer links to review job descriptions and submit applications.

### Urgent Deadline Alerts ($\le 4$ Hours Remaining)
- If a high-scoring posting is discovered with a closing window $\le 4$ hours, an immediate high-priority alert is dispatched with an amber badge: `🚨 URGENT APPLICATION DEADLINE`.
- Prioritize these submissions immediately before application portals close.

### On-Demand Discovery (*⚡ Check & Notify Now*)
- If applying outside scheduled hours, open the private web dashboard and click **⚡ Check & Notify Now** in the header.
- The system executes an immediate full-pipeline sweep across all 8 sources and sends you an instant delivery update.

---

## 3. Web Dashboard Operations

### Managing Job Statuses
- Navigate to the **Job History** (`/history`) tab.
- Click action buttons on individual job cards:
  - **Saved:** Bookmark for weekend deep-dives or referral hunting.
  - **Applied:** Marks the role as submitted. Automatically increments your weekly counter: `🎯 Applied this week: X`.
  - **Dismiss:** Flags as `not_interested` so it never clutters future views.
- Add interview notes and recruiter contacts directly in the notes field.

### Editing Candidate Profile & Tech Stack (`/settings`)
- In the dashboard, click **Settings**.
- Modify preferred roles, cities, skills, or target batch year.
- Add noisy companies to the **Company Blocklist** (case-insensitive substring matching).
- Saving automatically validates the configuration using Pydantic, increments the database version in `user_profiles`, and applies changes on the very next run.
- If an invalid profile is submitted, the system rolls back to the last known good configuration.

### Monitoring Source Health (`/sources`)
- Inspect real-time status across all 8 adapters:
  - 🟢 **Healthy:** Successful crawl within the last 24 hours.
  - 🟡 **Warning:** Zero postings returned, but no network/API errors.
  - 🔴 **Error:** API timeout, rate limit, or schema change. Detailed error trace is logged.

### Manual Job Entry (`/jobs/add`)
- If you discover a role from a WhatsApp group, college placement cell, or direct recruiter message, enter it manually at `/jobs/add`.
- The system automatically computes the SHA-256 fingerprint, matches candidate skills, calculates the 10-point score, and saves it to your database history.

---

## 4. Disaster Recovery & Database Snapshots

### Creating a Database Backup
Run the JSON snapshot utility locally or in CI:
```bash
python scripts/backup_db.py
```
This writes a complete, portable timestamped snapshot to `backups/db_backup_YYYYMMDD_HHMMSS.json` containing:
- All `user_profiles` version records.
- All `seen_jobs` records with statuses, timestamps, and candidate notes.
- Summary telemetry from `source_runs`.

### Restoring from Backup
In the event of database migration or migration to another Supabase instance:
```bash
python scripts/backup_db.py --restore backups/db_backup_20261004_120000.json
```

---

## 5. Troubleshooting & Failure Modes

| Symptom | Root Cause | Remediation Procedure |
|---|---|---|
| Telegram digest received, but no email | SMTP credentials expired or Gmail App Password revoked | Check `SMTP_USER` and `SMTP_PASSWORD` in `.env` / GitHub Secrets. Telegram fault isolation ensures jobs were delivered without data loss. |
| One source shows 🔴 Error in `/sources` | ATS provider changed public endpoint or rate limit | Inspect error log in `/sources`. Other 7 sources continue running unaffected. Swap or patch the specific adapter in `job_digest/sources/` without touching the rest of the pipeline. |
| Render dashboard slow to load on first visit | Free tier web service hibernated after 15m idle | Confirm UptimeRobot is pinging `https://<render-url>/health` every 10 minutes. Status must return HTTP 200 with DB ping `true`. |
| Urgent job alert not triggered | Job description did not include explicit deadline timestamp | Deadlines must be stated in text/schema to be detected. Unstated deadlines are processed normally in the 08:00 AM / 07:00 PM batch windows. |
| Corrupted profile saved in `/settings` | Validation error caught on save | Pydantic blocks corrupted configurations. The database falls back to the previous monotonic version stored in `user_profiles`. |

---

## 6. Maintenance Calendar

- **Weekly:** Check `/sources` dashboard to confirm all 8 adapters have green health indicators.
- **Bi-Weekly:** Run `python scripts/backup_db.py` to create a local JSON disaster recovery snapshot.
- **Monthly:** Review company blocklist in `/settings` to purge outdated recruitment agencies or consulting shops.
