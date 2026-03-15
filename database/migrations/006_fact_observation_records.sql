CREATE TABLE IF NOT EXISTS fact_observations (
    observation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    statement_id TEXT NOT NULL REFERENCES fact_statements(statement_id) ON DELETE CASCADE,
    excerpt_id TEXT REFERENCES fact_excerpts(excerpt_id) ON DELETE SET NULL,
    source_id TEXT REFERENCES fact_sources(source_id) ON DELETE SET NULL,
    observation_order INTEGER NOT NULL DEFAULT 1,
    predicate_key TEXT NOT NULL,
    predicate_family TEXT NOT NULL,
    object_text TEXT NOT NULL,
    object_type TEXT,
    object_ref TEXT,
    subject_text TEXT,
    observation_status TEXT NOT NULL DEFAULT 'candidate',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fact_observations_run_id
    ON fact_observations(run_id);

CREATE INDEX IF NOT EXISTS idx_fact_observations_statement_id
    ON fact_observations(statement_id);

CREATE INDEX IF NOT EXISTS idx_fact_observations_predicate_key
    ON fact_observations(predicate_key);
