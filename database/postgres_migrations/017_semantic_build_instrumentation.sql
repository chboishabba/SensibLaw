BEGIN;

CREATE TABLE IF NOT EXISTS pnf_factor_proposal (
    proposal_ref TEXT PRIMARY KEY,
    proposal_digest TEXT NOT NULL UNIQUE,
    document_ref TEXT NOT NULL,
    source_revision_ref TEXT NOT NULL,
    factor_type_ref TEXT NOT NULL,
    structural_signature TEXT NOT NULL,
    producer_contract TEXT NOT NULL,
    declaration_revision TEXT NOT NULL,
    source_span_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    input_observation_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    dependency_factor_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    role_bindings JSONB NOT NULL DEFAULT '{}'::jsonb,
    qualifier_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    candidate_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    residuals JSONB NOT NULL DEFAULT '[]'::jsonb,
    authority TEXT NOT NULL DEFAULT 'candidate_only',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (authority = 'candidate_only')
);

CREATE INDEX IF NOT EXISTS pnf_factor_proposal_document_idx
    ON pnf_factor_proposal (document_ref, factor_type_ref, structural_signature);

CREATE TABLE IF NOT EXISTS pnf_factor_proposal_dependency (
    proposal_ref TEXT NOT NULL REFERENCES pnf_factor_proposal(proposal_ref) ON DELETE CASCADE,
    dependency_ref TEXT NOT NULL,
    dependency_kind TEXT NOT NULL,
    PRIMARY KEY (proposal_ref, dependency_ref, dependency_kind),
    CHECK (dependency_kind IN ('observation', 'factor', 'span', 'declaration'))
);

CREATE TABLE IF NOT EXISTS pnf_document_reduction (
    graph_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    proposal_count INTEGER NOT NULL CHECK (proposal_count >= 0),
    deduplicated_count INTEGER NOT NULL CHECK (deduplicated_count >= 0),
    factor_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    residual_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE CHECK (identity_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pnf_reduction_residual (
    residual_ref TEXT PRIMARY KEY,
    graph_ref TEXT NOT NULL REFERENCES pnf_document_reduction(graph_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    residual_type TEXT NOT NULL,
    proposal_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pnf_cross_document_relation (
    relation_ref TEXT PRIMARY KEY,
    relation_type TEXT NOT NULL,
    source_document_ref TEXT NOT NULL,
    target_document_ref TEXT NOT NULL,
    source_coordinate_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_coordinate_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    qualifier_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    residuals JSONB NOT NULL DEFAULT '[]'::jsonb,
    identity_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (identity_closed = FALSE),
    legal_conclusion_promoted BOOLEAN NOT NULL DEFAULT FALSE CHECK (legal_conclusion_promoted = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (source_document_ref <> target_document_ref)
);

CREATE INDEX IF NOT EXISTS pnf_cross_document_relation_source_idx
    ON pnf_cross_document_relation (source_document_ref, relation_type);
CREATE INDEX IF NOT EXISTS pnf_cross_document_relation_target_idx
    ON pnf_cross_document_relation (target_document_ref, relation_type);

CREATE TABLE IF NOT EXISTS catalogue_document_current_build (
    catalogue_ref TEXT NOT NULL,
    document_ref TEXT NOT NULL,
    build_ref TEXT NOT NULL,
    promoted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    promotion_receipt_ref TEXT NOT NULL,
    PRIMARY KEY (catalogue_ref, document_ref)
);

CREATE TABLE IF NOT EXISTS semantic_build_phase_event (
    build_ref TEXT NOT NULL,
    event_ordinal INTEGER NOT NULL CHECK (event_ordinal >= 0),
    phase TEXT NOT NULL,
    state TEXT NOT NULL,
    subject_ref TEXT,
    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed >= 0),
    total INTEGER CHECK (total IS NULL OR total >= 0),
    started_at TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL,
    elapsed_ms BIGINT CHECK (elapsed_ms IS NULL OR elapsed_ms >= 0),
    worker TEXT,
    reused BOOLEAN,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (build_ref, event_ordinal),
    CHECK (state IN ('started', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS semantic_build_phase_event_phase_idx
    ON semantic_build_phase_event (build_ref, phase, elapsed_ms DESC NULLS LAST);

COMMIT;
