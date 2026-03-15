PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS fact_intake_runs (
    run_id TEXT PRIMARY KEY,
    contract_version TEXT NOT NULL,
    source_label TEXT NOT NULL,
    mary_projection_version TEXT NOT NULL,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_sources (
    source_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    source_order INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_label TEXT NOT NULL,
    source_ref TEXT,
    content_sha256 TEXT,
    provenance_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_fact_sources_run_id
    ON fact_sources(run_id, source_order);

CREATE TABLE IF NOT EXISTS fact_excerpts (
    excerpt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES fact_sources(source_id) ON DELETE CASCADE,
    excerpt_order INTEGER NOT NULL,
    excerpt_text TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    anchor_label TEXT,
    provenance_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_fact_excerpts_run_id
    ON fact_excerpts(run_id, source_id, excerpt_order);

CREATE TABLE IF NOT EXISTS fact_statements (
    statement_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    excerpt_id TEXT NOT NULL REFERENCES fact_excerpts(excerpt_id) ON DELETE CASCADE,
    statement_order INTEGER NOT NULL,
    statement_text TEXT NOT NULL,
    speaker_label TEXT,
    statement_role TEXT,
    statement_status TEXT NOT NULL DEFAULT 'captured',
    chronology_hint TEXT,
    provenance_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_fact_statements_run_id
    ON fact_statements(run_id, excerpt_id, statement_order);

CREATE TABLE IF NOT EXISTS fact_candidates (
    fact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    canonical_label TEXT,
    fact_text TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    chronology_sort_key TEXT,
    chronology_label TEXT,
    primary_statement_id TEXT REFERENCES fact_statements(statement_id) ON DELETE SET NULL,
    provenance_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_fact_candidates_run_id
    ON fact_candidates(run_id, chronology_sort_key, fact_id);

CREATE TABLE IF NOT EXISTS fact_candidate_statements (
    fact_id TEXT NOT NULL REFERENCES fact_candidates(fact_id) ON DELETE CASCADE,
    statement_id TEXT NOT NULL REFERENCES fact_statements(statement_id) ON DELETE CASCADE,
    link_kind TEXT NOT NULL DEFAULT 'supporting_statement',
    PRIMARY KEY (fact_id, statement_id)
);

CREATE TABLE IF NOT EXISTS fact_contestations (
    contestation_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL REFERENCES fact_candidates(fact_id) ON DELETE CASCADE,
    statement_id TEXT REFERENCES fact_statements(statement_id) ON DELETE SET NULL,
    contestation_status TEXT NOT NULL,
    reason_text TEXT NOT NULL,
    author TEXT,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fact_contestations_fact_id
    ON fact_contestations(fact_id, created_at);

CREATE TABLE IF NOT EXISTS fact_reviews (
    review_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL REFERENCES fact_candidates(fact_id) ON DELETE CASCADE,
    review_status TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    note TEXT,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fact_reviews_fact_id
    ON fact_reviews(fact_id, created_at);

COMMIT;
