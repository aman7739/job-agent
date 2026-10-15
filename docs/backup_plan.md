# Database Backup & Disaster Recovery Plan

> **Scope:** Candidate profile versions, application statuses (`saved`, `applied`, `not_interested`), digest history, and job index.

---

## 1. Implemented Logical Backups (`scripts/backup_db.py`)

The repository includes a dedicated database export utility:

```bash
python scripts/backup_db.py
```

### What is Captured
The script exports critical tables into a timestamped JSON snapshot (`backups/backup_YYYYMMDD_HHMMSS.json`):
- **`user_profiles`**: All revisions of the profile configuration, including the currently active version.
- **`seen_jobs`**: Fingerprints, canonical URLs, application state (`saved`, `applied`, `not_interested`), notes, and audit timestamps.
- **`jobs`**: Titles, companies, extracted skills, scores, and track flags (internship / fresher).
- **`digests`**: Historical digest logs, channel delivery statuses, and source error counters.

---

## 2. Disaster Recovery & Restoration Procedure

If the database is reset or needs to be reseeded:

1. **Re-create Schema:**
   Apply [`database/schema.sql`](../database/schema.sql) against the target PostgreSQL instance.

2. **Restore Application State from JSON Backup:**
   Execute a restore script targeting your latest backup file:

   ```python
   import json
   from job_digest.db import get_db_session
   from sqlalchemy import text

   with open("backups/latest_backup.json") as f:
       data = json.load(f)

   with get_db_session() as session:
       for s in data["seen_jobs"]:
           session.execute(
               text("""
                   INSERT INTO seen_jobs (fingerprint, canonical_url, status, applied_at, saved_at, notes)
                   VALUES (:fp, :url, :status, :applied_at, :saved_at, :notes)
                   ON CONFLICT (fingerprint) DO NOTHING
               """),
               {
                   "fp": s["fingerprint"],
                   "url": s["canonical_url"],
                   "status": s["status"],
                   "applied_at": s["applied_at"],
                   "saved_at": s["saved_at"],
                   "notes": s["notes"],
               },
           )
       session.commit()
   ```

3. **Verify Pipeline Resumption:**
   The deduplication engine reads existing fingerprints from `seen_jobs`, preventing duplicate notifications for previously tracked opportunities.

---

## 3. Managed Cloud Infrastructure (Neon Serverless PostgreSQL)

At the cloud infrastructure level:
- Neon provides automated storage snapshots and continuous write-ahead logging (WAL).
- Instant point-in-time branch creation allows spinning up an isolated database branch from any point in the past without taking the production database offline.
