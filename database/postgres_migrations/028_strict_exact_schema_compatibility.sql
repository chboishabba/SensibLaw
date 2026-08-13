BEGIN;

-- Some retained databases contain earlier generic semantic_owner_stream and
-- semantic_delta_admission tables with incompatible contracts.  Keep strict
-- exact evidence isolated rather than mutating those already-applied tables.
CREATE TABLE IF NOT EXISTS execution.semantic_strict_owner_stream (
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    owner_ref TEXT NOT NULL,
    current_revision BIGINT NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
    PRIMARY KEY (run_ref, owner_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_strict_delta_admission (
    delta_ref TEXT PRIMARY KEY REFERENCES execution.semantic_immutable_delta(delta_ref) ON DELETE RESTRICT,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    owner_ref TEXT NOT NULL,
    resulting_revision BIGINT NOT NULL CHECK (resulting_revision > 0),
    prior_revision BIGINT NOT NULL CHECK (prior_revision >= 0),
    fence_token TEXT NOT NULL,
    lease_epoch BIGINT NOT NULL DEFAULT 0,
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, owner_ref, resulting_revision)
);

CREATE INDEX IF NOT EXISTS semantic_strict_owner_stream_run_idx
    ON execution.semantic_strict_owner_stream (run_ref, owner_ref);

COMMIT;
