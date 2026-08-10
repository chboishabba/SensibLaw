BEGIN;

-- Exact parser-token support is already persisted by strict numeric sentence
-- closure.  Use it as the primary observation->object bridge.  Span containment
-- remains a fail-closed fallback only for evidence-relevant tokens with no exact
-- support row at all.

CREATE INDEX IF NOT EXISTS semantic_pnf_object_token_support_token_idx
    ON execution.semantic_pnf_object_token_support(token_id, object_id);

CREATE OR REPLACE FUNCTION execution.numeric_pnf_document_parser_object_anchor(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS TABLE(token_id BIGINT, sentence_id BIGINT, object_id BIGINT)
LANGUAGE sql
STABLE
AS $$
WITH identity AS (
    SELECT run_identity.run_ref,
           document_identity.document_ref
      FROM execution.semantic_pnf_run_identity AS run_identity
      CROSS JOIN execution.semantic_pnf_document_identity AS document_identity
     WHERE run_identity.run_id = selected_run_id
       AND document_identity.document_id = selected_document_id
), doc_token AS MATERIALIZED (
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
      JOIN identity ON TRUE
     WHERE token.run_ref = identity.run_ref
       AND token.document_ref = identity.document_ref
       AND token.representation_version = 2
), needed_token AS MATERIALIZED (
    SELECT DISTINCT token.*
      FROM doc_token AS token
      JOIN execution.semantic_symbol AS pos
        ON pos.symbol_id = token.pos_symbol_id
     WHERE pos.symbol_text IN ('PROPN', 'NOUN')
        OR EXISTS (
            SELECT 1
              FROM execution.semantic_symbol AS dep
             WHERE dep.symbol_id = token.dependency_symbol_id
               AND dep.symbol_text = 'appos'
        )
        OR EXISTS (
            SELECT 1
              FROM doc_token AS child
              JOIN execution.semantic_symbol AS dep
                ON dep.symbol_id = child.dependency_symbol_id
               AND dep.symbol_text = 'appos'
             WHERE child.head_token_id = token.token_id
        )
), exact_support AS MATERIALIZED (
    SELECT token.token_id,
           token.sentence_id,
           support.object_id
      FROM needed_token AS token
      JOIN execution.semantic_pnf_object_token_support AS support
        ON support.token_id = token.token_id
      JOIN execution.semantic_pnf_object AS object
        ON object.object_id = support.object_id
       AND object.head_symbol_id IN (token.lemma_symbol_id, token.orth_symbol_id)
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = object.region_id
       AND region.run_id = selected_run_id
       AND region.document_id = selected_document_id
), exact_anchor AS (
    SELECT support.token_id,
           min(support.sentence_id) AS sentence_id,
           min(support.object_id) AS object_id
      FROM exact_support AS support
     GROUP BY support.token_id
    HAVING count(DISTINCT support.object_id) = 1
), token_with_any_support AS MATERIALIZED (
    SELECT DISTINCT token.token_id
      FROM needed_token AS token
      JOIN execution.semantic_pnf_object_token_support AS support
        ON support.token_id = token.token_id
), fallback_candidate AS (
    SELECT token.token_id,
           token.sentence_id,
           object.object_id,
           (region.end_char - region.start_char) AS region_span,
           min(region.end_char - region.start_char)
               OVER (PARTITION BY token.token_id) AS minimum_region_span
      FROM needed_token AS token
      LEFT JOIN token_with_any_support AS has_support
        ON has_support.token_id = token.token_id
      JOIN execution.semantic_pnf_region AS region
        ON region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND token.start_char >= region.start_char
       AND token.end_char <= region.end_char
      JOIN execution.semantic_pnf_object AS object
        ON object.region_id = region.region_id
       AND object.head_symbol_id IN (token.lemma_symbol_id, token.orth_symbol_id)
     WHERE has_support.token_id IS NULL
), fallback_smallest AS (
    SELECT token_id, sentence_id, object_id
      FROM fallback_candidate
     WHERE region_span = minimum_region_span
), fallback_anchor AS (
    SELECT token_id,
           min(sentence_id) AS sentence_id,
           min(object_id) AS object_id
      FROM fallback_smallest
     GROUP BY token_id
    HAVING count(DISTINCT object_id) = 1
)
SELECT token_id, sentence_id, object_id FROM exact_anchor
UNION ALL
SELECT token_id, sentence_id, object_id FROM fallback_anchor;
$$;

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
       AND evidence_state IN (1, 2);

    WITH doc_token AS MATERIALIZED (
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
    ), doc_sentence AS MATERIALIZED (
        SELECT sentence.sentence_id, sentence.sentence_ref
          FROM execution.semantic_parser_sentence AS sentence
         WHERE sentence.run_ref = selected_run_ref
           AND sentence.document_ref = selected_document_ref
    ), doc_person_entity AS MATERIALIZED (
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
    ), doc_anchor AS MATERIALIZED (
        SELECT anchor.token_id, anchor.sentence_id, anchor.object_id
          FROM execution.numeric_pnf_document_parser_object_anchor(
              selected_run_id, selected_document_id
          ) AS anchor
    ), appos AS (
        SELECT source_token.token_id AS parser_source_token_id,
               target_token.token_id AS parser_target_token_id,
               source_anchor.object_id AS parser_source_object_id,
               target_anchor.object_id AS parser_target_object_id,
               sentence.sentence_id,
               EXISTS (
                   SELECT 1 FROM doc_person_entity AS entity
                    WHERE entity.sentence_ref = source_token.sentence_ref
                      AND source_token.start_char >= entity.start_char
                      AND source_token.end_char <= entity.end_char
               ) AS source_is_person,
               EXISTS (
                   SELECT 1 FROM doc_person_entity AS entity
                    WHERE entity.sentence_ref = target_token.sentence_ref
                      AND target_token.start_char >= entity.start_char
                      AND target_token.end_char <= entity.end_char
               ) AS target_is_person
          FROM doc_token AS source_token
          JOIN execution.semantic_symbol AS dependency
            ON dependency.symbol_id = source_token.dependency_symbol_id
           AND dependency.symbol_text = 'appos'
          JOIN doc_token AS target_token
            ON target_token.token_id = source_token.head_token_id
           AND target_token.sentence_ref = source_token.sentence_ref
          JOIN doc_sentence AS sentence
            ON sentence.sentence_ref = source_token.sentence_ref
          JOIN doc_anchor AS source_anchor
            ON source_anchor.token_id = source_token.token_id
          JOIN doc_anchor AS target_anchor
            ON target_anchor.token_id = target_token.token_id
         WHERE source_anchor.object_id <> target_anchor.object_id
    ), appos_evidence AS (
        SELECT CASE WHEN source_is_person AND NOT target_is_person
                    THEN parser_target_object_id ELSE parser_source_object_id END
                   AS source_object_id,
               CASE WHEN source_is_person AND NOT target_is_person
                    THEN parser_source_object_id ELSE parser_target_object_id END
                   AS target_object_id,
               CASE WHEN source_is_person <> target_is_person THEN 4 ELSE 2 END
                   AS witness_kind,
               CASE WHEN source_is_person AND NOT target_is_person
                    THEN parser_target_token_id ELSE parser_source_token_id END
                   AS source_token_id,
               CASE WHEN source_is_person AND NOT target_is_person
                    THEN parser_source_token_id ELSE parser_target_token_id END
                   AS target_token_id,
               sentence_id,
               'parser-appos:' || parser_source_token_id::TEXT || ':'
                   || parser_target_token_id::TEXT AS evidence_ref,
               1::SMALLINT AS candidate_count
          FROM appos
    ), person_entity_head AS (
        SELECT entity.entity_id AS parser_entity_id,
               entity.sentence_ref,
               entity.start_char,
               entity.end_char,
               head.token_id AS head_token_id,
               head.lemma_symbol_id AS family_lemma_symbol_id,
               anchor.object_id AS anchor_object_id
          FROM doc_person_entity AS entity
          JOIN LATERAL (
              SELECT token.token_id, token.lemma_symbol_id, token.end_char
                FROM doc_token AS token
                JOIN execution.semantic_symbol AS pos
                  ON pos.symbol_id = token.pos_symbol_id
                 AND pos.symbol_text = 'PROPN'
               WHERE token.sentence_ref = entity.sentence_ref
                 AND token.start_char >= entity.start_char
                 AND token.end_char <= entity.end_char
               ORDER BY token.end_char DESC, token.token_id DESC
               LIMIT 1
          ) AS head ON TRUE
          JOIN doc_anchor AS anchor
            ON anchor.token_id = head.token_id
         WHERE (
               SELECT count(*) FROM doc_token AS member
                WHERE member.sentence_ref = entity.sentence_ref
                  AND member.start_char >= entity.start_char
                  AND member.end_char <= entity.end_char
           ) >= 2
    ), family_cardinality AS (
        SELECT family_lemma_symbol_id,
               LEAST(256, count(DISTINCT parser_entity_id))::SMALLINT
                   AS candidate_count
          FROM person_entity_head
         GROUP BY family_lemma_symbol_id
    ), proper_name_evidence AS (
        SELECT mention_anchor.object_id AS source_object_id,
               person.anchor_object_id AS target_object_id,
               3::SMALLINT AS witness_kind,
               mention.token_id AS source_token_id,
               person.head_token_id AS target_token_id,
               sentence.sentence_id,
               'proper-name-expansion:' || mention.token_id::TEXT || ':'
                   || person.parser_entity_id::TEXT AS evidence_ref,
               cardinality.candidate_count
          FROM doc_token AS mention
          JOIN execution.semantic_symbol AS mention_pos
            ON mention_pos.symbol_id = mention.pos_symbol_id
           AND mention_pos.symbol_text = 'PROPN'
          JOIN doc_sentence AS sentence
            ON sentence.sentence_ref = mention.sentence_ref
          JOIN doc_anchor AS mention_anchor
            ON mention_anchor.token_id = mention.token_id
          JOIN person_entity_head AS person
            ON person.family_lemma_symbol_id = mention.lemma_symbol_id
          JOIN family_cardinality AS cardinality
            ON cardinality.family_lemma_symbol_id = mention.lemma_symbol_id
         WHERE NOT (
               mention.sentence_ref = person.sentence_ref
               AND mention.start_char >= person.start_char
               AND mention.end_char <= person.end_char
           )
           AND mention_anchor.object_id <> person.anchor_object_id
    ), alias_pair AS (
        SELECT left_entity.entity_id AS left_entity_id,
               right_entity.entity_id AS right_entity_id,
               sentence.sentence_id,
               left_head.token_id AS left_token_id,
               right_head.token_id AS right_token_id,
               left_anchor.object_id AS left_object_id,
               right_anchor.object_id AS right_object_id,
               min(cue.token_id) AS cue_token_id
          FROM doc_person_entity AS left_entity
          JOIN doc_person_entity AS right_entity
            ON right_entity.sentence_ref = left_entity.sentence_ref
           AND right_entity.start_char > left_entity.end_char
          JOIN doc_sentence AS sentence
            ON sentence.sentence_ref = left_entity.sentence_ref
          JOIN LATERAL (
              SELECT token.token_id FROM doc_token AS token
               WHERE token.sentence_ref = left_entity.sentence_ref
                 AND token.start_char >= left_entity.start_char
                 AND token.end_char <= left_entity.end_char
               ORDER BY token.end_char DESC LIMIT 1
          ) AS left_head ON TRUE
          JOIN LATERAL (
              SELECT token.token_id FROM doc_token AS token
               WHERE token.sentence_ref = right_entity.sentence_ref
                 AND token.start_char >= right_entity.start_char
                 AND token.end_char <= right_entity.end_char
               ORDER BY token.end_char DESC LIMIT 1
          ) AS right_head ON TRUE
          JOIN doc_anchor AS left_anchor ON left_anchor.token_id = left_head.token_id
          JOIN doc_anchor AS right_anchor ON right_anchor.token_id = right_head.token_id
          JOIN doc_token AS cue
            ON cue.sentence_ref = left_entity.sentence_ref
           AND cue.start_char >= left_entity.end_char
           AND cue.end_char <= right_entity.start_char
          JOIN execution.semantic_symbol AS cue_text
            ON cue_text.symbol_id = cue.orth_symbol_id
         WHERE left_anchor.object_id <> right_anchor.object_id
           AND (
               lower(cue_text.symbol_text) IN ('aka', 'a.k.a.', 'alias')
               OR (
                   lower(cue_text.symbol_text) = 'known'
                   AND EXISTS (
                       SELECT 1
                         FROM doc_token AS as_token
                         JOIN execution.semantic_symbol AS as_text
                           ON as_text.symbol_id = as_token.orth_symbol_id
                          AND lower(as_text.symbol_text) = 'as'
                        WHERE as_token.sentence_ref = cue.sentence_ref
                          AND as_token.start_char >= cue.end_char
                          AND as_token.end_char <= right_entity.start_char
                   )
               )
           )
         GROUP BY left_entity.entity_id, right_entity.entity_id,
                  sentence.sentence_id, left_head.token_id, right_head.token_id,
                  left_anchor.object_id, right_anchor.object_id
    ), alias_evidence AS (
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
    ), evidence AS (
        SELECT * FROM appos_evidence
        UNION ALL SELECT * FROM proper_name_evidence
        UNION ALL SELECT * FROM alias_evidence
    )
    INSERT INTO execution.semantic_pnf_identity_evidence_candidate
        (run_id, document_id, source_object_id, target_object_id,
         witness_kind, source_token_id, target_token_id, sentence_id,
         evidence_ref, candidate_count, evidence_state)
    SELECT selected_run_id, selected_document_id,
           source_object_id, target_object_id, witness_kind,
           source_token_id, target_token_id, sentence_id,
           evidence_ref, candidate_count, 1
      FROM evidence
    ON CONFLICT (run_id, document_id, source_object_id, target_object_id,
                 witness_kind, evidence_ref)
    DO UPDATE SET
        evidence_state = 1,
        candidate_count = EXCLUDED.candidate_count,
        source_token_id = EXCLUDED.source_token_id,
        target_token_id = EXCLUDED.target_token_id,
        sentence_id = EXCLUDED.sentence_id;

    SELECT count(*) INTO affected_count
      FROM execution.semantic_pnf_identity_evidence_candidate
     WHERE run_id = selected_run_id
       AND document_id = selected_document_id
       AND evidence_state = 1;
    RETURN affected_count;
END;
$$;

COMMIT;
