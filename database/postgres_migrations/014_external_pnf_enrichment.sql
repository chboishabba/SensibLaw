BEGIN;

CREATE SCHEMA IF NOT EXISTS enrichment;

CREATE TABLE IF NOT EXISTS enrichment.lookup_request (
    request_ref TEXT PRIMARY KEY,
    lookup_key_sha256 BYTEA NOT NULL,
    provider_ref TEXT NOT NULL,
    demand_kind_ref TEXT NOT NULL,
    language_ref TEXT NOT NULL,
    query_text TEXT NOT NULL,
    request_state_ref TEXT NOT NULL,
    cache_state_ref TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    request_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (lookup_key_sha256, provider_ref)
);

CREATE INDEX IF NOT EXISTS enrichment_lookup_request_pending_idx
    ON enrichment.lookup_request (provider_ref, request_state_ref, created_at)
    WHERE request_state_ref IN ('planned', 'retryable_failure');

CREATE TABLE IF NOT EXISTS enrichment.lookup_request_demand (
    request_ref TEXT NOT NULL
        REFERENCES enrichment.lookup_request(request_ref) ON DELETE CASCADE,
    demand_ref TEXT NOT NULL
        REFERENCES resolution.demand(demand_ref) ON DELETE CASCADE,
    PRIMARY KEY (request_ref, demand_ref)
);

CREATE TABLE IF NOT EXISTS enrichment.provider_request_receipt (
    request_receipt_ref TEXT PRIMARY KEY,
    request_ref TEXT NOT NULL
        REFERENCES enrichment.lookup_request(request_ref) ON DELETE CASCADE,
    provider_ref TEXT NOT NULL,
    operation_ref TEXT NOT NULL,
    request_state_ref TEXT NOT NULL,
    response_sha256 TEXT,
    detail TEXT,
    receipt_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS enrichment.provider_snapshot (
    snapshot_ref TEXT PRIMARY KEY,
    provider_ref TEXT NOT NULL,
    response_sha256 TEXT,
    snapshot_state_ref TEXT NOT NULL DEFAULT 'candidate_source',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    snapshot_sha256 BYTEA NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS enrichment.external_candidate (
    candidate_ref TEXT PRIMARY KEY,
    provider_ref TEXT NOT NULL,
    external_id TEXT NOT NULL,
    candidate_kind_ref TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    source_url TEXT,
    provider_score DOUBLE PRECISION,
    snapshot_ref TEXT REFERENCES enrichment.provider_snapshot(snapshot_ref),
    authority_state_ref TEXT NOT NULL CHECK (authority_state_ref = 'candidate_only'),
    candidate_sha256 BYTEA NOT NULL UNIQUE,
    UNIQUE (provider_ref, external_id, snapshot_ref)
);

CREATE INDEX IF NOT EXISTS enrichment_external_candidate_lookup_idx
    ON enrichment.external_candidate (provider_ref, external_id);

CREATE TABLE IF NOT EXISTS enrichment.external_candidate_alias (
    candidate_ref TEXT NOT NULL
        REFERENCES enrichment.external_candidate(candidate_ref) ON DELETE CASCADE,
    language_ref TEXT NOT NULL,
    alias_text TEXT NOT NULL,
    PRIMARY KEY (candidate_ref, language_ref, alias_text)
);

CREATE TABLE IF NOT EXISTS enrichment.external_candidate_type (
    candidate_ref TEXT NOT NULL
        REFERENCES enrichment.external_candidate(candidate_ref) ON DELETE CASCADE,
    type_ref TEXT NOT NULL,
    PRIMARY KEY (candidate_ref, type_ref)
);

CREATE TABLE IF NOT EXISTS enrichment.external_candidate_set (
    candidate_set_ref TEXT PRIMARY KEY,
    demand_ref TEXT NOT NULL REFERENCES resolution.demand(demand_ref) ON DELETE CASCADE,
    subject_ref TEXT NOT NULL,
    request_ref TEXT NOT NULL REFERENCES enrichment.lookup_request(request_ref),
    provider_ref TEXT NOT NULL,
    member_count INTEGER NOT NULL CHECK (member_count >= 0),
    authority_state_ref TEXT NOT NULL CHECK (authority_state_ref = 'candidate_only'),
    identity_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (identity_closed = FALSE),
    candidate_set_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (demand_ref, provider_ref, request_ref)
);

CREATE TABLE IF NOT EXISTS enrichment.external_candidate_set_member (
    candidate_set_ref TEXT NOT NULL
        REFERENCES enrichment.external_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    candidate_ref TEXT NOT NULL
        REFERENCES enrichment.external_candidate(candidate_ref),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (candidate_set_ref, candidate_ref),
    UNIQUE (candidate_set_ref, ordinal)
);

CREATE TABLE IF NOT EXISTS enrichment.external_candidate_assessment (
    candidate_set_ref TEXT NOT NULL
        REFERENCES enrichment.external_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    candidate_ref TEXT NOT NULL
        REFERENCES enrichment.external_candidate(candidate_ref),
    compatibility_state_ref TEXT NOT NULL,
    surface_score DOUBLE PRECISION NOT NULL,
    type_score DOUBLE PRECISION NOT NULL,
    context_score DOUBLE PRECISION NOT NULL,
    combined_score DOUBLE PRECISION NOT NULL,
    reasons TEXT[] NOT NULL DEFAULT '{}',
    assessment_sha256 BYTEA NOT NULL UNIQUE,
    PRIMARY KEY (candidate_set_ref, candidate_ref)
);

CREATE TABLE IF NOT EXISTS enrichment.external_candidate_set_residual (
    candidate_set_ref TEXT NOT NULL
        REFERENCES enrichment.external_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    residual_ref TEXT NOT NULL,
    PRIMARY KEY (candidate_set_ref, residual_ref)
);

CREATE TABLE IF NOT EXISTS enrichment.pressure_receipt (
    pressure_ref TEXT PRIMARY KEY,
    demand_ref TEXT NOT NULL REFERENCES resolution.demand(demand_ref) ON DELETE CASCADE,
    candidate_set_ref TEXT NOT NULL
        REFERENCES enrichment.external_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    before_total DOUBLE PRECISION NOT NULL,
    after_total DOUBLE PRECISION NOT NULL,
    monotone BOOLEAN NOT NULL,
    demand_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (demand_closed = FALSE),
    identity_closed BOOLEAN NOT NULL DEFAULT FALSE CHECK (identity_closed = FALSE),
    pressure_components JSONB NOT NULL,
    residual_transitions JSONB NOT NULL,
    receipt_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE VIEW enrichment.v_external_candidate_pressure AS
SELECT
    candidate_set.demand_ref,
    candidate_set.subject_ref,
    candidate_set.provider_ref,
    candidate_set.candidate_set_ref,
    candidate_set.member_count,
    pressure.before_total,
    pressure.after_total,
    pressure.monotone,
    demand.demand_state_ref,
    candidate_set.identity_closed
FROM enrichment.external_candidate_set AS candidate_set
JOIN enrichment.pressure_receipt AS pressure
  ON pressure.candidate_set_ref = candidate_set.candidate_set_ref
JOIN resolution.demand AS demand
  ON demand.demand_ref = candidate_set.demand_ref;

COMMIT;
