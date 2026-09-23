PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS fact_run_semantic_context (
    run_id TEXT PRIMARY KEY
        REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    context_kind TEXT NOT NULL,
    semantic_context_json TEXT NOT NULL DEFAULT '{}',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
