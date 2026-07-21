BEGIN;

CREATE SCHEMA IF NOT EXISTS legal_ir;
CREATE SCHEMA IF NOT EXISTS diagnostic;

CREATE TABLE IF NOT EXISTS legal_ir.semantic_build (
    build_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    source_revision_ref TEXT NOT NULL,
    canonical_text_ref TEXT NOT NULL,
    parser_build_ref TEXT NOT NULL,
    pnf_build_ref TEXT NOT NULL,
    refined_pnf_graph_ref TEXT NOT NULL,
    legal_ir_projection_ref TEXT NOT NULL,
    legacy_observation_set_ref TEXT NOT NULL,
    comparison_ledger_ref TEXT NOT NULL,
    coverage_demand_refs TEXT[] NOT NULL DEFAULT '{}',
    declaration_revision_refs TEXT[] NOT NULL DEFAULT '{}',
    build_state_ref TEXT NOT NULL,
    provenance_refs TEXT[] NOT NULL DEFAULT '{}',
    build_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS legal_ir.projection (
    projection_ref TEXT PRIMARY KEY,
    build_ref TEXT NOT NULL REFERENCES legal_ir.semantic_build(build_ref),
    pnf_build_ref TEXT NOT NULL,
    projection_contract_ref TEXT NOT NULL,
    omitted_factor_refs TEXT[] NOT NULL DEFAULT '{}',
    projection_residuals TEXT[] NOT NULL DEFAULT '{}',
    projection_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS legal_ir.observation (
    observation_ref TEXT PRIMARY KEY,
    projection_ref TEXT NOT NULL REFERENCES legal_ir.projection(projection_ref) ON DELETE CASCADE,
    pnf_factor_ref TEXT NOT NULL,
    pnf_revision_ref TEXT NOT NULL,
    structural_signature_ref TEXT NOT NULL,
    predicate_ref TEXT NOT NULL,
    role_bindings JSONB NOT NULL DEFAULT '{}',
    qualifier_state JSONB NOT NULL DEFAULT '{}',
    wrapper_state JSONB NOT NULL DEFAULT '{}',
    provenance_refs TEXT[] NOT NULL DEFAULT '{}',
    residual_refs TEXT[] NOT NULL DEFAULT '{}',
    projection_state_ref TEXT NOT NULL DEFAULT 'candidate',
    observation_sha256 BYTEA NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS legal_ir_observation_signature_idx
    ON legal_ir.observation (structural_signature_ref, predicate_ref);

CREATE TABLE IF NOT EXISTS diagnostic.legacy_witness (
    witness_ref TEXT PRIMARY KEY,
    build_ref TEXT NOT NULL REFERENCES legal_ir.semantic_build(build_ref),
    extractor_contract_ref TEXT NOT NULL,
    source_span_refs TEXT[] NOT NULL DEFAULT '{}',
    candidate_kind_ref TEXT NOT NULL,
    candidate_payload JSONB NOT NULL,
    match_state_ref TEXT NOT NULL,
    provenance_refs TEXT[] NOT NULL DEFAULT '{}',
    authority_state_ref TEXT NOT NULL CHECK (authority_state_ref = 'diagnostic_only'),
    witness_sha256 BYTEA NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS diagnostic.semantic_comparison (
    comparison_ref TEXT PRIMARY KEY,
    build_ref TEXT NOT NULL REFERENCES legal_ir.semantic_build(build_ref),
    document_ref TEXT NOT NULL,
    comparison_kind_ref TEXT NOT NULL,
    structural_signature_ref TEXT NOT NULL,
    source_span_refs TEXT[] NOT NULL DEFAULT '{}',
    pnf_factor_refs TEXT[] NOT NULL DEFAULT '{}',
    legal_ir_observation_refs TEXT[] NOT NULL DEFAULT '{}',
    legacy_witness_refs TEXT[] NOT NULL DEFAULT '{}',
    comparison_state_ref TEXT NOT NULL,
    coordinate_states JSONB NOT NULL DEFAULT '{}',
    discrepancy_refs TEXT[] NOT NULL DEFAULT '{}',
    proposed_actions TEXT[] NOT NULL DEFAULT '{}',
    comparison_sha256 BYTEA NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS diagnostic_semantic_comparison_state_idx
    ON diagnostic.semantic_comparison (comparison_state_ref, comparison_kind_ref);

CREATE TABLE IF NOT EXISTS diagnostic.pnf_coverage_demand (
    demand_ref TEXT PRIMARY KEY,
    build_ref TEXT NOT NULL REFERENCES legal_ir.semantic_build(build_ref),
    document_ref TEXT NOT NULL,
    source_observation_refs TEXT[] NOT NULL DEFAULT '{}',
    candidate_composition_kind_ref TEXT NOT NULL,
    expected_role_shape TEXT[] NOT NULL DEFAULT '{}',
    missing_factor_type_ref TEXT NOT NULL,
    witness_refs TEXT[] NOT NULL DEFAULT '{}',
    structural_signature_ref TEXT NOT NULL,
    demand_state_ref TEXT NOT NULL CHECK (demand_state_ref = 'requires_pnf_reconstruction'),
    direct_factor_creation_allowed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (direct_factor_creation_allowed = FALSE),
    demand_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS legal_ir.graph_revision (
    revision_ref TEXT PRIMARY KEY,
    subject_ref TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    prior_revision_refs TEXT[] NOT NULL DEFAULT '{}',
    source_span_refs TEXT[] NOT NULL DEFAULT '{}',
    legal_system_refs TEXT[] NOT NULL DEFAULT '{}',
    jurisdiction_refs TEXT[] NOT NULL DEFAULT '{}',
    temporal_refs TEXT[] NOT NULL DEFAULT '{}',
    author_ref TEXT NOT NULL,
    institution_ref TEXT,
    build_ref TEXT NOT NULL REFERENCES legal_ir.semantic_build(build_ref),
    revision_state_ref TEXT NOT NULL DEFAULT 'candidate',
    revision_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS legal_ir_graph_revision_subject_idx
    ON legal_ir.graph_revision (subject_ref, created_at);

CREATE TABLE IF NOT EXISTS legal_ir.reviewer_credential (
    credential_ref TEXT PRIMARY KEY,
    reviewer_ref TEXT NOT NULL,
    institution_ref TEXT,
    jurisdiction_refs TEXT[] NOT NULL DEFAULT '{}',
    practice_area_refs TEXT[] NOT NULL DEFAULT '{}',
    credential_type_refs TEXT[] NOT NULL DEFAULT '{}',
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    verification_state_ref TEXT NOT NULL,
    credential_sha256 BYTEA NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS legal_ir.review_attestation (
    attestation_ref TEXT PRIMARY KEY,
    revision_ref TEXT NOT NULL REFERENCES legal_ir.graph_revision(revision_ref),
    reviewer_ref TEXT NOT NULL,
    credential_refs TEXT[] NOT NULL DEFAULT '{}',
    institution_ref TEXT,
    review_state_ref TEXT NOT NULL CHECK (
        review_state_ref IN (
            'endorse',
            'approve_with_residuals',
            'reject',
            'contest',
            'abstain',
            'supersede'
        )
    ),
    coordinate_states JSONB NOT NULL DEFAULT '{}',
    reason_refs TEXT[] NOT NULL DEFAULT '{}',
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    supersedes_attestation_refs TEXT[] NOT NULL DEFAULT '{}',
    signature_ref TEXT,
    attestation_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS legal_ir_review_attestation_revision_idx
    ON legal_ir.review_attestation (revision_ref, review_state_ref, created_at);

CREATE TABLE IF NOT EXISTS legal_ir.trust_projection (
    projection_ref TEXT PRIMARY KEY,
    revision_ref TEXT NOT NULL REFERENCES legal_ir.graph_revision(revision_ref),
    scope_ref TEXT NOT NULL,
    endorsement_count INTEGER NOT NULL CHECK (endorsement_count >= 0),
    qualified_approval_count INTEGER NOT NULL CHECK (qualified_approval_count >= 0),
    rejection_count INTEGER NOT NULL CHECK (rejection_count >= 0),
    contest_count INTEGER NOT NULL CHECK (contest_count >= 0),
    abstention_count INTEGER NOT NULL CHECK (abstention_count >= 0),
    supersession_count INTEGER NOT NULL CHECK (supersession_count >= 0),
    active_reviewer_refs TEXT[] NOT NULL DEFAULT '{}',
    institution_refs TEXT[] NOT NULL DEFAULT '{}',
    unresolved_coordinate_refs TEXT[] NOT NULL DEFAULT '{}',
    state_ref TEXT NOT NULL,
    truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (truth_closed = FALSE),
    projection_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (revision_ref, scope_ref, projection_sha256)
);

CREATE TABLE IF NOT EXISTS legal_ir.federation_bundle (
    bundle_ref TEXT PRIMARY KEY,
    graph_revision_refs TEXT[] NOT NULL DEFAULT '{}',
    credential_refs TEXT[] NOT NULL DEFAULT '{}',
    attestation_refs TEXT[] NOT NULL DEFAULT '{}',
    trust_projection_refs TEXT[] NOT NULL DEFAULT '{}',
    federation_refs TEXT[] NOT NULL DEFAULT '{}',
    checkpoint_state_ref TEXT NOT NULL,
    anonymous_consensus BOOLEAN NOT NULL DEFAULT FALSE CHECK (anonymous_consensus = FALSE),
    disagreement_preserved BOOLEAN NOT NULL DEFAULT TRUE CHECK (disagreement_preserved = TRUE),
    bundle_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE VIEW legal_ir.v_reviewable_graph_revision AS
SELECT
    revision.revision_ref,
    revision.subject_ref,
    revision.jurisdiction_refs,
    revision.temporal_refs,
    revision.author_ref,
    revision.institution_ref,
    revision.revision_state_ref,
    COUNT(attestation.attestation_ref) FILTER (
        WHERE attestation.review_state_ref = 'endorse'
    ) AS endorsement_count,
    COUNT(attestation.attestation_ref) FILTER (
        WHERE attestation.review_state_ref = 'reject'
    ) AS rejection_count,
    COUNT(attestation.attestation_ref) FILTER (
        WHERE attestation.review_state_ref = 'contest'
    ) AS contest_count
FROM legal_ir.graph_revision AS revision
LEFT JOIN legal_ir.review_attestation AS attestation
  ON attestation.revision_ref = revision.revision_ref
GROUP BY revision.revision_ref;

COMMIT;
