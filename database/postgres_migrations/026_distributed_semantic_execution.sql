BEGIN;

CREATE SCHEMA IF NOT EXISTS execution;

-- One logical authority stream per semantic owner key.  Workers may compute in
-- parallel, but accepted revisions advance through this row monotonically.
CREATE TABLE IF NOT EXISTS execution.semantic_owner_stream (
    owner_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    scope_ref TEXT NOT NULL,
    factor_family TEXT NOT NULL,
    revision BIGINT NOT NULL DEFAULT 0 CHECK (revision >= 0),
    state_ref TEXT NOT NULL DEFAULT 'open'
        CHECK (state_ref IN ('open', 'finalising', 'fixed_point', 'failed')),
    dirty BOOLEAN NOT NULL DEFAULT FALSE,
    coverage_closed BOOLEAN NOT NULL DEFAULT FALSE,
    unresolved_obligation_count BIGINT NOT NULL DEFAULT 0
        CHECK (unresolved_obligation_count >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, scope_ref, factor_family)
);

CREATE TABLE IF NOT EXISTS execution.semantic_job (
    job_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    owner_ref TEXT NOT NULL
        REFERENCES execution.semantic_owner_stream(owner_ref) ON DELETE CASCADE,
    operation_contract_ref TEXT NOT NULL,
    input_manifest_ref TEXT NOT NULL,
    input_manifest_sha256 BYTEA NOT NULL,
    expected_owner_revision BIGINT NOT NULL CHECK (expected_owner_revision >= 0),
    canonical_ordinal BIGINT NOT NULL CHECK (canonical_ordinal >= 0),
    priority INTEGER NOT NULL DEFAULT 100,
    state_ref TEXT NOT NULL DEFAULT 'blocked'
        CHECK (state_ref IN (
            'blocked', 'ready', 'leased', 'completed', 'retryable', 'failed'
        )),
    not_before TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lease_owner TEXT,
    lease_epoch BIGINT NOT NULL DEFAULT 0 CHECK (lease_epoch >= 0),
    lease_expires_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_sha256 BYTEA NOT NULL,
    last_error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (owner_ref, operation_contract_ref, input_manifest_ref)
);

CREATE INDEX IF NOT EXISTS semantic_job_ready_queue_idx
    ON execution.semantic_job
       (priority, canonical_ordinal, job_ref)
    WHERE state_ref = 'ready';
CREATE INDEX IF NOT EXISTS semantic_job_expired_lease_idx
    ON execution.semantic_job (lease_expires_at, job_ref)
    WHERE state_ref = 'leased';
CREATE INDEX IF NOT EXISTS semantic_job_document_state_idx
    ON execution.semantic_job (document_ref, state_ref);

CREATE TABLE IF NOT EXISTS execution.semantic_job_dependency (
    job_ref TEXT NOT NULL
        REFERENCES execution.semantic_job(job_ref) ON DELETE CASCADE,
    dependency_job_ref TEXT NOT NULL
        REFERENCES execution.semantic_job(job_ref) ON DELETE CASCADE,
    dependency_kind_ref TEXT NOT NULL DEFAULT 'completion',
    PRIMARY KEY (job_ref, dependency_job_ref),
    CHECK (job_ref <> dependency_job_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_job_attempt (
    job_ref TEXT NOT NULL
        REFERENCES execution.semantic_job(job_ref) ON DELETE CASCADE,
    lease_epoch BIGINT NOT NULL CHECK (lease_epoch > 0),
    worker_ref TEXT NOT NULL,
    state_ref TEXT NOT NULL
        CHECK (state_ref IN ('leased', 'completed', 'expired', 'failed')),
    leased_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    resource_receipt JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (job_ref, lease_epoch)
);

-- Immutable worker output.  Execution is at-least-once; semantic admission is
-- idempotent and fenced by the accepted lease epoch.
CREATE TABLE IF NOT EXISTS execution.semantic_delta (
    delta_ref TEXT PRIMARY KEY,
    job_ref TEXT NOT NULL
        REFERENCES execution.semantic_job(job_ref) ON DELETE CASCADE,
    lease_epoch BIGINT NOT NULL CHECK (lease_epoch > 0),
    owner_ref TEXT NOT NULL
        REFERENCES execution.semantic_owner_stream(owner_ref),
    input_owner_revision BIGINT NOT NULL CHECK (input_owner_revision >= 0),
    output_manifest_ref TEXT NOT NULL,
    output_manifest_sha256 BYTEA NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (job_ref, lease_epoch),
    UNIQUE (job_ref, output_manifest_sha256)
);

CREATE TABLE IF NOT EXISTS execution.semantic_delta_admission (
    delta_ref TEXT PRIMARY KEY
        REFERENCES execution.semantic_delta(delta_ref) ON DELETE CASCADE,
    job_ref TEXT NOT NULL UNIQUE
        REFERENCES execution.semantic_job(job_ref) ON DELETE CASCADE,
    owner_ref TEXT NOT NULL
        REFERENCES execution.semantic_owner_stream(owner_ref),
    lease_epoch BIGINT NOT NULL,
    prior_owner_revision BIGINT NOT NULL CHECK (prior_owner_revision >= 0),
    resulting_owner_revision BIGINT NOT NULL
        CHECK (resulting_owner_revision > prior_owner_revision),
    admission_state_ref TEXT NOT NULL
        CHECK (admission_state_ref IN ('accepted', 'duplicate', 'stale')),
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (owner_ref, resulting_owner_revision)
);

CREATE TABLE IF NOT EXISTS execution.semantic_graph_manifest (
    manifest_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    owner_ref TEXT REFERENCES execution.semantic_owner_stream(owner_ref),
    graph_ref TEXT NOT NULL,
    graph_revision BIGINT NOT NULL CHECK (graph_revision >= 0),
    parent_manifest_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    root_sha256 BYTEA NOT NULL,
    node_count BIGINT NOT NULL DEFAULT 0 CHECK (node_count >= 0),
    edge_count BIGINT NOT NULL DEFAULT 0 CHECK (edge_count >= 0),
    unresolved_count BIGINT NOT NULL DEFAULT 0 CHECK (unresolved_count >= 0),
    coverage_digest BYTEA NOT NULL,
    operation_contract_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, graph_ref, graph_revision)
);

-- Large immutable families may be PostgreSQL rows or content-addressed object
-- segments.  PostgreSQL remains authoritative for identity and availability.
CREATE TABLE IF NOT EXISTS execution.semantic_graph_family_segment (
    segment_ref TEXT PRIMARY KEY,
    manifest_ref TEXT NOT NULL
        REFERENCES execution.semantic_graph_manifest(manifest_ref) ON DELETE CASCADE,
    family_ref TEXT NOT NULL,
    sequence_no BIGINT NOT NULL CHECK (sequence_no >= 0),
    storage_kind_ref TEXT NOT NULL
        CHECK (storage_kind_ref IN ('postgres_rows', 'object', 'filesystem_debug')),
    payload_uri TEXT,
    payload_sha256 BYTEA NOT NULL,
    ordered_digest BYTEA NOT NULL,
    row_count BIGINT NOT NULL CHECK (row_count >= 0),
    byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
    encoding_ref TEXT NOT NULL DEFAULT 'canonical-jsonl:v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (manifest_ref, family_ref, sequence_no)
);

CREATE TABLE IF NOT EXISTS execution.semantic_factor_revision (
    manifest_ref TEXT NOT NULL
        REFERENCES execution.semantic_graph_manifest(manifest_ref) ON DELETE CASCADE,
    factor_ref TEXT NOT NULL,
    factor_revision_ref TEXT NOT NULL,
    sequence_no BIGINT NOT NULL CHECK (sequence_no >= 0),
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    PRIMARY KEY (manifest_ref, factor_ref),
    UNIQUE (manifest_ref, sequence_no),
    UNIQUE (factor_revision_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_residual_revision (
    manifest_ref TEXT NOT NULL
        REFERENCES execution.semantic_graph_manifest(manifest_ref) ON DELETE CASCADE,
    residual_ref TEXT NOT NULL,
    sequence_no BIGINT NOT NULL CHECK (sequence_no >= 0),
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    PRIMARY KEY (manifest_ref, residual_ref),
    UNIQUE (manifest_ref, sequence_no)
);

CREATE TABLE IF NOT EXISTS execution.semantic_finalization_checkpoint (
    checkpoint_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    owner_ref TEXT REFERENCES execution.semantic_owner_stream(owner_ref),
    owner_revision BIGINT NOT NULL CHECK (owner_revision >= 0),
    phase_ref TEXT NOT NULL,
    state_ref TEXT NOT NULL
        CHECK (state_ref IN ('ready', 'leased', 'completed', 'failed')),
    cursor_ordinal BIGINT NOT NULL DEFAULT 0 CHECK (cursor_ordinal >= 0),
    total_rows BIGINT CHECK (total_rows IS NULL OR total_rows >= 0),
    lease_owner TEXT,
    lease_epoch BIGINT NOT NULL DEFAULT 0 CHECK (lease_epoch >= 0),
    lease_expires_at TIMESTAMPTZ,
    input_manifest_ref TEXT,
    output_manifest_ref TEXT,
    checkpoint_sha256 BYTEA NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, owner_revision, phase_ref)
);

CREATE INDEX IF NOT EXISTS semantic_finalization_ready_idx
    ON execution.semantic_finalization_checkpoint
       (document_ref, owner_revision, phase_ref)
    WHERE state_ref = 'ready';

CREATE TABLE IF NOT EXISTS execution.semantic_fixed_point_receipt (
    certificate_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    graph_manifest_ref TEXT NOT NULL
        REFERENCES execution.semantic_graph_manifest(manifest_ref),
    document_revision BIGINT NOT NULL CHECK (document_revision >= 0),
    accepted_job_set_digest BYTEA NOT NULL,
    unresolved_demand_digest BYTEA NOT NULL,
    coverage_digest BYTEA NOT NULL,
    operation_contract_refs JSONB NOT NULL,
    local_fixed_point BOOLEAN NOT NULL,
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, document_revision)
);

CREATE TABLE IF NOT EXISTS execution.semantic_execution_receipt (
    receipt_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    graph_manifest_ref TEXT NOT NULL
        REFERENCES execution.semantic_graph_manifest(manifest_ref),
    certificate_ref TEXT NOT NULL
        REFERENCES execution.semantic_fixed_point_receipt(certificate_ref),
    build_key_sha256 BYTEA NOT NULL,
    receipt_contract_ref TEXT NOT NULL,
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, build_key_sha256, receipt_contract_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    event_ref TEXT NOT NULL UNIQUE,
    aggregate_ref TEXT NOT NULL,
    event_type_ref TEXT NOT NULL,
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS semantic_outbox_pending_idx
    ON execution.semantic_outbox (outbox_id)
    WHERE delivered_at IS NULL;

CREATE TABLE IF NOT EXISTS execution.publication_build (
    publication_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    graph_manifest_ref TEXT NOT NULL
        REFERENCES execution.semantic_graph_manifest(manifest_ref),
    certificate_ref TEXT NOT NULL
        REFERENCES execution.semantic_fixed_point_receipt(certificate_ref),
    state_ref TEXT NOT NULL DEFAULT 'staged'
        CHECK (state_ref IN ('staged', 'committed', 'rolled_back', 'failed')),
    publication_digest BYTEA NOT NULL,
    staged_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    committed_at TIMESTAMPTZ,
    UNIQUE (document_ref, graph_manifest_ref)
);

COMMIT;
