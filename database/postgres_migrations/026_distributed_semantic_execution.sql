BEGIN;

-- Execution-only coordination for strict acceptance.  These tables deliberately
-- contain no semantic interpretation: the canonical owner remains the reducer.
CREATE TABLE IF NOT EXISTS execution.semantic_run (
    run_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    authority_backend TEXT NOT NULL,
    lifecycle TEXT NOT NULL,
    kernel_key TEXT,
    kernel_contract TEXT,
    worker_budget INTEGER,
    lifecycle_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner_revision BIGINT NOT NULL DEFAULT 0 CHECK (owner_revision >= 0),
    sealed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution.semantic_owner_stream (
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    owner_ref TEXT NOT NULL,
    current_revision BIGINT NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
    PRIMARY KEY (run_ref, owner_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_closure_job (
    job_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    owner_ref TEXT NOT NULL,
    input_revision BIGINT NOT NULL CHECK (input_revision >= 0),
    input_manifest JSONB NOT NULL,
    input_sha256 BYTEA NOT NULL,
    state TEXT NOT NULL DEFAULT 'open'
        CHECK (state IN ('open', 'leased', 'completed', 'failed')),
    lease_owner TEXT,
    lease_token TEXT,
    lease_expires_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, job_ref)
);

CREATE INDEX IF NOT EXISTS semantic_closure_job_ready_idx
    ON execution.semantic_closure_job (run_ref, state, lease_expires_at, input_revision, job_ref);

CREATE TABLE IF NOT EXISTS execution.semantic_job_attempt (
    attempt_ref TEXT PRIMARY KEY,
    job_ref TEXT NOT NULL REFERENCES execution.semantic_closure_job(job_ref) ON DELETE RESTRICT,
    worker_ref TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    input_sha256 BYTEA NOT NULL,
    output_sha256 BYTEA,
    state TEXT NOT NULL CHECK (state IN ('leased', 'completed', 'stale', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS execution.semantic_immutable_delta (
    delta_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    owner_ref TEXT NOT NULL,
    resulting_revision BIGINT NOT NULL CHECK (resulting_revision > 0),
    prior_revision BIGINT NOT NULL CHECK (prior_revision >= 0),
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    job_ref TEXT NOT NULL REFERENCES execution.semantic_closure_job(job_ref) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, owner_ref, resulting_revision)
);

CREATE TABLE IF NOT EXISTS execution.semantic_delta_admission (
    delta_ref TEXT PRIMARY KEY REFERENCES execution.semantic_immutable_delta(delta_ref) ON DELETE RESTRICT,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    owner_ref TEXT NOT NULL,
    resulting_revision BIGINT NOT NULL CHECK (resulting_revision > 0),
    fence_token TEXT NOT NULL,
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, owner_ref, resulting_revision)
);

CREATE TABLE IF NOT EXISTS execution.semantic_finalization_checkpoint (
    checkpoint_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    owner_ref TEXT NOT NULL,
    cursor_revision BIGINT NOT NULL CHECK (cursor_revision >= 0),
    sealed_manifest JSONB NOT NULL,
    manifest_sha256 BYTEA NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('sealed', 'committed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, owner_ref, cursor_revision)
);

CREATE TABLE IF NOT EXISTS execution.semantic_execution_receipt (
    receipt_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, document_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_publication (
    publication_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('staged', 'committed')),
    manifest JSONB NOT NULL,
    manifest_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, document_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_kernel_registration (
    run_ref TEXT PRIMARY KEY REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    kernel_key TEXT NOT NULL,
    kernel_contract TEXT NOT NULL,
    worker_budget INTEGER NOT NULL CHECK (worker_budget > 0),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS execution.semantic_owner_revision_history (
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    owner_ref TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 0),
    delta_ref TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_ref, owner_ref, revision)
);

CREATE TABLE IF NOT EXISTS execution.semantic_lifecycle_event (
    event_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    lifecycle TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE execution.semantic_run
    ADD COLUMN IF NOT EXISTS kernel_key TEXT,
    ADD COLUMN IF NOT EXISTS kernel_contract TEXT,
    ADD COLUMN IF NOT EXISTS worker_budget INTEGER,
    ADD COLUMN IF NOT EXISTS lifecycle_history JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMIT;
