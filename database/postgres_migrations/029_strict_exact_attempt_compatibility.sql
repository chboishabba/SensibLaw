BEGIN;

CREATE TABLE IF NOT EXISTS execution.semantic_strict_job_attempt (
    attempt_ref TEXT PRIMARY KEY,
    job_ref TEXT NOT NULL REFERENCES execution.semantic_closure_job(job_ref) ON DELETE RESTRICT,
    worker_ref TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    lease_epoch BIGINT NOT NULL CHECK (lease_epoch > 0),
    input_sha256 BYTEA NOT NULL,
    output_sha256 BYTEA,
    state TEXT NOT NULL CHECK (state IN ('leased', 'completed', 'stale', 'failed')),
    worker_pid BIGINT,
    backend_pid INTEGER,
    renewal_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS semantic_strict_job_attempt_job_idx
    ON execution.semantic_strict_job_attempt (job_ref, lease_epoch);

COMMIT;
