BEGIN;

-- 151: migration 150 resolves dependency heads by the exact numeric key
-- (sentence_id, head_start_char, head_end_char). Earlier parser indexes were
-- designed for ordinal traversal or document-wide spans and do not match that
-- join prefix. Give the set-wise head projection its physical lookup geometry
-- instead of replacing N client UPDATEs with an avoidable table-scale join.
--
-- representation_version=2 is the only consumer of this numeric head relation,
-- so keep the index partial and include token_id as the projected target.

CREATE INDEX IF NOT EXISTS semantic_parser_token_numeric_sentence_span_idx
    ON execution.semantic_parser_token
       (sentence_id, start_char, end_char, token_id)
    WHERE representation_version = 2;

COMMIT;
