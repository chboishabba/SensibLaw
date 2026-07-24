BEGIN;

ALTER TABLE pnf_factor_proposal
    ADD COLUMN IF NOT EXISTS semantic_coordinate_ref TEXT,
    ADD COLUMN IF NOT EXISTS scope_ref TEXT,
    ADD COLUMN IF NOT EXISTS statement_role TEXT NOT NULL DEFAULT 'main',
    ADD COLUMN IF NOT EXISTS coordinate_kind TEXT NOT NULL DEFAULT 'object',
    ADD COLUMN IF NOT EXISTS fibre_kind TEXT NOT NULL DEFAULT 'hypothesis',
    ADD COLUMN IF NOT EXISTS derivation_role TEXT NOT NULL DEFAULT 'support',
    ADD COLUMN IF NOT EXISTS producer_scope TEXT NOT NULL DEFAULT 'integrated',
    ADD COLUMN IF NOT EXISTS operation_contract TEXT,
    ADD COLUMN IF NOT EXISTS ontology_axis_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS transport_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS support_state TEXT NOT NULL DEFAULT 'candidate',
    ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS coverage_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS execution_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS pnf_factor_proposal_coordinate_idx
    ON pnf_factor_proposal
    (document_ref, semantic_coordinate_ref, fibre_kind, factor_type_ref);

CREATE TABLE IF NOT EXISTS semantic_coordinate (
    coordinate_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    source_span_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    statement_role TEXT NOT NULL,
    factor_family TEXT NOT NULL,
    coordinate_kind TEXT NOT NULL CHECK (
        coordinate_kind IN ('object', 'morphism', 'obligation', 'external')
    ),
    source_coordinate_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_coordinate_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS semantic_coordinate_document_idx
    ON semantic_coordinate (document_ref, scope_ref, factor_family);

CREATE TABLE IF NOT EXISTS semantic_fibre_element (
    element_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    coordinate_ref TEXT NOT NULL REFERENCES semantic_coordinate(coordinate_ref),
    fibre_kind TEXT NOT NULL CHECK (fibre_kind IN (
        'observation', 'hypothesis', 'composition', 'constraint',
        'consequence', 'enrichment', 'residual', 'review'
    )),
    content_ref TEXT NOT NULL,
    derivation_role TEXT NOT NULL CHECK (
        derivation_role IN ('support', 'contradict', 'undetermined', 'transport')
    ),
    producer_contract TEXT NOT NULL,
    operation_contract TEXT NOT NULL,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    dependency_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    transport_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    ontology_axis_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    coverage_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    support_state TEXT NOT NULL,
    confidence DOUBLE PRECISION CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    ),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    external BOOLEAN NOT NULL DEFAULT FALSE,
    execution_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    authority TEXT NOT NULL CHECK (
        authority IN ('candidate_only', 'external_candidate')
    ),
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (coordinate_ref, content_ref, producer_contract, operation_contract)
);

CREATE INDEX IF NOT EXISTS semantic_fibre_element_coordinate_idx
    ON semantic_fibre_element
    (document_ref, coordinate_ref, fibre_kind, derivation_role);

CREATE TABLE IF NOT EXISTS semantic_fibre_derivation (
    derivation_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    operation_kind TEXT NOT NULL,
    declaration_ref TEXT NOT NULL,
    producer_contract TEXT NOT NULL,
    input_element_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    output_element_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    sub_executor_ref TEXT NOT NULL,
    rule_set_revision TEXT NOT NULL,
    receipt_ref TEXT,
    assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_transport (
    transport_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    source_coordinate_ref TEXT NOT NULL,
    target_coordinate_ref TEXT NOT NULL,
    transport_type TEXT NOT NULL,
    strength TEXT NOT NULL CHECK (
        strength IN ('discoverable', 'candidate', 'close', 'exact', 'identity')
    ),
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    ontology_axis_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_operations JSONB NOT NULL DEFAULT '[]'::jsonb,
    residual_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    identity_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (identity_closed = FALSE),
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (source_coordinate_ref <> target_coordinate_ref),
    CHECK (strength <> 'discoverable' OR NOT (allowed_operations ? 'substitute'))
);

CREATE TABLE IF NOT EXISTS semantic_ontology_axis (
    axis_ref TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    authority_ref TEXT NOT NULL,
    relation_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    root_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    open_world BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_axis_obligation (
    obligation_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    coordinate_ref TEXT NOT NULL,
    axis_ref TEXT NOT NULL REFERENCES semantic_ontology_axis(axis_ref),
    obligation_type TEXT NOT NULL,
    trigger_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    frontier_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    state TEXT NOT NULL CHECK (state IN (
        'open', 'satisfied', 'contradicted', 'both',
        'undetermined', 'inapplicable'
    )),
    resource_limit_reached BOOLEAN NOT NULL DEFAULT FALSE,
    truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_fibre_boundary_obligation (
    boundary_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    coordinate_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    boundary_kind TEXT NOT NULL,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    frontier_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_axis_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    state TEXT NOT NULL CHECK (state IN ('open', 'discharged', 'external')),
    message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_fibre_summary (
    factor_ref TEXT PRIMARY KEY,
    graph_ref TEXT NOT NULL,
    document_ref TEXT NOT NULL,
    semantic_coordinate_ref TEXT NOT NULL,
    fibre_kind TEXT NOT NULL,
    factor_type_ref TEXT NOT NULL,
    structural_signature TEXT NOT NULL,
    proposal_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    derivation_roles JSONB NOT NULL DEFAULT '[]'::jsonb,
    ontology_axis_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    transport_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    support_states JSONB NOT NULL DEFAULT '[]'::jsonb,
    residual_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    deterministic_materialisation BOOLEAN NOT NULL DEFAULT TRUE
        CHECK (deterministic_materialisation = TRUE),
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE CHECK (identity_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS integrated_semantic_producer_receipt (
    receipt_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    contract_ref TEXT NOT NULL,
    proposal_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    sub_executor_receipt_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    fibre_ledger_ref TEXT NOT NULL,
    residual_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    external_proposal_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    one_proposal_contract BOOLEAN NOT NULL DEFAULT TRUE
        CHECK (one_proposal_contract = TRUE),
    one_reduction_authority BOOLEAN NOT NULL DEFAULT TRUE
        CHECK (one_reduction_authority = TRUE),
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE CHECK (identity_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
