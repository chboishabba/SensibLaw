BEGIN;

CREATE TABLE IF NOT EXISTS pnf_candidate_assessment (
    assessment_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    proposal_ref TEXT NOT NULL,
    semantic_coordinate_ref TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (
        outcome IN ('satisfied', 'violated', 'both', 'undetermined', 'inapplicable')
    ),
    coverage_complete BOOLEAN NOT NULL,
    applicable BOOLEAN NOT NULL,
    payload JSONB NOT NULL,
    assessment_sha256 BYTEA NOT NULL,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS pnf_candidate_assessment_document_idx
    ON pnf_candidate_assessment (document_ref, semantic_coordinate_ref, outcome);

CREATE TABLE IF NOT EXISTS pnf_admissibility_receipt (
    receipt_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    proposal_ref TEXT NOT NULL,
    assessment_ref TEXT NOT NULL
        REFERENCES pnf_candidate_assessment(assessment_ref),
    state TEXT NOT NULL CHECK (state IN ('admitted', 'rejected', 'blocked')),
    authority_ceiling TEXT NOT NULL,
    payload JSONB NOT NULL,
    receipt_sha256 BYTEA NOT NULL,
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (identity_promoted = FALSE),
    applicability_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (applicability_closed = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS pnf_admissibility_document_state_idx
    ON pnf_admissibility_receipt (document_ref, state, proposal_ref);

CREATE TABLE IF NOT EXISTS pnf_resolution_receipt (
    resolution_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    fibre_summary_ref TEXT NOT NULL,
    semantic_coordinate_ref TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('resolved_unique', 'resolved_preferred', 'retained_plural',
                  'blocked_insufficient_coverage', 'blocked_conflict', 'inapplicable')
    ),
    selected_proposal_ref TEXT,
    selector_ref TEXT NOT NULL,
    payload JSONB NOT NULL,
    receipt_sha256 BYTEA NOT NULL,
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (identity_promoted = FALSE),
    applicability_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (applicability_closed = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS pnf_resolution_document_state_idx
    ON pnf_resolution_receipt (document_ref, state, semantic_coordinate_ref);

CREATE TABLE IF NOT EXISTS pnf_domain_ir_projection_contract (
    contract_ref TEXT PRIMARY KEY,
    domain TEXT NOT NULL CHECK (domain IN ('legal', 'timeline', 'retrieval')),
    authority_ceiling TEXT NOT NULL,
    residual_policy TEXT NOT NULL,
    payload JSONB NOT NULL,
    contract_sha256 BYTEA NOT NULL,
    projection_adds_world_truth BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (projection_adds_world_truth = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pnf_projection_demand (
    demand_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    domain TEXT NOT NULL CHECK (domain IN ('legal', 'timeline', 'retrieval')),
    resolution_ref TEXT NOT NULL
        REFERENCES pnf_resolution_receipt(resolution_ref),
    source_factor_ref TEXT NOT NULL,
    structural_signature_ref TEXT NOT NULL,
    demand_kind TEXT NOT NULL,
    priority INTEGER NOT NULL,
    payload JSONB NOT NULL,
    demand_sha256 BYTEA NOT NULL,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    applicability_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (applicability_closed = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS pnf_projection_demand_frontier_idx
    ON pnf_projection_demand (document_ref, domain, demand_kind, priority DESC);

CREATE TABLE IF NOT EXISTS pnf_projection_loss_receipt (
    loss_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    domain TEXT NOT NULL CHECK (domain IN ('legal', 'timeline', 'retrieval')),
    source_resolution_ref TEXT NOT NULL
        REFERENCES pnf_resolution_receipt(resolution_ref),
    projection_contract_ref TEXT NOT NULL
        REFERENCES pnf_domain_ir_projection_contract(contract_ref),
    payload JSONB NOT NULL,
    receipt_sha256 BYTEA NOT NULL,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pnf_domain_ir_projection_receipt (
    receipt_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    domain TEXT NOT NULL CHECK (domain IN ('legal', 'timeline', 'retrieval')),
    source_resolution_ref TEXT NOT NULL
        REFERENCES pnf_resolution_receipt(resolution_ref),
    source_factor_ref TEXT NOT NULL,
    projection_contract_ref TEXT NOT NULL
        REFERENCES pnf_domain_ir_projection_contract(contract_ref),
    state TEXT NOT NULL CHECK (state IN ('projected', 'blocked', 'inapplicable')),
    selected_proposal_ref TEXT,
    loss_ref TEXT REFERENCES pnf_projection_loss_receipt(loss_ref),
    payload JSONB NOT NULL,
    receipt_sha256 BYTEA NOT NULL,
    applicability_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (applicability_closed = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pnf_domain_ir (
    domain_ir_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    domain TEXT NOT NULL CHECK (domain IN ('legal', 'timeline', 'retrieval')),
    source_resolution_ref TEXT NOT NULL
        REFERENCES pnf_resolution_receipt(resolution_ref),
    source_factor_ref TEXT NOT NULL,
    selected_proposal_ref TEXT NOT NULL,
    structural_signature_ref TEXT NOT NULL,
    projection_contract_ref TEXT NOT NULL
        REFERENCES pnf_domain_ir_projection_contract(contract_ref),
    projection_receipt_ref TEXT NOT NULL
        REFERENCES pnf_domain_ir_projection_receipt(receipt_ref),
    loss_ref TEXT NOT NULL REFERENCES pnf_projection_loss_receipt(loss_ref),
    validation_state TEXT NOT NULL,
    payload JSONB NOT NULL,
    ir_sha256 BYTEA NOT NULL,
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (identity_promoted = FALSE),
    applicability_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (applicability_closed = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS pnf_domain_ir_document_domain_idx
    ON pnf_domain_ir (document_ref, domain, validation_state);

CREATE TABLE IF NOT EXISTS pnf_ir_execution_receipt (
    receipt_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    request_ref TEXT NOT NULL,
    domain_ir_ref TEXT NOT NULL REFERENCES pnf_domain_ir(domain_ir_ref),
    rule_or_query_ref TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (
        outcome IN ('executed', 'refused_invalid_ir',
                    'refused_missing_applicability',
                    'blocked_missing_evidence', 'superseded')
    ),
    applicability_witnessed BOOLEAN NOT NULL,
    payload JSONB NOT NULL,
    receipt_sha256 BYTEA NOT NULL,
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (identity_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS pnf_ir_execution_document_outcome_idx
    ON pnf_ir_execution_receipt (document_ref, outcome, rule_or_query_ref);

COMMIT;
