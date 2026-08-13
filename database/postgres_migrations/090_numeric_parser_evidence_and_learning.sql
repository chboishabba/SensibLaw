BEGIN;

-- Compile finite lexical cue classes once at the vocabulary boundary.  The
-- expensive parser-evidence CTEs below join only numeric SymbolIds.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_hot_cue_symbol (
    cue_class SMALLINT NOT NULL CHECK (cue_class BETWEEN 1 AND 3),
    symbol_id BIGINT NOT NULL
        REFERENCES execution.semantic_symbol(symbol_id) ON DELETE CASCADE,
    PRIMARY KEY(cue_class,symbol_id)
);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_hot_cue_symbols()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    DELETE FROM execution.semantic_pnf_hot_cue_symbol;
    INSERT INTO execution.semantic_pnf_hot_cue_symbol(cue_class,symbol_id)
    SELECT CASE
               WHEN lower(symbol.symbol_text) IN ('aka','a.k.a.','alias') THEN 1
               WHEN lower(symbol.symbol_text) = 'known' THEN 2
               ELSE 3
           END::SMALLINT,
           symbol.symbol_id
      FROM execution.semantic_symbol AS symbol
     WHERE symbol.kind_id = 1
       AND lower(symbol.symbol_text) IN ('aka','a.k.a.','alias','known','as');
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;
SELECT execution.refresh_numeric_pnf_hot_cue_symbols();

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_hot_cue_on_symbol_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind_id=1 AND lower(NEW.symbol_text) IN ('aka','a.k.a.','alias','known','as') THEN
        PERFORM execution.refresh_numeric_pnf_hot_cue_symbols();
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS semantic_symbol_refresh_hot_cue ON execution.semantic_symbol;
CREATE TRIGGER semantic_symbol_refresh_hot_cue
AFTER INSERT OR UPDATE OF kind_id,symbol_text ON execution.semantic_symbol
FOR EACH ROW EXECUTE FUNCTION execution.refresh_numeric_pnf_hot_cue_on_symbol_insert();

-- Numeric-only replacement of the parser identity-evidence producer from 083.
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
      FROM execution.semantic_pnf_run_identity WHERE run_id=selected_run_id;
    SELECT document_ref INTO selected_document_ref
      FROM execution.semantic_pnf_document_identity WHERE document_id=selected_document_id;
    IF selected_run_ref IS NULL OR selected_document_ref IS NULL THEN
        RAISE EXCEPTION 'unknown numeric run/document %, %', selected_run_id, selected_document_id;
    END IF;

    UPDATE execution.semantic_pnf_identity_evidence_candidate
       SET evidence_state=4
     WHERE run_id=selected_run_id AND document_id=selected_document_id
       AND evidence_state IN (1,2);

    WITH constant AS MATERIALIZED (
        SELECT max(symbol_id) FILTER (WHERE constant_id=1) AS propn_id,
               max(symbol_id) FILTER (WHERE constant_id=3) AS appos_id,
               max(symbol_id) FILTER (WHERE constant_id=4) AS person_id
          FROM execution.semantic_pnf_hot_symbol_constant
    ), doc_token AS MATERIALIZED (
        SELECT token.token_id,token.sentence_id,token.sentence_ref,
               token.start_char,token.end_char,token.orth_symbol_id,
               token.lemma_symbol_id,token.pos_symbol_id,
               token.dependency_symbol_id,token.head_token_id
          FROM execution.semantic_parser_token AS token
         WHERE token.run_ref=selected_run_ref
           AND token.document_ref=selected_document_ref
           AND token.representation_version=2
    ), doc_sentence AS MATERIALIZED (
        SELECT sentence_id,sentence_ref
          FROM execution.semantic_parser_sentence
         WHERE run_ref=selected_run_ref AND document_ref=selected_document_ref
    ), doc_person_entity AS MATERIALIZED (
        SELECT entity.entity_id,entity.sentence_ref,entity.start_char,entity.end_char
          FROM execution.semantic_parser_entity_span AS entity
          CROSS JOIN constant
         WHERE entity.run_ref=selected_run_ref
           AND entity.document_ref=selected_document_ref
           AND entity.entity_type_symbol_id=constant.person_id
    ), doc_anchor AS MATERIALIZED (
        SELECT * FROM execution.numeric_pnf_document_parser_object_anchor(
            selected_run_id,selected_document_id
        )
    ), appos AS (
        SELECT source_token.token_id AS parser_source_token_id,
               target_token.token_id AS parser_target_token_id,
               source_anchor.object_id AS parser_source_object_id,
               target_anchor.object_id AS parser_target_object_id,
               sentence.sentence_id,
               EXISTS (
                   SELECT 1 FROM doc_person_entity AS entity
                    WHERE entity.sentence_ref=source_token.sentence_ref
                      AND source_token.start_char>=entity.start_char
                      AND source_token.end_char<=entity.end_char
               ) AS source_is_person,
               EXISTS (
                   SELECT 1 FROM doc_person_entity AS entity
                    WHERE entity.sentence_ref=target_token.sentence_ref
                      AND target_token.start_char>=entity.start_char
                      AND target_token.end_char<=entity.end_char
               ) AS target_is_person
          FROM doc_token AS source_token
          CROSS JOIN constant
          JOIN doc_token AS target_token
            ON target_token.token_id=source_token.head_token_id
           AND target_token.sentence_ref=source_token.sentence_ref
          JOIN doc_sentence AS sentence ON sentence.sentence_ref=source_token.sentence_ref
          JOIN doc_anchor AS source_anchor ON source_anchor.token_id=source_token.token_id
          JOIN doc_anchor AS target_anchor ON target_anchor.token_id=target_token.token_id
         WHERE source_token.dependency_symbol_id=constant.appos_id
           AND source_anchor.object_id<>target_anchor.object_id
    ), appos_evidence AS (
        SELECT CASE WHEN source_is_person AND NOT target_is_person
                    THEN parser_target_object_id ELSE parser_source_object_id END AS source_object_id,
               CASE WHEN source_is_person AND NOT target_is_person
                    THEN parser_source_object_id ELSE parser_target_object_id END AS target_object_id,
               CASE WHEN source_is_person<>target_is_person THEN 4 ELSE 2 END::SMALLINT AS witness_kind,
               CASE WHEN source_is_person AND NOT target_is_person
                    THEN parser_target_token_id ELSE parser_source_token_id END AS source_token_id,
               CASE WHEN source_is_person AND NOT target_is_person
                    THEN parser_source_token_id ELSE parser_target_token_id END AS target_token_id,
               sentence_id,
               'parser-appos:'||parser_source_token_id::TEXT||':'||parser_target_token_id::TEXT AS evidence_ref,
               1::SMALLINT AS candidate_count
          FROM appos
    ), person_entity_head AS (
        SELECT entity.entity_id AS parser_entity_id,entity.sentence_ref,
               entity.start_char,entity.end_char,head.token_id AS head_token_id,
               head.lemma_symbol_id AS family_lemma_symbol_id,
               anchor.object_id AS anchor_object_id
          FROM doc_person_entity AS entity
          CROSS JOIN constant
          JOIN LATERAL (
              SELECT token.token_id,token.lemma_symbol_id,token.end_char
                FROM doc_token AS token
               WHERE token.sentence_ref=entity.sentence_ref
                 AND token.start_char>=entity.start_char
                 AND token.end_char<=entity.end_char
                 AND token.pos_symbol_id=constant.propn_id
               ORDER BY token.end_char DESC,token.token_id DESC LIMIT 1
          ) AS head ON TRUE
          JOIN doc_anchor AS anchor ON anchor.token_id=head.token_id
         WHERE (SELECT count(*) FROM doc_token AS member
                 WHERE member.sentence_ref=entity.sentence_ref
                   AND member.start_char>=entity.start_char
                   AND member.end_char<=entity.end_char) >= 2
    ), family_cardinality AS (
        SELECT family_lemma_symbol_id,
               LEAST(256,count(DISTINCT parser_entity_id))::SMALLINT AS candidate_count
          FROM person_entity_head GROUP BY family_lemma_symbol_id
    ), proper_name_evidence AS (
        SELECT mention_anchor.object_id AS source_object_id,
               person.anchor_object_id AS target_object_id,
               3::SMALLINT AS witness_kind,mention.token_id AS source_token_id,
               person.head_token_id AS target_token_id,sentence.sentence_id,
               'proper-name-expansion:'||mention.token_id::TEXT||':'||person.parser_entity_id::TEXT AS evidence_ref,
               cardinality.candidate_count
          FROM doc_token AS mention
          CROSS JOIN constant
          JOIN doc_sentence AS sentence ON sentence.sentence_ref=mention.sentence_ref
          JOIN doc_anchor AS mention_anchor ON mention_anchor.token_id=mention.token_id
          JOIN person_entity_head AS person
            ON person.family_lemma_symbol_id=mention.lemma_symbol_id
          JOIN family_cardinality AS cardinality
            ON cardinality.family_lemma_symbol_id=mention.lemma_symbol_id
         WHERE mention.pos_symbol_id=constant.propn_id
           AND NOT (mention.sentence_ref=person.sentence_ref
                    AND mention.start_char>=person.start_char
                    AND mention.end_char<=person.end_char)
           AND mention_anchor.object_id<>person.anchor_object_id
    ), alias_pair AS (
        SELECT left_entity.entity_id AS left_entity_id,
               right_entity.entity_id AS right_entity_id,
               sentence.sentence_id,left_head.token_id AS left_token_id,
               right_head.token_id AS right_token_id,
               left_anchor.object_id AS left_object_id,
               right_anchor.object_id AS right_object_id,
               min(cue.token_id) AS cue_token_id
          FROM doc_person_entity AS left_entity
          JOIN doc_person_entity AS right_entity
            ON right_entity.sentence_ref=left_entity.sentence_ref
           AND right_entity.start_char>left_entity.end_char
          JOIN doc_sentence AS sentence ON sentence.sentence_ref=left_entity.sentence_ref
          JOIN LATERAL (
              SELECT token.token_id FROM doc_token AS token
               WHERE token.sentence_ref=left_entity.sentence_ref
                 AND token.start_char>=left_entity.start_char
                 AND token.end_char<=left_entity.end_char
               ORDER BY token.end_char DESC LIMIT 1
          ) AS left_head ON TRUE
          JOIN LATERAL (
              SELECT token.token_id FROM doc_token AS token
               WHERE token.sentence_ref=right_entity.sentence_ref
                 AND token.start_char>=right_entity.start_char
                 AND token.end_char<=right_entity.end_char
               ORDER BY token.end_char DESC LIMIT 1
          ) AS right_head ON TRUE
          JOIN doc_anchor AS left_anchor ON left_anchor.token_id=left_head.token_id
          JOIN doc_anchor AS right_anchor ON right_anchor.token_id=right_head.token_id
          JOIN doc_token AS cue
            ON cue.sentence_ref=left_entity.sentence_ref
           AND cue.start_char>=left_entity.end_char
           AND cue.end_char<=right_entity.start_char
         WHERE left_anchor.object_id<>right_anchor.object_id
           AND (
               EXISTS (SELECT 1 FROM execution.semantic_pnf_hot_cue_symbol AS direct
                        WHERE direct.cue_class=1 AND direct.symbol_id=cue.orth_symbol_id)
               OR (
                   EXISTS (SELECT 1 FROM execution.semantic_pnf_hot_cue_symbol AS known
                            WHERE known.cue_class=2 AND known.symbol_id=cue.orth_symbol_id)
                   AND EXISTS (
                       SELECT 1 FROM doc_token AS as_token
                       JOIN execution.semantic_pnf_hot_cue_symbol AS as_cue
                         ON as_cue.cue_class=3 AND as_cue.symbol_id=as_token.orth_symbol_id
                        WHERE as_token.sentence_ref=cue.sentence_ref
                          AND as_token.start_char>=cue.end_char
                          AND as_token.end_char<=right_entity.start_char
                   )
               )
           )
         GROUP BY left_entity.entity_id,right_entity.entity_id,sentence.sentence_id,
                  left_head.token_id,right_head.token_id,left_anchor.object_id,right_anchor.object_id
    ), alias_evidence AS (
        SELECT right_object_id AS source_object_id,left_object_id AS target_object_id,
               6::SMALLINT AS witness_kind,right_token_id AS source_token_id,
               left_token_id AS target_token_id,sentence_id,
               'explicit-alias:'||cue_token_id::TEXT||':'||left_entity_id::TEXT||':'||right_entity_id::TEXT AS evidence_ref,
               1::SMALLINT AS candidate_count
          FROM alias_pair
    ), evidence AS (
        SELECT * FROM appos_evidence
        UNION ALL SELECT * FROM proper_name_evidence
        UNION ALL SELECT * FROM alias_evidence
    )
    INSERT INTO execution.semantic_pnf_identity_evidence_candidate
        (run_id,document_id,source_object_id,target_object_id,witness_kind,
         source_token_id,target_token_id,sentence_id,evidence_ref,candidate_count,evidence_state)
    SELECT selected_run_id,selected_document_id,source_object_id,target_object_id,
           witness_kind,source_token_id,target_token_id,sentence_id,evidence_ref,candidate_count,1
      FROM evidence
    ON CONFLICT (run_id,document_id,source_object_id,target_object_id,witness_kind,evidence_ref)
    DO UPDATE SET evidence_state=1,candidate_count=EXCLUDED.candidate_count,
                  source_token_id=EXCLUDED.source_token_id,
                  target_token_id=EXCLUDED.target_token_id,
                  sentence_id=EXCLUDED.sentence_id;

    SELECT count(*) INTO affected_count
      FROM execution.semantic_pnf_identity_evidence_candidate
     WHERE run_id=selected_run_id AND document_id=selected_document_id AND evidence_state=1;
    RETURN affected_count;
END;
$$;

-- Exact runtime check corresponding to CorpusLearningEconomy: for comparable
-- same-token workloads, fixed numeric work must be unchanged and unresolved
-- resolution work may not increase after reuse.
CREATE OR REPLACE FUNCTION execution.assert_numeric_pnf_learning_nonincrease(
    before_measurement_id BIGINT,
    after_measurement_id BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql STABLE AS $$
DECLARE before_row RECORD; after_row RECORD;
BEGIN
    SELECT * INTO before_row FROM execution.semantic_pnf_corpus_reuse_measurement
     WHERE measurement_id=before_measurement_id;
    SELECT * INTO after_row FROM execution.semantic_pnf_corpus_reuse_measurement
     WHERE measurement_id=after_measurement_id;
    IF before_row.measurement_id IS NULL OR after_row.measurement_id IS NULL THEN
        RAISE EXCEPTION 'unknown corpus reuse measurement';
    END IF;
    IF before_row.token_count<>after_row.token_count THEN
        RAISE EXCEPTION 'learning comparison requires same token workload';
    END IF;
    IF before_row.fixed_numeric_work<>after_row.fixed_numeric_work THEN
        RAISE EXCEPTION 'learning comparison requires unchanged fixed numeric work';
    END IF;
    RETURN after_row.unresolved_resolution_work<=before_row.unresolved_resolution_work;
END;
$$;

-- Batch ancestor compilation over selected document ids.  Semantic isolation is
-- preserved while scheduling may batch independent document fibres.
CREATE OR REPLACE FUNCTION execution.refresh_numeric_parser_token_ancestors_batch(
    selected_run_id BIGINT,
    selected_document_ids BIGINT[],
    selected_max_depth SMALLINT DEFAULT 8
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE item BIGINT; run_ref_value TEXT; document_ref_value TEXT; affected BIGINT:=0;
BEGIN
    SELECT run_ref INTO run_ref_value FROM execution.semantic_pnf_run_identity
     WHERE run_id=selected_run_id;
    FOREACH item IN ARRAY selected_document_ids LOOP
        SELECT document_ref INTO document_ref_value
          FROM execution.semantic_pnf_document_identity WHERE document_id=item;
        IF document_ref_value IS NOT NULL THEN
            affected:=affected+execution.refresh_numeric_parser_token_ancestors(
                run_ref_value,document_ref_value,selected_max_depth
            );
        END IF;
    END LOOP;
    RETURN affected;
END;
$$;

-- Cache lookup is proposal/reuse only: multiple entities for one label are
-- expected and returned in descending proof-bearing support order.
CREATE OR REPLACE FUNCTION execution.numeric_pnf_cached_entities_for_label(
    selected_label_symbol_id BIGINT,
    selected_limit INTEGER DEFAULT 16
) RETURNS TABLE(canonical_entity_id BIGINT,authority_class SMALLINT,
                admitted_support_count BIGINT)
LANGUAGE sql STABLE AS $$
SELECT cache.canonical_entity_id,cache.authority_class,cache.admitted_support_count
  FROM execution.semantic_pnf_corpus_entity_label_cache AS cache
 WHERE cache.label_symbol_id=selected_label_symbol_id
 ORDER BY cache.admitted_support_count DESC,cache.authority_class,cache.canonical_entity_id
 LIMIT LEAST(GREATEST(selected_limit,1),256);
$$;

COMMIT;
