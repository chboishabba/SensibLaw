-- Generic compiler substrate. This is additive to the legal ontology: generic
-- document/PNF evidence never requires a legal_source, actor, or event row.

CREATE TABLE IF NOT EXISTS compiler_declaration (
    declaration_ref TEXT PRIMARY KEY,
    declaration_kind TEXT NOT NULL CHECK (declaration_kind IN (
        'grammar', 'type_system', 'relation_algebra', 'closure_contract', 'authority_policy'
    )),
    revision_sha256 TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (declaration_kind, revision_sha256)
);

CREATE TABLE IF NOT EXISTS compiler_document (
    document_ref TEXT PRIMARY KEY,
    content_sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL,
    canonical_text TEXT NOT NULL,
    canonicalisation_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (content_sha256, media_type, canonicalisation_ref)
);

CREATE TABLE IF NOT EXISTS compiler_build (
    build_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES compiler_document(document_ref),
    build_stage TEXT NOT NULL CHECK (build_stage IN (
        'canonicalisation', 'tokenisation', 'annotation', 'reduction',
        'pnf_construction', 'local_meet_planning', 'typed_meet',
        'factor_refinement', 'demand_projection'
    )),
    build_key_sha256 TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    output_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, build_stage, build_key_sha256)
);

CREATE TABLE IF NOT EXISTS compiler_build_dependency (
    build_ref TEXT NOT NULL REFERENCES compiler_build(build_ref) ON DELETE CASCADE,
    dependency_kind TEXT NOT NULL CHECK (dependency_kind IN ('build', 'declaration', 'artifact')),
    dependency_ref TEXT NOT NULL,
    PRIMARY KEY (build_ref, dependency_kind, dependency_ref)
);

CREATE TABLE IF NOT EXISTS compiler_annotation_layer (
    layer_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES compiler_document(document_ref),
    build_ref TEXT NOT NULL REFERENCES compiler_build(build_ref),
    tokenizer_ref TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE (document_ref, tokenizer_ref, text_sha256)
);

CREATE TABLE IF NOT EXISTS compiler_annotation_token (
    layer_ref TEXT NOT NULL REFERENCES compiler_annotation_layer(layer_ref) ON DELETE CASCADE,
    token_index INTEGER NOT NULL CHECK (token_index >= 0),
    annotation_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY (layer_ref, token_index, annotation_type)
);

CREATE TABLE IF NOT EXISTS compiler_annotation_span (
    span_ref TEXT PRIMARY KEY,
    layer_ref TEXT NOT NULL REFERENCES compiler_annotation_layer(layer_ref) ON DELETE CASCADE,
    start_token INTEGER NOT NULL CHECK (start_token >= 0),
    end_token INTEGER NOT NULL CHECK (end_token > start_token),
    annotation_type TEXT NOT NULL,
    payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS compiler_annotation_span_layer_range_idx
    ON compiler_annotation_span (layer_ref, start_token, end_token);

CREATE TABLE IF NOT EXISTS compiler_annotation_relation (
    relation_ref TEXT PRIMARY KEY,
    layer_ref TEXT NOT NULL REFERENCES compiler_annotation_layer(layer_ref) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    left_ref TEXT NOT NULL,
    right_ref TEXT NOT NULL,
    payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS compiler_annotation_relation_layer_type_idx
    ON compiler_annotation_relation (layer_ref, relation_type);

CREATE TABLE IF NOT EXISTS compiler_pnf_graph (
    graph_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES compiler_document(document_ref),
    build_ref TEXT NOT NULL REFERENCES compiler_build(build_ref),
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS compiler_pnf_factor (
    factor_ref TEXT PRIMARY KEY,
    graph_ref TEXT NOT NULL REFERENCES compiler_pnf_graph(graph_ref) ON DELETE CASCADE,
    factor_type TEXT NOT NULL,
    payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS compiler_pnf_factor_graph_type_idx
    ON compiler_pnf_factor (graph_ref, factor_type);

CREATE TABLE IF NOT EXISTS compiler_factor_revision (
    factor_revision_ref TEXT PRIMARY KEY,
    factor_ref TEXT NOT NULL REFERENCES compiler_pnf_factor(factor_ref) ON DELETE CASCADE,
    prior_factor_revision_ref TEXT REFERENCES compiler_factor_revision(factor_revision_ref),
    revision_sha256 TEXT NOT NULL,
    closure_state TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (factor_ref, revision_sha256)
);

CREATE TABLE IF NOT EXISTS compiler_typed_meet (
    meet_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES compiler_document(document_ref),
    left_ref TEXT NOT NULL,
    right_ref TEXT NOT NULL,
    meet_type TEXT NOT NULL,
    meet_state TEXT NOT NULL,
    payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS compiler_typed_meet_document_state_idx
    ON compiler_typed_meet (document_ref, meet_state);

CREATE TABLE IF NOT EXISTS compiler_factor_refinement (
    refinement_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES compiler_document(document_ref),
    factor_ref TEXT NOT NULL REFERENCES compiler_pnf_factor(factor_ref),
    prior_factor_revision_ref TEXT NOT NULL REFERENCES compiler_factor_revision(factor_revision_ref),
    resulting_factor_revision_ref TEXT NOT NULL REFERENCES compiler_factor_revision(factor_revision_ref),
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS compiler_resolution_demand (
    demand_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES compiler_document(document_ref),
    factor_revision_ref TEXT NOT NULL REFERENCES compiler_factor_revision(factor_revision_ref),
    subject_kind TEXT NOT NULL,
    formal_role TEXT,
    semantic_key_sha256 TEXT NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE (factor_revision_ref, semantic_key_sha256)
);
CREATE INDEX IF NOT EXISTS compiler_resolution_demand_key_idx
    ON compiler_resolution_demand (semantic_key_sha256);
