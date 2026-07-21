BEGIN;

CREATE TABLE IF NOT EXISTS semantic_supersession_notice (
    notice_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    replacement_pairs JSONB NOT NULL,
    reason_ref TEXT NOT NULL,
    evidence_refs JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS semantic_supersession_notice_document_idx
    ON semantic_supersession_notice (document_ref, created_at);

CREATE TABLE IF NOT EXISTS semantic_retraction_notice (
    notice_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    proposal_refs JSONB NOT NULL,
    receipt_refs JSONB NOT NULL,
    supersession_notice_ref TEXT NOT NULL
        REFERENCES semantic_supersession_notice(notice_ref) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_stale_solver_receipt (
    record_ref TEXT PRIMARY KEY,
    receipt_ref TEXT NOT NULL,
    job_ref TEXT NOT NULL,
    stale_input_refs JSONB NOT NULL,
    replacement_job_ref TEXT,
    supersession_notice_refs JSONB NOT NULL,
    proposal_outputs_admitted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (proposal_outputs_admitted = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_backpressure_event (
    document_ref TEXT NOT NULL,
    event_ordinal BIGINT NOT NULL CHECK (event_ordinal >= 0),
    delta_ref TEXT NOT NULL,
    admission_state TEXT NOT NULL,
    pending_jobs INTEGER NOT NULL CHECK (pending_jobs >= 0),
    in_flight_jobs INTEGER NOT NULL CHECK (in_flight_jobs >= 0),
    dirty_groups INTEGER NOT NULL CHECK (dirty_groups >= 0),
    branching_mass BIGINT NOT NULL CHECK (branching_mass >= 0),
    deferred_deltas INTEGER NOT NULL CHECK (deferred_deltas >= 0),
    paused BOOLEAN NOT NULL,
    reasons JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_ref, event_ordinal),
    CHECK (admission_state IN ('accepted', 'deferred', 'duplicate'))
);

CREATE TABLE IF NOT EXISTS semantic_constraint_work_item (
    work_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    constraint_ref TEXT NOT NULL,
    incident_factor_refs JSONB NOT NULL,
    triggering_factor_refs JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS semantic_constraint_work_item_document_idx
    ON semantic_constraint_work_item (document_ref, constraint_ref);

CREATE TABLE IF NOT EXISTS semantic_constraint_worklist_result (
    result_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    assessment_refs JSONB NOT NULL,
    work_refs JSONB NOT NULL,
    changed_factor_refs JSONB NOT NULL,
    fixed_point_rounds INTEGER NOT NULL CHECK (fixed_point_rounds >= 0),
    pending_work_items INTEGER NOT NULL DEFAULT 0
        CHECK (pending_work_items = 0),
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_document_region_coordinator (
    coordinator_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    region_summary_refs JSONB NOT NULL,
    region_certificate_refs JSONB NOT NULL,
    boundary_routes JSONB NOT NULL,
    discharged_boundary_refs JSONB NOT NULL,
    unresolved_boundary_refs JSONB NOT NULL,
    local_fixed_point TEXT NOT NULL,
    identity_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (identity_promoted = FALSE),
    legal_truth_closed BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (legal_truth_closed = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (local_fixed_point IN ('reached', 'not_reached')),
    CHECK (
        local_fixed_point <> 'reached'
        OR jsonb_array_length(unresolved_boundary_refs) = 0
    )
);

COMMIT;
