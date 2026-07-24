BEGIN;

CREATE TABLE IF NOT EXISTS legal_ir.review_claim (
    claim_ref TEXT PRIMARY KEY,
    claim_kind_ref TEXT NOT NULL CHECK (claim_kind_ref IN (
        'identification', 'graph_placement', 'structural_role', 'legal_function',
        'legal_outcome', 'legal_implication', 'cross_source_join',
        'temporal_validity', 'jurisdictional_scope', 'reconstruction_fitness',
        'subgraph_coherence', 'build_fitness'
    )),
    subject_ref TEXT NOT NULL,
    proposition_ref TEXT NOT NULL,
    target_refs TEXT[] NOT NULL DEFAULT '{}',
    source_span_refs TEXT[] NOT NULL DEFAULT '{}',
    dependency_claim_refs TEXT[] NOT NULL DEFAULT '{}',
    residual_refs TEXT[] NOT NULL DEFAULT '{}',
    truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (truth_closed = FALSE),
    claim_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS legal_ir.system_review_attestation (
    attestation_ref TEXT PRIMARY KEY,
    revision_ref TEXT NOT NULL REFERENCES legal_ir.graph_revision(revision_ref),
    build_ref TEXT NOT NULL REFERENCES legal_ir.semantic_build(build_ref),
    reviewer_ref TEXT NOT NULL,
    credential_refs TEXT[] NOT NULL DEFAULT '{}',
    institution_ref TEXT,
    review_state_ref TEXT NOT NULL CHECK (review_state_ref IN (
        'endorse', 'approve_with_residuals', 'reject', 'contest',
        'abstain', 'supersede'
    )),
    reviewed_claim_refs TEXT[] NOT NULL,
    reason_refs TEXT[] NOT NULL DEFAULT '{}',
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    method_refs TEXT[] NOT NULL DEFAULT '{}',
    supersedes_attestation_refs TEXT[] NOT NULL DEFAULT '{}',
    signature_ref TEXT,
    changes_graph_revision BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (changes_graph_revision = FALSE),
    changes_pnf BOOLEAN NOT NULL DEFAULT FALSE CHECK (changes_pnf = FALSE),
    truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (truth_closed = FALSE),
    attestation_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_ir.system_review_claim_state (
    attestation_ref TEXT NOT NULL
        REFERENCES legal_ir.system_review_attestation(attestation_ref) ON DELETE CASCADE,
    claim_ref TEXT NOT NULL REFERENCES legal_ir.review_claim(claim_ref),
    claim_state_ref TEXT NOT NULL CHECK (claim_state_ref IN (
        'supported', 'supported_with_residuals', 'unsupported',
        'contested', 'unresolved', 'not_reviewed'
    )),
    PRIMARY KEY (attestation_ref, claim_ref)
);

CREATE TABLE IF NOT EXISTS legal_ir.system_review_projection (
    projection_ref TEXT PRIMARY KEY,
    revision_ref TEXT NOT NULL REFERENCES legal_ir.graph_revision(revision_ref),
    build_ref TEXT NOT NULL REFERENCES legal_ir.semantic_build(build_ref),
    scope_ref TEXT NOT NULL,
    state_ref TEXT NOT NULL,
    supported_claim_refs TEXT[] NOT NULL DEFAULT '{}',
    qualified_claim_refs TEXT[] NOT NULL DEFAULT '{}',
    unsupported_claim_refs TEXT[] NOT NULL DEFAULT '{}',
    contested_claim_refs TEXT[] NOT NULL DEFAULT '{}',
    unresolved_claim_refs TEXT[] NOT NULL DEFAULT '{}',
    reviewer_refs TEXT[] NOT NULL DEFAULT '{}',
    institution_refs TEXT[] NOT NULL DEFAULT '{}',
    truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (truth_closed = FALSE),
    universal_authority BOOLEAN NOT NULL DEFAULT FALSE CHECK (universal_authority = FALSE),
    projection_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (revision_ref, build_ref, scope_ref, projection_sha256)
);

CREATE SCHEMA IF NOT EXISTS transport;

CREATE TABLE IF NOT EXISTS transport.legal_artifact_envelope (
    object_id TEXT PRIMARY KEY,
    kind_ref TEXT NOT NULL CHECK (kind_ref IN ('artifact', 'receipt')),
    content_digest TEXT NOT NULL CHECK (content_digest LIKE 'sha256:%'),
    producer_contract_ref TEXT NOT NULL,
    producer_locator_set TEXT[] NOT NULL DEFAULT '{}',
    semantic_build_ref TEXT REFERENCES legal_ir.semantic_build(build_ref),
    source_revision_refs TEXT[] NOT NULL DEFAULT '{}',
    payload_media_type TEXT NOT NULL,
    payload_size BIGINT NOT NULL CHECK (payload_size >= 0),
    semantic_promotion_performed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_promotion_performed = FALSE),
    trust_imported BOOLEAN NOT NULL DEFAULT FALSE CHECK (trust_imported = FALSE),
    truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (truth_closed = FALSE),
    envelope_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (kind_ref, object_id, content_digest, producer_contract_ref)
);

CREATE TABLE IF NOT EXISTS transport.legal_artifact_member (
    object_id TEXT NOT NULL REFERENCES transport.legal_artifact_envelope(object_id)
        ON DELETE CASCADE,
    member_ref TEXT NOT NULL,
    member_kind_ref TEXT NOT NULL,
    content_digest TEXT NOT NULL CHECK (content_digest LIKE 'sha256:%'),
    producer_contract_ref TEXT NOT NULL,
    PRIMARY KEY (object_id, member_ref)
);

CREATE TABLE IF NOT EXISTS transport.legal_artifact_verification_receipt (
    receipt_ref TEXT PRIMARY KEY,
    object_id TEXT NOT NULL REFERENCES transport.legal_artifact_envelope(object_id),
    expected_digest TEXT NOT NULL,
    observed_digest TEXT NOT NULL,
    locator_ref TEXT NOT NULL,
    verification_state_ref TEXT NOT NULL CHECK (verification_state_ref IN (
        'verified_available', 'digest_mismatch'
    )),
    member_states JSONB NOT NULL,
    semantic_promotion_performed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_promotion_performed = FALSE),
    review_state_imported BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (review_state_imported = FALSE),
    truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (truth_closed = FALSE),
    receipt_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
