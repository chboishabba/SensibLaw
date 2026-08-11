BEGIN;

-- Proper-name evidence fan-out -------------------------------------------------
--
-- Proper-name expansion is candidate evidence, never bootstrap identity.  The
-- previous producer joined every PROPN mention to every multi-token PERSON head
-- sharing its family lemma, even though candidate_count > 1 is non-admissible.
-- That made parser-evidence work proportional to mention x family-cardinality.
--
-- This migration preserves exact ambiguity cardinality while retaining at most
-- K representative targets per standalone surname mention.  Overflow is an
-- execution receipt, not semantic rejection.  Tokens already inside a PERSON
-- span are not proper-name-expansion sources: their full-name structure is
-- already present and treating the component surname as standalone can create a
-- false unique target after self-exclusion.

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_proper_name_evidence_overflow (
    run_id BIGINT NOT NULL,
    document_id BIGINT NOT NULL,
    source_object_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE CASCADE,
    source_token_id BIGINT NOT NULL
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE CASCADE,
    family_lemma_symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE RESTRICT,
    possible_target_count BIGINT NOT NULL CHECK (possible_target_count > 1),
    retained_target_limit SMALLINT NOT NULL CHECK (retained_target_limit BETWEEN 1 AND 256),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, document_id, source_object_id, source_token_id,
                 family_lemma_symbol_id)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_proper_name_evidence_overflow_doc_idx
    ON execution.semantic_pnf_proper_name_evidence_overflow
       (run_id, document_id, possible_target_count DESC, source_token_id);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_parser_identity_evidence(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_run_ref TEXT;
    selected_document_ref TEXT;
    affected_count BIGINT := 0;
    max_name_targets CONSTANT INTEGER := 16;
BEGIN
    SELECT run_ref INTO selected_run_ref
      FROM execution.semantic_pnf_run_identity
     WHERE run_id = selected_run_id;
    SELECT document_ref INTO selected_document_ref
      FROM execution.semantic_pnf_document_identity
     WHERE document_id = selected_document_id;

    IF selected_run_ref IS NULL OR selected_document_ref IS NULL THEN
        RAISE EXCEPTION 'unknown numeric run/document %, %',
            selected_run_id, selected_document_id;
    END IF;

    UPDATE execution.semantic_pnf_identity_evidence_candidate
       SET evidence_state = 4
     WHERE run_id = selected_run_id
       AND document_id = selected_document_id
       AND evidence_state IN (1, 2, 3);

    DELETE FROM execution.semantic_pnf_proper_name_evidence_overflow
     WHERE run_id = selected_run_id
       AND document_id = selected_document_id;

    -- All three parser-evidence lanes share this one document carrier.  PERSON
    -- membership, family cardinality and bounded target ranking are therefore
    -- computed once per refresh, including the overflow receipt.
    WITH
    doc_token AS MATERIALIZED (
        SELECT token.token_id,
               token.sentence_id,
               token.sentence_ref,
               token.start_char,
               token.end_char,
               token.orth_symbol_id,
               token.lemma_symbol_id,
               token.pos_symbol_id,
               token.dependency_symbol_id,
               token.head_token_id
          FROM execution.semantic_parser_token AS token
         WHERE token.run_ref = selected_run_ref
           AND token.document_ref = selected_document_ref
           AND token.representation_version = 2
    ),
    appos_token AS MATERIALIZED (
        SELECT token.token_id AS source_token_id,
               token.head_token_id AS target_token_id
          FROM doc_token AS token
          JOIN execution.semantic_symbol AS dependency
            ON dependency.symbol_id = token.dependency_symbol_id
           AND dependency.symbol_text = 'appos'
    ),
    doc_sentence AS MATERIALIZED (
        SELECT sentence.sentence_id,
               sentence.sentence_ref
          FROM execution.semantic_parser_sentence AS sentence
         WHERE sentence.run_ref = selected_run_ref
           AND sentence.document_ref = selected_document_ref
    ),
    doc_person_entity AS MATERIALIZED (
        SELECT entity.entity_id,
               entity.sentence_ref,
               entity.start_char,
               entity.end_char
          FROM execution.semantic_parser_entity_span AS entity
          JOIN execution.semantic_symbol AS entity_type
            ON entity_type.symbol_id = entity.entity_type_symbol_id
           AND entity_type.symbol_text = 'PERSON'
         WHERE entity.run_ref = selected_run_ref
           AND entity.document_ref = selected_document_ref
    ),
    doc_anchor AS MATERIALIZED (
        SELECT anchor.token_id,
               anchor.sentence_id,
               anchor.object_id
          FROM execution.numeric_pnf_document_parser_object_anchor(
              selected_run_id, selected_document_id
          ) AS anchor
    ),
    person_entity_member AS MATERIALIZED (
        SELECT entity.entity_id AS parser_entity_id,
               entity.sentence_ref,
               entity.start_char,
               entity.end_char,
               token.token_id,
               token.lemma_symbol_id,
               token.pos_symbol_id,
               token.end_char AS token_end_char,
               count(*) OVER (PARTITION BY entity.entity_id) AS member_count
          FROM doc_person_entity AS entity
          JOIN doc_token AS token
            ON token.sentence_ref = entity.sentence_ref
           AND token.start_char >= entity.start_char
           AND token.end_char <= entity.end_char
    ),
    person_member_token AS MATERIALIZED (
        SELECT DISTINCT token_id
          FROM person_entity_member
    ),
    person_entity_head AS MATERIALIZED (
        SELECT DISTINCT ON (member.parser_entity_id)
               member.parser_entity_id,
               member.sentence_ref,
               member.start_char,
               member.end_char,
               member.token_id AS head_token_id,
               member.lemma_symbol_id AS family_lemma_symbol_id,
               anchor.object_id AS anchor_object_id
          FROM person_entity_member AS member
          JOIN execution.semantic_symbol AS pos
            ON pos.symbol_id = member.pos_symbol_id
           AND pos.symbol_text = 'PROPN'
          JOIN doc_anchor AS anchor
            ON anchor.token_id = member.token_id
          WHERE member.member_count >= 2
          ORDER BY member.parser_entity_id,
                   member.token_end_char DESC,
                   member.token_id DESC
    ),
    family_target AS MATERIALIZED (
        SELECT person.*,
               count(*) OVER (
                   PARTITION BY person.family_lemma_symbol_id
               )::BIGINT AS family_candidate_count,
               row_number() OVER (
                   PARTITION BY person.family_lemma_symbol_id
                   ORDER BY person.parser_entity_id,
                            person.anchor_object_id,
                            person.head_token_id
               ) AS family_rank
          FROM person_entity_head AS person
    ),

    -- Direct dependency apposition remains proof-producing local structure.
    appos AS (
        SELECT source_token.token_id AS parser_source_token_id,
               target_token.token_id AS parser_target_token_id,
               source_anchor.object_id AS parser_source_object_id,
               target_anchor.object_id AS parser_target_object_id,
               sentence.sentence_id,
               EXISTS (
                   SELECT 1
                     FROM person_member_token AS member
                    WHERE member.token_id = source_token.token_id
               ) AS source_is_person,
               EXISTS (
                   SELECT 1
                     FROM person_member_token AS member
                    WHERE member.token_id = target_token.token_id
               ) AS target_is_person
          FROM appos_token AS dependency
          JOIN doc_token AS source_token
            ON source_token.token_id = dependency.source_token_id
          JOIN doc_token AS target_token
            ON target_token.token_id = dependency.target_token_id
           AND target_token.sentence_ref = source_token.sentence_ref
          JOIN doc_sentence AS sentence
            ON sentence.sentence_ref = source_token.sentence_ref
          JOIN doc_anchor AS source_anchor
            ON source_anchor.token_id = source_token.token_id
          JOIN doc_anchor AS target_anchor
            ON target_anchor.token_id = target_token.token_id
         WHERE source_anchor.object_id <> target_anchor.object_id
    ),
    appos_evidence AS (
        SELECT CASE
                   WHEN source_is_person AND NOT target_is_person
                   THEN parser_target_object_id
                   ELSE parser_source_object_id
               END AS source_object_id,
               CASE
                   WHEN source_is_person AND NOT target_is_person
                   THEN parser_source_object_id
                   ELSE parser_target_object_id
               END AS target_object_id,
               CASE WHEN source_is_person <> target_is_person THEN 4 ELSE 2 END
                   AS witness_kind,
               CASE
                   WHEN source_is_person AND NOT target_is_person
                   THEN parser_target_token_id
                   ELSE parser_source_token_id
               END AS source_token_id,
               CASE
                   WHEN source_is_person AND NOT target_is_person
                   THEN parser_source_token_id
                   ELSE parser_target_token_id
               END AS target_token_id,
               sentence_id,
               'parser-appos:' || parser_source_token_id::TEXT || ':'
                   || parser_target_token_id::TEXT AS evidence_ref,
               1::SMALLINT AS candidate_count
          FROM appos
    ),

    -- Proper-name expansion is only for standalone proper-name tokens.  A token
    -- inside any PERSON span is already part of explicit full-name structure.
    proper_name_mention AS MATERIALIZED (
        SELECT token.token_id,
               token.sentence_id,
               token.sentence_ref,
               token.start_char,
               token.end_char,
               token.lemma_symbol_id,
               anchor.object_id AS source_object_id
          FROM doc_token AS token
          JOIN execution.semantic_symbol AS pos
            ON pos.symbol_id = token.pos_symbol_id
           AND pos.symbol_text = 'PROPN'
          JOIN doc_anchor AS anchor
            ON anchor.token_id = token.token_id
          LEFT JOIN person_member_token AS member
            ON member.token_id = token.token_id
         WHERE member.token_id IS NULL
    ),
    proper_name_raw AS (
        SELECT mention.source_object_id,
               target.anchor_object_id AS target_object_id,
               mention.token_id AS source_token_id,
               target.head_token_id AS target_token_id,
               mention.sentence_id,
               mention.lemma_symbol_id AS family_lemma_symbol_id,
               target.parser_entity_id,
               target.family_candidate_count,
               row_number() OVER (
                   PARTITION BY mention.token_id
                   ORDER BY target.family_rank,
                            target.parser_entity_id,
                            target.anchor_object_id
               ) AS mention_target_rank
          FROM proper_name_mention AS mention
          JOIN family_target AS target
            ON target.family_lemma_symbol_id = mention.lemma_symbol_id
           AND target.family_rank <= max_name_targets
         WHERE mention.source_object_id <> target.anchor_object_id
    ),
    proper_name_evidence AS (
        SELECT source_object_id,
               target_object_id,
               3::SMALLINT AS witness_kind,
               source_token_id,
               target_token_id,
               sentence_id,
               'proper-name-expansion:' || source_token_id::TEXT || ':'
                   || parser_entity_id::TEXT AS evidence_ref,
               LEAST(256, family_candidate_count)::SMALLINT AS candidate_count
          FROM proper_name_raw
         WHERE mention_target_rank <= max_name_targets
    ),
    proper_name_overflow AS (
        SELECT DISTINCT
               mention.source_object_id,
               mention.token_id AS source_token_id,
               mention.lemma_symbol_id AS family_lemma_symbol_id,
               target.family_candidate_count AS possible_target_count
          FROM proper_name_mention AS mention
          JOIN family_target AS target
            ON target.family_lemma_symbol_id = mention.lemma_symbol_id
           AND target.family_rank = 1
         WHERE target.family_candidate_count > max_name_targets
    ),

    doc_alias_cue AS MATERIALIZED (
        SELECT cue.token_id AS cue_token_id,
               cue.sentence_ref,
               cue.start_char AS cue_start,
               cue.end_char AS cue_end,
               lower(cue_text.symbol_text) AS cue_text
          FROM doc_token AS cue
          JOIN execution.semantic_symbol AS cue_text
            ON cue_text.symbol_id = cue.orth_symbol_id
         WHERE lower(cue_text.symbol_text) IN ('aka', 'a.k.a.', 'alias', 'known')
    ),

    -- Explicit alias cues retain the existing conservative sentence-local rule.
    alias_pair AS (
        SELECT left_entity.entity_id AS left_entity_id,
               right_entity.entity_id AS right_entity_id,
               sentence.sentence_id,
               left_head.token_id AS left_token_id,
               right_head.token_id AS right_token_id,
               left_anchor.object_id AS left_object_id,
               right_anchor.object_id AS right_object_id,
               min(cue.cue_token_id) AS cue_token_id
          FROM doc_alias_cue AS cue
          JOIN doc_person_entity AS left_entity
            ON left_entity.sentence_ref = cue.sentence_ref
           AND left_entity.end_char <= cue.cue_start
          JOIN doc_person_entity AS right_entity
            ON right_entity.sentence_ref = cue.sentence_ref
           AND right_entity.start_char >= cue.cue_end
          JOIN doc_sentence AS sentence
            ON sentence.sentence_ref = cue.sentence_ref
          JOIN LATERAL (
              SELECT member.token_id
                FROM person_entity_member AS member
               WHERE member.parser_entity_id = left_entity.entity_id
               ORDER BY member.token_end_char DESC, member.token_id DESC
               LIMIT 1
          ) AS left_head ON TRUE
          JOIN LATERAL (
              SELECT member.token_id
                FROM person_entity_member AS member
               WHERE member.parser_entity_id = right_entity.entity_id
               ORDER BY member.token_end_char DESC, member.token_id DESC
               LIMIT 1
          ) AS right_head ON TRUE
          JOIN doc_anchor AS left_anchor
            ON left_anchor.token_id = left_head.token_id
          JOIN doc_anchor AS right_anchor
            ON right_anchor.token_id = right_head.token_id
         WHERE left_anchor.object_id <> right_anchor.object_id
           AND (
               cue.cue_text IN ('aka', 'a.k.a.', 'alias')
               OR (
                   cue.cue_text = 'known'
                   AND EXISTS (
                       SELECT 1
                         FROM doc_token AS as_token
                         JOIN execution.semantic_symbol AS as_text
                           ON as_text.symbol_id = as_token.orth_symbol_id
                          AND lower(as_text.symbol_text) = 'as'
                        WHERE as_token.sentence_ref = cue.sentence_ref
                          AND as_token.start_char >= cue.cue_end
                          AND as_token.end_char <= right_entity.start_char
                   )
               )
           )
         GROUP BY left_entity.entity_id,
                  right_entity.entity_id,
                  sentence.sentence_id,
                  left_head.token_id,
                  right_head.token_id,
                  left_anchor.object_id,
                  right_anchor.object_id
    ),
    alias_evidence AS (
        SELECT right_object_id AS source_object_id,
               left_object_id AS target_object_id,
               6::SMALLINT AS witness_kind,
               right_token_id AS source_token_id,
               left_token_id AS target_token_id,
               sentence_id,
               'explicit-alias:' || cue_token_id::TEXT || ':'
                   || left_entity_id::TEXT || ':' || right_entity_id::TEXT
                   AS evidence_ref,
               1::SMALLINT AS candidate_count
          FROM alias_pair
    ),
    evidence AS (
        SELECT * FROM appos_evidence
        UNION ALL
        SELECT * FROM proper_name_evidence
        UNION ALL
        SELECT * FROM alias_evidence
    ),
    evidence_write AS (
        INSERT INTO execution.semantic_pnf_identity_evidence_candidate
            (run_id, document_id, source_object_id, target_object_id,
             witness_kind, source_token_id, target_token_id, sentence_id,
             evidence_ref, candidate_count, evidence_state)
        SELECT selected_run_id,
               selected_document_id,
               evidence.source_object_id,
               evidence.target_object_id,
               evidence.witness_kind,
               evidence.source_token_id,
               evidence.target_token_id,
               evidence.sentence_id,
               evidence.evidence_ref,
               evidence.candidate_count,
               1
          FROM evidence
        ON CONFLICT (run_id, document_id, source_object_id, target_object_id,
                     witness_kind, evidence_ref)
        DO UPDATE SET
            evidence_state = 1,
            candidate_count = EXCLUDED.candidate_count,
            source_token_id = EXCLUDED.source_token_id,
            target_token_id = EXCLUDED.target_token_id,
            sentence_id = EXCLUDED.sentence_id
        RETURNING candidate_id
    ),
    overflow_write AS (
        INSERT INTO execution.semantic_pnf_proper_name_evidence_overflow
            (run_id, document_id, source_object_id, source_token_id,
             family_lemma_symbol_id, possible_target_count,
             retained_target_limit)
        SELECT selected_run_id,
               selected_document_id,
               overflow.source_object_id,
               overflow.source_token_id,
               overflow.family_lemma_symbol_id,
               overflow.possible_target_count,
               max_name_targets::SMALLINT
          FROM proper_name_overflow AS overflow
        ON CONFLICT (run_id, document_id, source_object_id, source_token_id,
                     family_lemma_symbol_id)
        DO UPDATE SET
            possible_target_count = EXCLUDED.possible_target_count,
            retained_target_limit = EXCLUDED.retained_target_limit,
            observed_at = CURRENT_TIMESTAMP
        RETURNING source_token_id
    )
    SELECT (SELECT count(*) FROM evidence_write)
         + (SELECT 0 * count(*) FROM overflow_write)
      INTO affected_count;

    RETURN affected_count;
END;
$$;

COMMIT;
