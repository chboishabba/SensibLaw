BEGIN;

-- Canonical G4 stable source-evidence carrier for direct sentence publication.
-- This schema intentionally has no foreign key to execution.semantic_parser_token.
CREATE TABLE IF NOT EXISTS execution.semantic_source_token_evidence (
    evidence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evidence_digest BYTEA NOT NULL UNIQUE,
    run_ref TEXT NOT NULL,
    document_ref TEXT NOT NULL,
    sentence_digest BYTEA NOT NULL,
    token_ordinal INTEGER NOT NULL,
    start_char BIGINT NOT NULL,
    end_char BIGINT NOT NULL,
    start_byte BIGINT NOT NULL,
    end_byte BIGINT NOT NULL,
    CHECK (start_char >= 0 AND end_char >= start_char),
    CHECK (start_byte >= 0 AND end_byte >= start_byte),
    UNIQUE (run_ref, document_ref, sentence_digest, token_ordinal)
);

CREATE INDEX IF NOT EXISTS semantic_source_token_evidence_scope_idx
    ON execution.semantic_source_token_evidence
       (run_ref, document_ref, sentence_digest, token_ordinal);

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_object_evidence_support (
    object_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE CASCADE,
    evidence_id BIGINT NOT NULL
        REFERENCES execution.semantic_source_token_evidence(evidence_id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (object_id, ordinal),
    UNIQUE (object_id, evidence_id)
);

CREATE INDEX IF NOT EXISTS semantic_pnf_object_evidence_support_evidence_idx
    ON execution.semantic_pnf_object_evidence_support(evidence_id, object_id);

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_factor_evidence_support (
    factor_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_factor(factor_id) ON DELETE CASCADE,
    evidence_id BIGINT NOT NULL
        REFERENCES execution.semantic_source_token_evidence(evidence_id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (factor_id, ordinal),
    UNIQUE (factor_id, evidence_id)
);

CREATE INDEX IF NOT EXISTS semantic_pnf_factor_evidence_support_evidence_idx
    ON execution.semantic_pnf_factor_evidence_support(evidence_id, factor_id);

COMMIT;
