BEGIN;

CREATE TABLE IF NOT EXISTS semantic_observation_delta (
    delta_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    batch_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    parser_contract TEXT NOT NULL,
    observation_refs JSONB NOT NULL,
    observations JSONB NOT NULL,
    token_start INTEGER NOT NULL CHECK (token_start >= 0),
    token_end INTEGER NOT NULL CHECK (token_end >= token_start),
    char_start INTEGER NOT NULL CHECK (char_start >= 0),
    char_end INTEGER NOT NULL CHECK (char_end >= char_start),
    token_count INTEGER NOT NULL CHECK (token_count = token_end - token_start),
    coverage_barrier TEXT NOT NULL,
    coverage_complete BOOLEAN NOT NULL,
    payload_sha256 BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, batch_ref),
    CHECK (coverage_barrier IN ('token_batch', 'sentence', 'section', 'document'))
);

CREATE INDEX IF NOT EXISTS semantic_observation_delta_document_idx
    ON semantic_observation_delta (document_ref, sequence_no, scope_ref);

CREATE TABLE IF NOT EXISTS semantic_coverage_notice (
    notice_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    barrier TEXT NOT NULL,
    state TEXT NOT NULL,
    evidence_refs JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (barrier IN ('token_batch', 'sentence', 'section', 'document')),
    CHECK (state IN ('open', 'complete'))
);

CREATE INDEX IF NOT EXISTS semantic_coverage_notice_scope_idx
    ON semantic_coverage_notice (document_ref, scope_ref, barrier, state);

CREATE TABLE IF NOT EXISTS semantic_solver_job (
    job_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    owner_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    factor_family TEXT NOT NULL,
    declaration_ref TEXT NOT NULL,
    input_revision BIGINT NOT NULL CHECK (input_revision >= 0),
    input_refs JSONB NOT NULL,
    input_payload JSONB NOT NULL,
    rule_set_revision TEXT NOT NULL,
    coverage_requirements JSONB NOT NULL,
    assumptions JSONB NOT NULL,
    priority INTEGER NOT NULL CHECK (priority >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS semantic_solver_job_owner_idx
    ON semantic_solver_job (document_ref, owner_ref, input_revision);

CREATE TABLE IF NOT EXISTS semantic_solver_receipt (
    receipt_ref TEXT PRIMARY KEY,
    job_ref TEXT NOT NULL REFERENCES semantic_solver_job(job_ref) ON DELETE RESTRICT,
    document_ref TEXT NOT NULL,
    owner_ref TEXT NOT NULL,
    input_revision BIGINT NOT NULL CHECK (input_revision >= 0),
    input_refs JSONB NOT NULL,
    rule_set_revision TEXT NOT NULL,
    proposal_refs JSONB NOT NULL,
    residuals JSONB NOT NULL,
    assumptions JSONB NOT NULL,
    coverage_requirements JSONB NOT NULL,
    metrics JSONB NOT NULL,
    backend_ref TEXT NOT NULL,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE CHECK (semantic_state_promoted = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_state_delta (
    document_ref TEXT NOT NULL,
    resulting_revision BIGINT NOT NULL CHECK (resulting_revision >= 0),
    prior_revision BIGINT NOT NULL CHECK (prior_revision >= 0),
    accepted_observation_refs JSONB NOT NULL,
    accepted_proposal_refs JSONB NOT NULL,
    changed_factor_refs JSONB NOT NULL,
    introduced_residual_refs JSONB NOT NULL,
    discharged_residual_refs JSONB NOT NULL,
    dirty_owner_refs JSONB NOT NULL,
    emitted_job_refs JSONB NOT NULL,
    PRIMARY KEY (document_ref, resulting_revision),
    CHECK (resulting_revision >= prior_revision)
);

CREATE TABLE IF NOT EXISTS semantic_materialized_reduction (
    graph_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 0),
    ledger_ref TEXT NOT NULL,
    proposal_count INTEGER NOT NULL CHECK (proposal_count >= 0),
    factor_refs JSONB NOT NULL,
    residual_refs JSONB NOT NULL,
    shared_graph_mutation BOOLEAN NOT NULL DEFAULT FALSE CHECK (shared_graph_mutation = FALSE),
    last_writer_wins BOOLEAN NOT NULL DEFAULT FALSE CHECK (last_writer_wins = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_region_boundary_summary (
    summary_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    stable_factor_refs JSONB NOT NULL,
    unresolved_external_refs JSONB NOT NULL,
    possible_cross_scope_hosts JSONB NOT NULL,
    definition_scope_obligations JSONB NOT NULL,
    coverage_notice_refs JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_fixed_point_certificate (
    certificate_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision >= 0),
    ledger_ref TEXT NOT NULL,
    materialized_graph_ref TEXT NOT NULL,
    local_fixed_point TEXT NOT NULL,
    unconsumed_observation_deltas INTEGER NOT NULL CHECK (unconsumed_observation_deltas >= 0),
    dirty_reduction_groups INTEGER NOT NULL CHECK (dirty_reduction_groups >= 0),
    pending_jobs INTEGER NOT NULL CHECK (pending_jobs >= 0),
    in_flight_jobs INTEGER NOT NULL CHECK (in_flight_jobs >= 0),
    unresolved_local_boundary_obligations INTEGER NOT NULL CHECK (unresolved_local_boundary_obligations >= 0),
    open_required_coverage_barriers INTEGER NOT NULL CHECK (open_required_coverage_barriers >= 0),
    unresolved_external_residuals JSONB NOT NULL,
    resource_limit_reached BOOLEAN NOT NULL,
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE CHECK (identity_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (local_fixed_point IN ('reached', 'not_reached')),
    CHECK (
        local_fixed_point <> 'reached'
        OR (
            unconsumed_observation_deltas = 0
            AND dirty_reduction_groups = 0
            AND pending_jobs = 0
            AND in_flight_jobs = 0
            AND unresolved_local_boundary_obligations = 0
            AND open_required_coverage_barriers = 0
            AND resource_limit_reached = FALSE
        )
    )
);

CREATE INDEX IF NOT EXISTS semantic_fixed_point_document_idx
    ON semantic_fixed_point_certificate (document_ref, revision DESC);

CREATE TABLE IF NOT EXISTS semantic_stage_timing (
    timing_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    stage TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    elapsed_ms BIGINT NOT NULL CHECK (elapsed_ms >= 0),
    backend_ref TEXT,
    input_nodes BIGINT CHECK (input_nodes IS NULL OR input_nodes >= 0),
    output_nodes BIGINT CHECK (output_nodes IS NULL OR output_nodes >= 0),
    input_edges BIGINT CHECK (input_edges IS NULL OR input_edges >= 0),
    output_edges BIGINT CHECK (output_edges IS NULL OR output_edges >= 0),
    proposals_generated BIGINT CHECK (proposals_generated IS NULL OR proposals_generated >= 0),
    duplicates_collapsed BIGINT CHECK (duplicates_collapsed IS NULL OR duplicates_collapsed >= 0),
    invalid_rejected BIGINT CHECK (invalid_rejected IS NULL OR invalid_rejected >= 0),
    alternatives_retained BIGINT CHECK (alternatives_retained IS NULL OR alternatives_retained >= 0),
    residuals_emitted BIGINT CHECK (residuals_emitted IS NULL OR residuals_emitted >= 0),
    tokens_processed BIGINT CHECK (tokens_processed IS NULL OR tokens_processed >= 0),
    tokens_per_second DOUBLE PRECISION,
    reduction_ratio DOUBLE PRECISION,
    reduction_efficiency_edges_per_second DOUBLE PRECISION,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, ordinal)
);

CREATE INDEX IF NOT EXISTS semantic_stage_timing_stage_idx
    ON semantic_stage_timing (document_ref, stage, elapsed_ms DESC);

COMMIT;
