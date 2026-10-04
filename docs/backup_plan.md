# Database Backup & Disaster Recovery Plan

> **Scope:** Candidate Profile versions, Application statuses (`saved`, `applied`, `not_interested`), digests history, and job index.

---

## 1. Automated Cloud Backups (Supabase)
Supabase provides automated physical backups on all projects:
- Daily automatic database snapshots.
- Point-in-time recovery (PITR) available on managed plans.
- Supabase dashboard: **Database → Backups** allows one-click restoration.

---

## 2. Application-Level JSON Snapshots (`scripts/backup_db.py`)
In addition to Supabase cloud backups, an application-level logical backup script is included:

```bash
python scripts/backup_db.py
```

### What is captured:
- **`user_profiles`**: All versions of the YAML profile, including the currently active configuration.
- **`seen_jobs`**: Every fingerprint ever processed, along with timestamps for `first_seen_at`, `notified_at`, `saved_at`, `applied_at`, and candidate notes.
- **`jobs`**: Metadata of recent scored jobs (title, company, score, intern/fulltime flags).
- **`digests`**: Log of all sent digests, channel deliveries, and source failure metrics.

Output is stored in `backups/backup_YYYYMMDD_HHMMSS.json`.

---

## 3. Disaster Recovery / Restoration Procedure

If the cloud database is ever accidentally wiped or a new database must be seeded:
1. Initialize the tables using `database/schema.sql`.
2. Seed the candidate profile using the latest YAML from the backup JSON or `profile.yaml`.
3. Application statuses (`seen_jobs`) can be re-populated by running a restore query:
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
                   "fp": s["fingerprint"], "url": s["canonical_url"],
                   "status": s["status"], "applied_at": s["applied_at"],
                   "saved_at": s["saved_at"], "notes": s["notes"],
               }
           )
       session.commit()
   ```
4. The agent will resume without duplicating previously seen or notified listings.
