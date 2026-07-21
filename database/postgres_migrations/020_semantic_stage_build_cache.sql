BEGIN;

CREATE TABLE IF NOT EXISTS semantic_stage_build_cache (
    stage_build_key TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    stage TEXT NOT NULL,
    contract_ref TEXT NOT NULL,
    input_refs JSONB NOT NULL,
    declaration_refs JSONB NOT NULL,
    output_ref TEXT NOT NULL,
    output_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (stage IN (
        'parser',
        'observation_projection',
        'base_proposals',
        'base_reduction',
        'composition_rule_set',
        'composition_reduction',
        'constraint_fixed_point',
        'legal_ir_projection'
    ))
);

CREATE INDEX IF NOT EXISTS semantic_stage_build_cache_document_idx
    ON semantic_stage_build_cache (document_ref, stage, created_at DESC);

CREATE TABLE IF NOT EXISTS semantic_stage_reuse_receipt (
    receipt_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    stage TEXT NOT NULL,
    stage_build_key TEXT NOT NULL
        REFERENCES semantic_stage_build_cache(stage_build_key) ON DELETE RESTRICT,
    reused BOOLEAN NOT NULL,
    source_output_ref TEXT NOT NULL,
    semantic_state_promoted BOOLEAN NOT NULL DEFAULT FALSE
        CHECK (semantic_state_promoted = FALSE),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS semantic_stage_reuse_receipt_document_idx
    ON semantic_stage_reuse_receipt (document_ref, stage, created_at DESC);

COMMIT;
