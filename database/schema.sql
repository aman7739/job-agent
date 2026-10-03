-- Job Digest Agent: PostgreSQL Schema (Supabase)

CREATE TABLE IF NOT EXISTS job_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,
    source_type VARCHAR(32) NOT NULL, -- 'ats', 'search_api', 'feed', 'imap', 'manual'
    config JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seen_jobs (
    fingerprint VARCHAR(64) PRIMARY KEY, -- sha256(company | title | location)
    canonical_url TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notified_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'seen' -- 'seen', 'saved', 'applied', 'not_interested'
);
CREATE INDEX IF NOT EXISTS idx_seen_jobs_canonical_url ON seen_jobs(canonical_url);
CREATE INDEX IF NOT EXISTS idx_seen_jobs_status ON seen_jobs(status);

CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    fingerprint VARCHAR(64) UNIQUE NOT NULL REFERENCES seen_jobs(fingerprint) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    canonical_url TEXT NOT NULL,
    description_text TEXT,
    posted_at TIMESTAMPTZ,
    source VARCHAR(64) NOT NULL,
    is_intern BOOLEAN NOT NULL DEFAULT FALSE,
    is_apprentice BOOLEAN NOT NULL DEFAULT FALSE,
    min_years NUMERIC(3, 1),
    salary_lpa NUMERIC(6, 2),
    stipend NUMERIC(8, 2),
    batch_years INT[],
    matched_skills TEXT[],
    missing_skills TEXT[],
    score NUMERIC(4, 2),
    score_breakdown JSONB DEFAULT '{}'::jsonb,
    raw_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_intern ON jobs(is_intern, is_apprentice);

CREATE TABLE IF NOT EXISTS digests (
    id BIGSERIAL PRIMARY KEY,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_jobs INT NOT NULL DEFAULT 0,
    internships_count INT NOT NULL DEFAULT 0,
    fulltime_count INT NOT NULL DEFAULT 0,
    channels_notified TEXT[] NOT NULL DEFAULT '{}',
    failed_sources TEXT[] DEFAULT '{}',
    content_html TEXT,
    content_text TEXT
);

CREATE TABLE IF NOT EXISTS source_runs (
    id BIGSERIAL PRIMARY KEY,
    source_name VARCHAR(64) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    jobs_found INT NOT NULL DEFAULT 0,
    jobs_new INT NOT NULL DEFAULT 0,
    is_success BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_source_runs_source ON source_runs(source_name, started_at DESC);

CREATE TABLE IF NOT EXISTS email_messages (
    message_id VARCHAR(255) PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    subject TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    jobs_extracted INT NOT NULL DEFAULT 0
);
