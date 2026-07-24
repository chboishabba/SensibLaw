BEGIN;

CREATE TABLE IF NOT EXISTS source_admission_receipt (
    receipt_ref TEXT PRIMARY KEY,
    corpus_ref TEXT,
    source_revision_ref TEXT NOT NULL,
    source_role TEXT NOT NULL,
    semantic_scope TEXT NOT NULL,
    admission_state TEXT NOT NULL CHECK (
        admission_state IN ('compile', 'evidence_only', 'exclude')
    ),
    exclusion_reason TEXT,
    profile_ref TEXT NOT NULL,
    contract_ref TEXT NOT NULL,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    receipt_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_revision_ref, profile_ref)
);

CREATE INDEX IF NOT EXISTS source_admission_profile_state_idx
    ON source_admission_receipt (profile_ref, admission_state, source_role);

CREATE TABLE IF NOT EXISTS legal_source_revision (
    source_revision_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    admission_receipt_ref TEXT NOT NULL
        REFERENCES source_admission_receipt(receipt_ref),
    acquisition_receipt_ref TEXT,
    jurisdiction_ref TEXT NOT NULL,
    source_role TEXT NOT NULL,
    authority_level TEXT NOT NULL,
    temporal_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    provider_profile_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    media_type TEXT NOT NULL,
    canonical_text_sha256 TEXT NOT NULL,
    compile_eligible BOOLEAN NOT NULL DEFAULT TRUE
        CHECK (compile_eligible = TRUE),
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (identity_promoted = FALSE),
    applicability_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (applicability_closed = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    revision_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS legal_source_revision_selection_idx
    ON legal_source_revision
    (jurisdiction_ref, source_role, authority_level, compile_eligible);

CREATE TABLE IF NOT EXISTS legal_source_plan_receipt (
    plan_ref TEXT PRIMARY KEY,
    demand_ref TEXT NOT NULL,
    plan_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('ready_persisted', 'blocked_missing_context',
                  'blocked_acquisition_required')
    ),
    selected_source_revision_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    blocked_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    authority TEXT NOT NULL DEFAULT 'acquisition_plan_only'
        CHECK (authority = 'acquisition_plan_only'),
    applicability_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (applicability_closed = FALSE),
    plan_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS governed_acquisition_receipt (
    receipt_ref TEXT PRIMARY KEY,
    request_ref TEXT NOT NULL,
    operator_authorization_ref TEXT NOT NULL,
    provider_profile_ref TEXT NOT NULL,
    requested_url TEXT NOT NULL,
    final_url TEXT,
    source_revision_ref TEXT,
    content_sha256 TEXT,
    media_type TEXT,
    byte_count BIGINT NOT NULL DEFAULT 0,
    state TEXT NOT NULL CHECK (
        state IN ('persisted', 'reused', 'rejected', 'failed')
    ),
    failure_reason TEXT,
    network_operation_explicit BOOLEAN NOT NULL DEFAULT TRUE
        CHECK (network_operation_explicit = TRUE),
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    receipt_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (request_ref, content_sha256)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'legal_source_revision_acquisition_fk'
          AND conrelid = 'legal_source_revision'::regclass
    ) THEN
        ALTER TABLE legal_source_revision
            ADD CONSTRAINT legal_source_revision_acquisition_fk
            FOREIGN KEY (acquisition_receipt_ref)
            REFERENCES governed_acquisition_receipt(receipt_ref)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS execution_document_transaction_attempt (
    attempt_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    build_key_sha256 TEXT NOT NULL,
    attempt_no INTEGER NOT NULL CHECK (attempt_no >= 1),
    state TEXT NOT NULL CHECK (state IN ('succeeded', 'retryable_failure', 'failed')),
    sqlstate TEXT,
    retry_delay_ms INTEGER NOT NULL DEFAULT 0 CHECK (retry_delay_ms >= 0),
    worker_ref TEXT,
    telemetry_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, build_key_sha256, attempt_no)
);

CREATE TABLE IF NOT EXISTS curated_legal_ir_parity_receipt (
    receipt_ref TEXT PRIMARY KEY,
    corpus_ref TEXT NOT NULL,
    admission_profile_ref TEXT NOT NULL,
    compiler_contract_ref TEXT NOT NULL,
    source_revision_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    ordinary_graph_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    legal_graph_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    demand_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    plan_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    legal_ir_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    typed_meet_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    legacy_witness_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    identity_snapshot JSONB NOT NULL,
    control_snapshot JSONB,
    identity_parity BOOLEAN,
    network_attempt_count INTEGER NOT NULL DEFAULT 0
        CHECK (network_attempt_count = 0),
    unexpected_failure_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    applicability_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (applicability_closed = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    receipt_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
