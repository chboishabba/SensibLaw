BEGIN;

-- Execution-only, typed staging for work-conserving document persistence.
-- Rows in this relation have no semantic publication authority.  Authority is
-- acquired only when the ordered document savepoint merges a closed stage into
-- the normalized algebra/evidence/resolution tables and publishes the completed
-- operational build.
CREATE UNLOGGED TABLE IF NOT EXISTS execution.document_persistence_stage (
    stage_ref TEXT NOT NULL,
    document_ref TEXT NOT NULL,
    build_key_sha256 TEXT NOT NULL,
    lane_ref TEXT NOT NULL CHECK (lane_ref IN ('token', 'annotation', 'graph', 'resolution', 'binding')),
    row_kind_ref TEXT NOT NULL,
    partition_no INTEGER NOT NULL CHECK (partition_no >= 0),
    ordinal BIGINT NOT NULL CHECK (ordinal >= 0),
    text_01 TEXT,
    text_02 TEXT,
    text_03 TEXT,
    text_04 TEXT,
    text_05 TEXT,
    text_06 TEXT,
    text_07 TEXT,
    text_08 TEXT,
    text_09 TEXT,
    text_10 TEXT,
    text_11 TEXT,
    text_12 TEXT,
    int_01 BIGINT,
    int_02 BIGINT,
    int_03 BIGINT,
    int_04 BIGINT,
    int_05 BIGINT,
    int_06 BIGINT,
    bytea_01 BYTEA,
    bytea_02 BYTEA,
    PRIMARY KEY (stage_ref, lane_ref, row_kind_ref, ordinal)
);

CREATE INDEX IF NOT EXISTS document_persistence_stage_kind_idx
    ON execution.document_persistence_stage (stage_ref, row_kind_ref);

CREATE INDEX IF NOT EXISTS document_persistence_stage_document_idx
    ON execution.document_persistence_stage (document_ref, build_key_sha256);

CREATE TABLE IF NOT EXISTS execution.document_persistence_run (
    stage_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    build_key_sha256 TEXT NOT NULL,
    family_ref TEXT NOT NULL,
    state_ref TEXT NOT NULL
        CHECK (state_ref IN ('staging', 'staged', 'publishing', 'published', 'failed')),
    worker_budget INTEGER NOT NULL CHECK (worker_budget >= 1),
    lane_count INTEGER NOT NULL DEFAULT 0 CHECK (lane_count >= 0),
    row_count BIGINT NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    statement_count INTEGER NOT NULL DEFAULT 0 CHECK (statement_count >= 0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    staged_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    failure_type_ref TEXT,
    failure_message TEXT
);

CREATE INDEX IF NOT EXISTS document_persistence_run_document_idx
    ON execution.document_persistence_run (document_ref, build_key_sha256, state_ref);

CREATE TABLE IF NOT EXISTS execution.document_persistence_lane (
    stage_ref TEXT NOT NULL REFERENCES execution.document_persistence_run(stage_ref)
        ON DELETE CASCADE,
    lane_ref TEXT NOT NULL,
    partition_no INTEGER NOT NULL CHECK (partition_no >= 0),
    state_ref TEXT NOT NULL CHECK (state_ref IN ('staging', 'staged', 'failed')),
    backend_pid INTEGER,
    worker_pid BIGINT,
    row_count BIGINT NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    byte_count BIGINT NOT NULL DEFAULT 0 CHECK (byte_count >= 0),
    elapsed_ms BIGINT NOT NULL DEFAULT 0 CHECK (elapsed_ms >= 0),
    client_user_cpu_ms BIGINT NOT NULL DEFAULT 0 CHECK (client_user_cpu_ms >= 0),
    client_system_cpu_ms BIGINT NOT NULL DEFAULT 0 CHECK (client_system_cpu_ms >= 0),
    wait_event_type_ref TEXT,
    wait_event_ref TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    PRIMARY KEY (stage_ref, lane_ref, partition_no)
);

COMMENT ON TABLE execution.document_persistence_stage IS
    'Typed, unlogged, execution-only rows. Never semantic authority.';
COMMENT ON TABLE execution.document_persistence_run IS
    'Document persistence execution receipt; publication occurs only in the ordered authority savepoint.';
COMMENT ON TABLE execution.document_persistence_lane IS
    'Per-backend COPY telemetry for work-conserving persistence lanes.';

COMMIT;
