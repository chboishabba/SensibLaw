BEGIN;

-- spaCy owns one bounded mutable Doc at a time. PostgreSQL owns the durable,
-- typed parser observations. No parser state, receipt, cursor, event, or cache
-- descriptor is represented by JSON/JSONB.

CREATE TABLE IF NOT EXISTS execution.semantic_parser_source (
    source_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    content_sha256 BYTEA NOT NULL,
    byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
    encoding_ref TEXT NOT NULL,
    locator TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, document_ref, content_sha256)
);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_partition (
    partition_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    source_ref TEXT NOT NULL REFERENCES execution.semantic_parser_source(source_ref) ON DELETE RESTRICT,
    parser_contract_ref TEXT NOT NULL,
    partition_kind TEXT NOT NULL CHECK (partition_kind IN ('structural', 'boundary_repair')),
    sequence_no BIGINT NOT NULL CHECK (sequence_no >= 0),
    owner_start_char BIGINT NOT NULL CHECK (owner_start_char >= 0),
    owner_end_char BIGINT NOT NULL CHECK (owner_end_char > owner_start_char),
    context_start_char BIGINT NOT NULL CHECK (context_start_char >= 0),
    context_end_char BIGINT NOT NULL CHECK (context_end_char > context_start_char),
    repair_depth INTEGER NOT NULL DEFAULT 0 CHECK (repair_depth >= 0),
    resolves_obligation_ref TEXT,
    state TEXT NOT NULL DEFAULT 'ready'
        CHECK (state IN ('ready', 'leased', 'completed', 'failed')),
    lease_owner TEXT,
    lease_token TEXT,
    lease_epoch BIGINT NOT NULL DEFAULT 0 CHECK (lease_epoch >= 0),
    lease_expires_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    worker_pid BIGINT,
    backend_pid INTEGER,
    sentence_count BIGINT NOT NULL DEFAULT 0 CHECK (sentence_count >= 0),
    token_count BIGINT NOT NULL DEFAULT 0 CHECK (token_count >= 0),
    entity_count BIGINT NOT NULL DEFAULT 0 CHECK (entity_count >= 0),
    boundary_obligation_count BIGINT NOT NULL DEFAULT 0
        CHECK (boundary_obligation_count >= 0),
    elapsed_ns BIGINT,
    completed_at TIMESTAMPTZ,
    last_error_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (context_start_char <= owner_start_char),
    CHECK (context_end_char >= owner_end_char),
    UNIQUE (run_ref, sequence_no)
);

CREATE INDEX IF NOT EXISTS semantic_parser_partition_ready_idx
    ON execution.semantic_parser_partition (run_ref, state, sequence_no)
    WHERE state IN ('ready', 'leased');

CREATE TABLE IF NOT EXISTS execution.semantic_parser_attempt (
    attempt_ref TEXT PRIMARY KEY,
    partition_ref TEXT NOT NULL REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE CASCADE,
    worker_ref TEXT NOT NULL,
    worker_pid BIGINT NOT NULL,
    backend_pid INTEGER,
    lease_token TEXT NOT NULL,
    lease_epoch BIGINT NOT NULL CHECK (lease_epoch > 0),
    state TEXT NOT NULL CHECK (state IN ('leased', 'completed', 'stale', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    error_reason TEXT,
    UNIQUE (partition_ref, lease_epoch)
);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_symbol (
    symbol_ref TEXT PRIMARY KEY,
    symbol_kind TEXT NOT NULL CHECK (
        symbol_kind IN (
            'orth', 'lemma', 'pos', 'tag', 'dependency',
            'morph_feature', 'morph_value', 'entity_type', 'pipeline_component'
        )
    ),
    symbol_text TEXT NOT NULL,
    UNIQUE (symbol_kind, symbol_text)
);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_sentence (
    sentence_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    partition_ref TEXT NOT NULL REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE RESTRICT,
    local_sentence_ordinal INTEGER NOT NULL CHECK (local_sentence_ordinal >= 0),
    start_char BIGINT NOT NULL CHECK (start_char >= 0),
    end_char BIGINT NOT NULL CHECK (end_char > start_char),
    segmentation_contract_ref TEXT NOT NULL,
    ownership_state TEXT NOT NULL CHECK (ownership_state = 'owned'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, document_ref, segmentation_contract_ref, start_char, end_char)
);

CREATE INDEX IF NOT EXISTS semantic_parser_sentence_document_idx
    ON execution.semantic_parser_sentence (run_ref, document_ref, start_char, end_char);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_token (
    token_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    partition_ref TEXT NOT NULL REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE RESTRICT,
    sentence_ref TEXT NOT NULL REFERENCES execution.semantic_parser_sentence(sentence_ref) ON DELETE CASCADE,
    local_token_ordinal INTEGER NOT NULL CHECK (local_token_ordinal >= 0),
    start_char BIGINT NOT NULL CHECK (start_char >= 0),
    end_char BIGINT NOT NULL CHECK (end_char > start_char),
    orth_ref TEXT NOT NULL REFERENCES execution.semantic_parser_symbol(symbol_ref) ON DELETE RESTRICT,
    lemma_ref TEXT REFERENCES execution.semantic_parser_symbol(symbol_ref) ON DELETE RESTRICT,
    pos_ref TEXT REFERENCES execution.semantic_parser_symbol(symbol_ref) ON DELETE RESTRICT,
    tag_ref TEXT REFERENCES execution.semantic_parser_symbol(symbol_ref) ON DELETE RESTRICT,
    dependency_ref TEXT REFERENCES execution.semantic_parser_symbol(symbol_ref) ON DELETE RESTRICT,
    head_token_ref TEXT,
    head_start_char BIGINT,
    head_end_char BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sentence_ref, local_token_ordinal),
    UNIQUE (run_ref, document_ref, start_char, end_char)
);

CREATE INDEX IF NOT EXISTS semantic_parser_token_sentence_idx
    ON execution.semantic_parser_token (sentence_ref, local_token_ordinal);
CREATE INDEX IF NOT EXISTS semantic_parser_token_span_idx
    ON execution.semantic_parser_token (run_ref, document_ref, start_char, end_char);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_token_morphology (
    token_ref TEXT NOT NULL REFERENCES execution.semantic_parser_token(token_ref) ON DELETE CASCADE,
    feature_ref TEXT NOT NULL REFERENCES execution.semantic_parser_symbol(symbol_ref) ON DELETE RESTRICT,
    value_ref TEXT NOT NULL REFERENCES execution.semantic_parser_symbol(symbol_ref) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (token_ref, feature_ref, value_ref),
    UNIQUE (token_ref, ordinal)
);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_entity_span (
    entity_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    partition_ref TEXT NOT NULL REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE RESTRICT,
    sentence_ref TEXT REFERENCES execution.semantic_parser_sentence(sentence_ref) ON DELETE SET NULL,
    start_char BIGINT NOT NULL CHECK (start_char >= 0),
    end_char BIGINT NOT NULL CHECK (end_char > start_char),
    entity_type_ref TEXT NOT NULL REFERENCES execution.semantic_parser_symbol(symbol_ref) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_ref, document_ref, start_char, end_char, entity_type_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_boundary_obligation (
    obligation_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    source_partition_ref TEXT NOT NULL REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE RESTRICT,
    repair_partition_ref TEXT REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE SET NULL,
    obligation_kind TEXT NOT NULL CHECK (
        obligation_kind IN ('sentence_crosses_owner', 'dependency_head_outside_sentence')
    ),
    suspected_start_char BIGINT NOT NULL CHECK (suspected_start_char >= 0),
    suspected_end_char BIGINT NOT NULL CHECK (suspected_end_char > suspected_start_char),
    state TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'resolved', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,
    UNIQUE (
        run_ref, document_ref, obligation_kind,
        suspected_start_char, suspected_end_char
    )
);

ALTER TABLE execution.semantic_parser_partition
    DROP CONSTRAINT IF EXISTS semantic_parser_partition_resolves_obligation_ref_fkey;
ALTER TABLE execution.semantic_parser_partition
    ADD CONSTRAINT semantic_parser_partition_resolves_obligation_ref_fkey
    FOREIGN KEY (resolves_obligation_ref)
    REFERENCES execution.semantic_parser_boundary_obligation(obligation_ref)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE IF NOT EXISTS execution.semantic_parser_artifact (
    artifact_ref TEXT PRIMARY KEY,
    partition_ref TEXT NOT NULL REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE CASCADE,
    content_sha256 BYTEA NOT NULL,
    byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
    encoding_ref TEXT NOT NULL,
    locator TEXT NOT NULL,
    cache_only BOOLEAN NOT NULL DEFAULT TRUE CHECK (cache_only),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (partition_ref, content_sha256)
);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_partition_receipt (
    receipt_ref TEXT PRIMARY KEY,
    partition_ref TEXT NOT NULL UNIQUE REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE CASCADE,
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    parser_contract_ref TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    tokenization BOOLEAN NOT NULL,
    sentence_segmentation BOOLEAN NOT NULL,
    part_of_speech BOOLEAN NOT NULL,
    morphology BOOLEAN NOT NULL,
    dependencies BOOLEAN NOT NULL,
    named_entities BOOLEAN NOT NULL,
    sentence_count BIGINT NOT NULL CHECK (sentence_count >= 0),
    token_count BIGINT NOT NULL CHECK (token_count >= 0),
    entity_count BIGINT NOT NULL CHECK (entity_count >= 0),
    boundary_obligation_count BIGINT NOT NULL CHECK (boundary_obligation_count >= 0),
    elapsed_ns BIGINT NOT NULL CHECK (elapsed_ns >= 0),
    worker_pid BIGINT NOT NULL,
    backend_pid INTEGER,
    docbin_artifact_ref TEXT REFERENCES execution.semantic_parser_artifact(artifact_ref) ON DELETE SET NULL,
    receipt_sha256 BYTEA NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_document_coverage (
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    total_partitions BIGINT NOT NULL DEFAULT 0 CHECK (total_partitions >= 0),
    completed_partitions BIGINT NOT NULL DEFAULT 0 CHECK (completed_partitions >= 0),
    open_boundary_obligations BIGINT NOT NULL DEFAULT 0 CHECK (open_boundary_obligations >= 0),
    tokenization BOOLEAN NOT NULL DEFAULT FALSE,
    sentence_segmentation BOOLEAN NOT NULL DEFAULT FALSE,
    part_of_speech BOOLEAN NOT NULL DEFAULT FALSE,
    morphology BOOLEAN NOT NULL DEFAULT FALSE,
    dependencies BOOLEAN NOT NULL DEFAULT FALSE,
    named_entities BOOLEAN NOT NULL DEFAULT FALSE,
    state TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'complete', 'failed')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_ref, document_ref)
);

CREATE TABLE IF NOT EXISTS execution.semantic_parser_outbox (
    event_ref TEXT PRIMARY KEY,
    event_type_ref TEXT NOT NULL CHECK (
        event_type_ref IN (
            'parser.sentence.committed.v1',
            'parser.boundary-obligation.opened.v1',
            'parser.partition.completed.v1',
            'parser.document-coverage.closed.v1'
        )
    ),
    run_ref TEXT NOT NULL REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    partition_ref TEXT REFERENCES execution.semantic_parser_partition(partition_ref) ON DELETE CASCADE,
    sentence_ref TEXT REFERENCES execution.semantic_parser_sentence(sentence_ref) ON DELETE CASCADE,
    obligation_ref TEXT REFERENCES execution.semantic_parser_boundary_obligation(obligation_ref) ON DELETE CASCADE,
    emitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    consumed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS semantic_parser_outbox_pending_idx
    ON execution.semantic_parser_outbox (run_ref, emitted_at)
    WHERE consumed_at IS NULL;

COMMIT;
