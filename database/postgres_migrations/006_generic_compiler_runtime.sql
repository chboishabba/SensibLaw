BEGIN;

CREATE SCHEMA IF NOT EXISTS corpus;
CREATE SCHEMA IF NOT EXISTS language;
CREATE SCHEMA IF NOT EXISTS algebra;
CREATE SCHEMA IF NOT EXISTS pnf;
CREATE SCHEMA IF NOT EXISTS evidence;
CREATE SCHEMA IF NOT EXISTS resolution;
CREATE SCHEMA IF NOT EXISTS execution;
CREATE SCHEMA IF NOT EXISTS governance;

-- Generic declarations. Domain, registry, grammar, type, relation, closure, and
-- authority knowledge enters as versioned data rather than schema branches.
CREATE TABLE IF NOT EXISTS algebra.declaration (
    declaration_ref text PRIMARY KEY,
    declaration_kind text NOT NULL,
    version_ref text NOT NULL,
    content_sha256 bytea NOT NULL,
    payload bytea,
    media_type text,
    UNIQUE (declaration_kind, version_ref, content_sha256)
);

CREATE TABLE IF NOT EXISTS corpus.binary_content (
    content_ref text PRIMARY KEY,
    content_sha256 bytea NOT NULL UNIQUE,
    media_type text NOT NULL,
    compression_ref text,
    payload bytea NOT NULL,
    uncompressed_byte_length bigint NOT NULL CHECK (uncompressed_byte_length >= 0)
);

CREATE TABLE IF NOT EXISTS corpus.canonical_content (
    canonical_ref text PRIMARY KEY,
    content_sha256 bytea NOT NULL,
    encoding_ref text NOT NULL,
    normalization_ref text NOT NULL,
    compression_ref text,
    payload bytea NOT NULL,
    uncompressed_byte_length bigint NOT NULL CHECK (uncompressed_byte_length >= 0),
    UNIQUE (content_sha256, encoding_ref, normalization_ref)
);

CREATE TABLE IF NOT EXISTS corpus.document (
    document_ref text PRIMARY KEY,
    source_content_ref text REFERENCES corpus.binary_content(content_ref),
    canonical_ref text NOT NULL REFERENCES corpus.canonical_content(canonical_ref),
    media_type text NOT NULL,
    adapter_ref text NOT NULL,
    adapter_version text NOT NULL,
    compiler_context_ref text NOT NULL,
    document_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS corpus.corpus (
    corpus_ref text PRIMARY KEY,
    root_ref text NOT NULL,
    compiler_context_ref text NOT NULL,
    manifest_sha256 bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corpus.document_occurrence (
    corpus_ref text NOT NULL REFERENCES corpus.corpus(corpus_ref) ON DELETE CASCADE,
    relative_path text NOT NULL,
    document_ref text NOT NULL REFERENCES corpus.document(document_ref),
    occurrence_state text NOT NULL,
    PRIMARY KEY (corpus_ref, relative_path)
);

CREATE TABLE IF NOT EXISTS corpus.span (
    span_ref text PRIMARY KEY,
    document_ref text NOT NULL REFERENCES corpus.document(document_ref) ON DELETE CASCADE,
    start_char integer NOT NULL CHECK (start_char >= 0),
    end_char integer NOT NULL CHECK (end_char > start_char),
    start_token integer,
    end_token integer,
    span_type_ref text NOT NULL,
    CHECK ((start_token IS NULL AND end_token IS NULL) OR
           (start_token >= 0 AND end_token > start_token))
);

-- Logical dictionary identity is separate from physical compressed symbols.
CREATE TABLE IF NOT EXISTS language.lexeme (
    lexeme_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    language_ref text NOT NULL DEFAULT 'und',
    normalized_text text NOT NULL,
    lexical_kind_ref text NOT NULL,
    UNIQUE (language_ref, normalized_text, lexical_kind_ref)
);

CREATE TABLE IF NOT EXISTS language.tokenizer_run (
    tokenizer_run_ref text PRIMARY KEY,
    document_ref text NOT NULL REFERENCES corpus.document(document_ref) ON DELETE CASCADE,
    tokenizer_ref text NOT NULL,
    tokenizer_version text NOT NULL,
    token_count integer NOT NULL CHECK (token_count >= 0),
    output_sha256 bytea NOT NULL,
    UNIQUE (document_ref, tokenizer_ref, tokenizer_version, output_sha256)
);

CREATE TABLE IF NOT EXISTS language.codec (
    codec_ref text PRIMARY KEY,
    codec_kind_ref text NOT NULL,
    codec_version text NOT NULL,
    corpus_ref text REFERENCES corpus.corpus(corpus_ref),
    dictionary_sha256 bytea NOT NULL
);

CREATE TABLE IF NOT EXISTS language.codec_symbol (
    codec_ref text NOT NULL REFERENCES language.codec(codec_ref) ON DELETE CASCADE,
    symbol_code integer NOT NULL CHECK (symbol_code >= 0),
    lexeme_id integer NOT NULL REFERENCES language.lexeme(lexeme_id),
    frequency_rank integer NOT NULL CHECK (frequency_rank >= 0),
    PRIMARY KEY (codec_ref, symbol_code),
    UNIQUE (codec_ref, lexeme_id),
    UNIQUE (codec_ref, frequency_rank)
);

CREATE TABLE IF NOT EXISTS language.token_stream_chunk (
    tokenizer_run_ref text NOT NULL REFERENCES language.tokenizer_run(tokenizer_run_ref) ON DELETE CASCADE,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    first_token_index integer NOT NULL CHECK (first_token_index >= 0),
    token_count integer NOT NULL CHECK (token_count > 0),
    codec_ref text NOT NULL REFERENCES language.codec(codec_ref),
    encoded_symbols bytea NOT NULL,
    encoded_offsets bytea,
    content_sha256 bytea NOT NULL,
    PRIMARY KEY (tokenizer_run_ref, chunk_index),
    UNIQUE (tokenizer_run_ref, first_token_index)
);

-- Sparse token rows are an optional query projection, not the canonical dense codec.
CREATE TABLE IF NOT EXISTS language.token_projection (
    tokenizer_run_ref text NOT NULL REFERENCES language.tokenizer_run(tokenizer_run_ref) ON DELETE CASCADE,
    token_index integer NOT NULL CHECK (token_index >= 0),
    lexeme_id integer NOT NULL REFERENCES language.lexeme(lexeme_id),
    span_ref text REFERENCES corpus.span(span_ref),
    surface_text text,
    PRIMARY KEY (tokenizer_run_ref, token_index)
);

CREATE TABLE IF NOT EXISTS language.posting_block (
    codec_ref text NOT NULL REFERENCES language.codec(codec_ref) ON DELETE CASCADE,
    lexeme_id integer NOT NULL REFERENCES language.lexeme(lexeme_id),
    block_index integer NOT NULL CHECK (block_index >= 0),
    encoded_document_positions bytea NOT NULL,
    content_sha256 bytea NOT NULL,
    PRIMARY KEY (codec_ref, lexeme_id, block_index)
);

CREATE TABLE IF NOT EXISTS language.lemma_candidate (
    tokenizer_run_ref text NOT NULL REFERENCES language.tokenizer_run(tokenizer_run_ref) ON DELETE CASCADE,
    token_index integer NOT NULL CHECK (token_index >= 0),
    lemma_lexeme_id integer NOT NULL REFERENCES language.lexeme(lexeme_id),
    derivation_ref text NOT NULL,
    annotation_backend_ref text NOT NULL,
    candidate_state text NOT NULL DEFAULT 'alternative',
    PRIMARY KEY (tokenizer_run_ref, token_index, lemma_lexeme_id, derivation_ref)
);

CREATE TABLE IF NOT EXISTS language.annotation_layer (
    annotation_layer_ref text PRIMARY KEY,
    document_ref text NOT NULL REFERENCES corpus.document(document_ref) ON DELETE CASCADE,
    backend_ref text NOT NULL,
    backend_version text NOT NULL,
    input_sha256 bytea NOT NULL,
    output_sha256 bytea NOT NULL,
    UNIQUE (document_ref, backend_ref, backend_version, output_sha256)
);

CREATE TABLE IF NOT EXISTS language.annotation_node (
    annotation_node_ref text PRIMARY KEY,
    annotation_layer_ref text NOT NULL REFERENCES language.annotation_layer(annotation_layer_ref) ON DELETE CASCADE,
    annotation_type_ref text NOT NULL,
    span_ref text REFERENCES corpus.span(span_ref),
    value_ref text,
    attributes bytea,
    attributes_media_type text
);

CREATE TABLE IF NOT EXISTS language.annotation_relation (
    annotation_relation_ref text PRIMARY KEY,
    annotation_layer_ref text NOT NULL REFERENCES language.annotation_layer(annotation_layer_ref) ON DELETE CASCADE,
    relation_type_ref text NOT NULL,
    source_node_ref text NOT NULL REFERENCES language.annotation_node(annotation_node_ref),
    target_node_ref text NOT NULL REFERENCES language.annotation_node(annotation_node_ref),
    attributes bytea,
    attributes_media_type text
);

CREATE TABLE IF NOT EXISTS algebra.alternative (
    alternative_ref text PRIMARY KEY,
    type_ref text NOT NULL,
    value_ref text,
    value_literal text,
    authority_state_ref text NOT NULL,
    alternative_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS algebra.alternative_derivation (
    alternative_ref text NOT NULL REFERENCES algebra.alternative(alternative_ref) ON DELETE CASCADE,
    derivation_ref text NOT NULL,
    PRIMARY KEY (alternative_ref, derivation_ref)
);

CREATE TABLE IF NOT EXISTS algebra.factor (
    factor_ref text PRIMARY KEY,
    document_ref text REFERENCES corpus.document(document_ref),
    factor_type_ref text NOT NULL,
    closure_state_ref text NOT NULL,
    factor_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS algebra.factor_alternative (
    factor_ref text NOT NULL REFERENCES algebra.factor(factor_ref) ON DELETE CASCADE,
    alternative_ref text NOT NULL REFERENCES algebra.alternative(alternative_ref),
    alternative_state_ref text NOT NULL,
    PRIMARY KEY (factor_ref, alternative_ref)
);

CREATE TABLE IF NOT EXISTS algebra.constraint (
    constraint_ref text PRIMARY KEY,
    constraint_type_ref text NOT NULL,
    required boolean NOT NULL,
    declaration_ref text REFERENCES algebra.declaration(declaration_ref),
    constraint_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS algebra.constraint_factor (
    constraint_ref text NOT NULL REFERENCES algebra.constraint(constraint_ref) ON DELETE CASCADE,
    factor_ref text NOT NULL REFERENCES algebra.factor(factor_ref) ON DELETE CASCADE,
    factor_role_ref text NOT NULL,
    PRIMARY KEY (constraint_ref, factor_ref, factor_role_ref)
);

CREATE TABLE IF NOT EXISTS algebra.relation (
    relation_ref text PRIMARY KEY,
    relation_type_ref text NOT NULL,
    left_ref text NOT NULL,
    right_ref text NOT NULL,
    relation_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS algebra.residual (
    residual_ref text PRIMARY KEY,
    target_ref text NOT NULL,
    residual_type_ref text NOT NULL,
    residual_state_ref text NOT NULL,
    residual_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS algebra.pressure_assessment (
    pressure_ref text PRIMARY KEY,
    target_ref text NOT NULL,
    pressure_kind_ref text NOT NULL CHECK (pressure_kind_ref IN ('coverage', 'closure')),
    pressure_state_ref text NOT NULL,
    assessment_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS algebra.pressure_reason (
    pressure_ref text NOT NULL REFERENCES algebra.pressure_assessment(pressure_ref) ON DELETE CASCADE,
    reason_ref text NOT NULL,
    PRIMARY KEY (pressure_ref, reason_ref)
);

CREATE TABLE IF NOT EXISTS pnf.graph (
    graph_ref text PRIMARY KEY,
    document_ref text NOT NULL REFERENCES corpus.document(document_ref) ON DELETE CASCADE,
    graph_type_ref text NOT NULL,
    schema_version_ref text NOT NULL,
    closure_state_ref text NOT NULL,
    graph_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS pnf.graph_factor (
    graph_ref text NOT NULL REFERENCES pnf.graph(graph_ref) ON DELETE CASCADE,
    factor_ref text NOT NULL REFERENCES algebra.factor(factor_ref),
    graph_role_ref text NOT NULL,
    PRIMARY KEY (graph_ref, factor_ref, graph_role_ref)
);

CREATE TABLE IF NOT EXISTS pnf.graph_constraint (
    graph_ref text NOT NULL REFERENCES pnf.graph(graph_ref) ON DELETE CASCADE,
    constraint_ref text NOT NULL REFERENCES algebra.constraint(constraint_ref),
    PRIMARY KEY (graph_ref, constraint_ref)
);

CREATE TABLE IF NOT EXISTS evidence.snapshot (
    snapshot_ref text PRIMARY KEY,
    registry_ref text NOT NULL,
    external_ref text NOT NULL,
    revision_ref text NOT NULL,
    formal_type_ref text,
    payload_sha256 bytea NOT NULL,
    raw_content_ref text REFERENCES corpus.binary_content(content_ref),
    fetched_at timestamptz,
    UNIQUE (registry_ref, external_ref, revision_ref)
);

CREATE TABLE IF NOT EXISTS evidence.assertion (
    assertion_ref text PRIMARY KEY,
    snapshot_ref text REFERENCES evidence.snapshot(snapshot_ref) ON DELETE CASCADE,
    subject_ref text NOT NULL,
    predicate_ref text NOT NULL,
    object_ref text,
    object_literal text,
    assertion_role_ref text NOT NULL,
    assertion_sha256 bytea NOT NULL UNIQUE,
    CHECK ((object_ref IS NULL) <> (object_literal IS NULL))
);

CREATE TABLE IF NOT EXISTS evidence.local_evidence (
    evidence_ref text PRIMARY KEY,
    document_ref text NOT NULL REFERENCES corpus.document(document_ref) ON DELETE CASCADE,
    evidence_type_ref text NOT NULL,
    relation_ref text,
    evidence_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS evidence.local_evidence_subject (
    evidence_ref text NOT NULL REFERENCES evidence.local_evidence(evidence_ref) ON DELETE CASCADE,
    subject_ref text NOT NULL,
    PRIMARY KEY (evidence_ref, subject_ref)
);

CREATE TABLE IF NOT EXISTS resolution.demand (
    demand_ref text PRIMARY KEY,
    factor_ref text NOT NULL REFERENCES algebra.factor(factor_ref) ON DELETE CASCADE,
    subject_kind_ref text NOT NULL,
    formal_role_ref text,
    scope_ref text NOT NULL,
    semantic_key_sha256 bytea NOT NULL,
    budget_class_ref text NOT NULL,
    demand_state_ref text NOT NULL,
    UNIQUE (semantic_key_sha256, factor_ref)
);

CREATE TABLE IF NOT EXISTS resolution.demand_facet (
    demand_ref text NOT NULL REFERENCES resolution.demand(demand_ref) ON DELETE CASCADE,
    facet_ref text NOT NULL,
    PRIMARY KEY (demand_ref, facet_ref)
);

CREATE TABLE IF NOT EXISTS resolution.typed_meet (
    meet_ref text PRIMARY KEY,
    left_ref text NOT NULL,
    right_ref text NOT NULL,
    meet_type_ref text NOT NULL,
    meet_state_ref text NOT NULL,
    meet_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS resolution.meet_evidence (
    meet_ref text NOT NULL REFERENCES resolution.typed_meet(meet_ref) ON DELETE CASCADE,
    evidence_ref text NOT NULL,
    PRIMARY KEY (meet_ref, evidence_ref)
);

CREATE TABLE IF NOT EXISTS resolution.meet_residual (
    meet_ref text NOT NULL REFERENCES resolution.typed_meet(meet_ref) ON DELETE CASCADE,
    residual_ref text NOT NULL REFERENCES algebra.residual(residual_ref),
    PRIMARY KEY (meet_ref, residual_ref)
);

CREATE TABLE IF NOT EXISTS resolution.assessment (
    assessment_ref text PRIMARY KEY,
    subject_ref text NOT NULL,
    candidate_ref text NOT NULL,
    outcome_ref text NOT NULL,
    assessment_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS resolution.assessment_coordinate (
    assessment_ref text NOT NULL REFERENCES resolution.assessment(assessment_ref) ON DELETE CASCADE,
    coordinate_type_ref text NOT NULL,
    meet_ref text NOT NULL REFERENCES resolution.typed_meet(meet_ref),
    PRIMARY KEY (assessment_ref, coordinate_type_ref)
);

CREATE TABLE IF NOT EXISTS resolution.refinement (
    refinement_ref text PRIMARY KEY,
    prior_factor_ref text NOT NULL REFERENCES algebra.factor(factor_ref),
    resulting_factor_ref text NOT NULL REFERENCES algebra.factor(factor_ref),
    assessment_ref text REFERENCES resolution.assessment(assessment_ref),
    refinement_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS resolution.refinement_alternative_transition (
    refinement_ref text NOT NULL REFERENCES resolution.refinement(refinement_ref) ON DELETE CASCADE,
    alternative_ref text NOT NULL REFERENCES algebra.alternative(alternative_ref),
    transition_type_ref text NOT NULL CHECK (transition_type_ref IN ('added', 'retained', 'rejected')),
    PRIMARY KEY (refinement_ref, alternative_ref, transition_type_ref)
);

CREATE TABLE IF NOT EXISTS resolution.refinement_residual_transition (
    refinement_ref text NOT NULL REFERENCES resolution.refinement(refinement_ref) ON DELETE CASCADE,
    residual_ref text NOT NULL,
    prior_state_ref text,
    resulting_state_ref text,
    PRIMARY KEY (refinement_ref, residual_ref)
);

CREATE TABLE IF NOT EXISTS execution.operation (
    operation_ref text NOT NULL,
    operation_version text NOT NULL,
    PRIMARY KEY (operation_ref, operation_version)
);

CREATE TABLE IF NOT EXISTS execution.build (
    build_ref text PRIMARY KEY,
    operation_ref text NOT NULL,
    operation_version text NOT NULL,
    build_key_sha256 bytea NOT NULL UNIQUE,
    output_ref text NOT NULL,
    build_state_ref text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (operation_ref, operation_version)
        REFERENCES execution.operation(operation_ref, operation_version)
);

CREATE TABLE IF NOT EXISTS execution.build_input (
    build_ref text NOT NULL REFERENCES execution.build(build_ref) ON DELETE CASCADE,
    input_ref text NOT NULL,
    input_role_ref text NOT NULL,
    PRIMARY KEY (build_ref, input_ref, input_role_ref)
);

CREATE TABLE IF NOT EXISTS execution.dependency (
    dependent_ref text NOT NULL,
    prerequisite_ref text NOT NULL,
    operation_ref text NOT NULL,
    operation_version text NOT NULL,
    PRIMARY KEY (dependent_ref, prerequisite_ref, operation_ref, operation_version)
);

CREATE TABLE IF NOT EXISTS execution.schedule (
    schedule_ref text PRIMARY KEY,
    semantic_key_sha256 bytea NOT NULL,
    backend_ref text,
    schedule_state_ref text NOT NULL,
    batch_ref text,
    rate_limit_class_ref text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution.schedule_demand (
    schedule_ref text NOT NULL REFERENCES execution.schedule(schedule_ref) ON DELETE CASCADE,
    demand_ref text NOT NULL REFERENCES resolution.demand(demand_ref),
    PRIMARY KEY (schedule_ref, demand_ref)
);

CREATE TABLE IF NOT EXISTS execution.failure_receipt (
    failure_ref text PRIMARY KEY,
    target_ref text NOT NULL,
    phase_ref text NOT NULL,
    failure_type_ref text NOT NULL,
    detail text,
    failure_sha256 bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS governance.decision (
    decision_ref text PRIMARY KEY,
    target_ref text NOT NULL,
    decision_type_ref text NOT NULL,
    outcome_ref text NOT NULL CHECK (outcome_ref IN ('promote', 'hold', 'abstain', 'audit')),
    editing_authority boolean NOT NULL DEFAULT false,
    decision_sha256 bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS resolution_demand_open_idx
    ON resolution.demand (subject_kind_ref, formal_role_ref, budget_class_ref)
    WHERE demand_state_ref = 'open';
CREATE INDEX IF NOT EXISTS algebra_factor_open_idx
    ON algebra.factor (factor_type_ref, closure_state_ref)
    WHERE closure_state_ref NOT IN ('closed', 'locally_closed', 'not_required');
CREATE INDEX IF NOT EXISTS evidence_assertion_spo_idx
    ON evidence.assertion (subject_ref, predicate_ref, object_ref);
CREATE INDEX IF NOT EXISTS execution_dependency_prerequisite_idx
    ON execution.dependency (prerequisite_ref);
CREATE INDEX IF NOT EXISTS language_lexeme_norm_idx
    ON language.lexeme (language_ref, normalized_text);

CREATE OR REPLACE VIEW pnf.v_document_pnf AS
SELECT
    g.document_ref,
    g.graph_ref,
    g.closure_state_ref AS graph_closure_state,
    f.factor_ref,
    f.factor_type_ref,
    f.closure_state_ref AS factor_closure_state,
    fa.alternative_ref,
    a.type_ref,
    a.value_ref,
    a.value_literal,
    fa.alternative_state_ref
FROM pnf.graph AS g
JOIN pnf.graph_factor AS gf ON gf.graph_ref = g.graph_ref
JOIN algebra.factor AS f ON f.factor_ref = gf.factor_ref
LEFT JOIN algebra.factor_alternative AS fa ON fa.factor_ref = f.factor_ref
LEFT JOIN algebra.alternative AS a ON a.alternative_ref = fa.alternative_ref;

CREATE OR REPLACE VIEW resolution.v_unresolved_demand AS
SELECT
    o.corpus_ref,
    d.document_ref,
    rd.demand_ref,
    rd.factor_ref,
    rd.subject_kind_ref,
    rd.formal_role_ref,
    rd.scope_ref,
    rd.semantic_key_sha256,
    rd.budget_class_ref,
    rd.demand_state_ref
FROM resolution.demand AS rd
JOIN algebra.factor AS f ON f.factor_ref = rd.factor_ref
JOIN corpus.document AS d ON d.document_ref = f.document_ref
JOIN corpus.document_occurrence AS o ON o.document_ref = d.document_ref
WHERE rd.demand_state_ref IN ('open', 'not_evaluated', 'budget_exhausted');

CREATE OR REPLACE VIEW corpus.v_document_summary AS
SELECT
    d.document_ref,
    count(DISTINCT f.factor_ref) AS factor_count,
    count(DISTINCT f.factor_ref) FILTER (
        WHERE f.closure_state_ref IN ('closed', 'locally_closed', 'not_required')
    ) AS closed_factor_count,
    count(DISTINCT r.residual_ref) FILTER (
        WHERE r.residual_state_ref NOT IN ('closed', 'discharged')
    ) AS open_residual_count,
    count(DISTINCT rd.demand_ref) FILTER (
        WHERE rd.demand_state_ref IN ('open', 'not_evaluated', 'budget_exhausted')
    ) AS unresolved_demand_count
FROM corpus.document AS d
LEFT JOIN algebra.factor AS f ON f.document_ref = d.document_ref
LEFT JOIN algebra.residual AS r ON r.target_ref = f.factor_ref
LEFT JOIN resolution.demand AS rd ON rd.factor_ref = f.factor_ref
GROUP BY d.document_ref;

CREATE OR REPLACE VIEW governance.v_review_queue AS
SELECT decision_ref, target_ref, decision_type_ref, outcome_ref, created_at
FROM governance.decision
WHERE outcome_ref IN ('hold', 'audit');

CREATE OR REPLACE VIEW execution.v_dependency_staleness AS
SELECT dep.dependent_ref, dep.prerequisite_ref, dep.operation_ref, dep.operation_version
FROM execution.dependency AS dep
LEFT JOIN execution.build AS b ON b.output_ref = dep.dependent_ref
WHERE b.build_ref IS NULL OR b.build_state_ref <> 'satisfied';

COMMIT;
