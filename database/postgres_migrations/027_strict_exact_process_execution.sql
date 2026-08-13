BEGIN;

-- Additive control-plane evidence for strict exact execution.  Migration 026
-- remains the compatibility foundation; these columns/tables are the durable
-- authority for process workers and multi-round convergence.
ALTER TABLE execution.semantic_run
    ADD COLUMN IF NOT EXISTS build_key_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS operation_contract_ref TEXT,
    ADD COLUMN IF NOT EXISTS max_rounds INTEGER NOT NULL DEFAULT 64,
    ADD COLUMN IF NOT EXISTS round_ordinal INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS fixed_point_certificate JSONB,
    ADD COLUMN IF NOT EXISTS fixed_point_digest BYTEA,
    ADD COLUMN IF NOT EXISTS finalization_cursor JSONB,
    ADD COLUMN IF NOT EXISTS serializer_manifest JSONB,
    ADD COLUMN IF NOT EXISTS publication_manifest JSONB;

ALTER TABLE execution.semantic_closure_job
    ADD COLUMN IF NOT EXISTS build_key_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS operation_contract_ref TEXT,
    ADD COLUMN IF NOT EXISTS lease_epoch BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS expected_owner_revision BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS worker_pid BIGINT,
    ADD COLUMN IF NOT EXISTS backend_pid INTEGER,
    ADD COLUMN IF NOT EXISTS renewals INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE execution.semantic_job_attempt
    ADD COLUMN IF NOT EXISTS lease_epoch BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS worker_pid BIGINT,
    ADD COLUMN IF NOT EXISTS backend_pid INTEGER,
    ADD COLUMN IF NOT EXISTS renewal_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE execution.semantic_immutable_delta
    ADD COLUMN IF NOT EXISTS build_key_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS operation_contract_ref TEXT,
    ADD COLUMN IF NOT EXISTS lease_epoch BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS expected_owner_revision BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS execution.semantic_worker_receipt (
    receipt_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    worker_ref TEXT NOT NULL,
    worker_pid BIGINT NOT NULL,
    backend_pid INTEGER,
    application_name TEXT NOT NULL,
    leases INTEGER NOT NULL DEFAULT 0,
    renewals INTEGER NOT NULL DEFAULT 0,
    accepted INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    stale INTEGER NOT NULL DEFAULT 0,
    retries INTEGER NOT NULL DEFAULT 0,
    failures INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, worker_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_round_manifest (
    round_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    round_ordinal INTEGER NOT NULL CHECK (round_ordinal > 0),
    input_owner_revision BIGINT NOT NULL CHECK (input_owner_revision >= 0),
    output_owner_revision BIGINT,
    job_count INTEGER NOT NULL DEFAULT 0,
    delta_count INTEGER NOT NULL DEFAULT 0,
    changed_owner_count INTEGER NOT NULL DEFAULT 0,
    awakened_job_count INTEGER NOT NULL DEFAULT 0,
    manifest JSONB NOT NULL,
    manifest_sha256 BYTEA NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('open', 'committed', 'fixed_point', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, round_ordinal)
);

CREATE TABLE IF NOT EXISTS execution.semantic_finalization_cursor (
    cursor_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    owner_ref TEXT NOT NULL,
    cursor_revision BIGINT NOT NULL CHECK (cursor_revision >= 0),
    batch_ordinal INTEGER NOT NULL CHECK (batch_ordinal >= 0),
    manifest JSONB NOT NULL,
    manifest_sha256 BYTEA NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('open', 'committed')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, document_ref, owner_ref, batch_ordinal)
);

CREATE INDEX IF NOT EXISTS semantic_round_manifest_run_idx
    ON execution.semantic_round_manifest (run_ref, round_ordinal);

COMMIT;
