BEGIN;

-- 137: compile_corpus.py persists resolution.demand while H3/H6/H9 execute on
-- execution.semantic_pnf_demand. Persist the producer's immutable parser-token
-- reference immediately. Exact numeric document coordinates may be filled on a
-- later replay if the numeric parser tape is not present yet.
-- No text, nearest-noun, NER trimming or cross-region recovery is permitted.
CREATE TABLE IF NOT EXISTS resolution.demand_occurrence_provenance (
    demand_ref TEXT NOT NULL
        REFERENCES resolution.demand(demand_ref) ON DELETE CASCADE,
    residual_type_ref TEXT NOT NULL,
    occurrence_role SMALLINT NOT NULL CHECK (occurrence_role IN (1,2,3)),
    parser_token_ref TEXT NOT NULL,
    document_ref TEXT NOT NULL,
    start_char BIGINT,
    end_char BIGINT,
    semantic_role_ref TEXT,
    ordinal SMALLINT NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    producer_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        demand_ref,residual_type_ref,occurrence_role,parser_token_ref,ordinal
    ),
    CHECK (
        (start_char IS NULL AND end_char IS NULL)
        OR (
            start_char IS NOT NULL
            AND end_char IS NOT NULL
            AND start_char >= 0
            AND end_char > start_char
        )
    )
);

CREATE INDEX IF NOT EXISTS resolution_demand_occurrence_coordinate_idx
    ON resolution.demand_occurrence_provenance
       (document_ref,start_char,end_char,demand_ref,residual_type_ref)
    WHERE start_char IS NOT NULL AND end_char IS NOT NULL;

CREATE OR REPLACE VIEW resolution.demand_occurrence_provenance_audit_v1 AS
SELECT demand.demand_ref,
       provenance.residual_type_ref,
       count(*) FILTER (WHERE provenance.occurrence_role=1)::BIGINT
           AS trigger_count,
       count(*) FILTER (WHERE provenance.occurrence_role=2)::BIGINT
           AS target_count,
       count(*) FILTER (WHERE provenance.occurrence_role=3)::BIGINT
           AS evidence_count,
       count(*) FILTER (
           WHERE provenance.start_char IS NULL
              OR provenance.end_char IS NULL
       )::BIGINT AS unresolved_coordinate_count,
       count(*) FILTER (
           WHERE provenance.occurrence_role=1
             AND provenance.start_char IS NOT NULL
             AND provenance.end_char IS NOT NULL
             AND EXISTS (
                 SELECT 1
                   FROM execution.semantic_parser_token AS token
                  WHERE token.document_ref=provenance.document_ref
                    AND token.start_char=provenance.start_char
                    AND token.end_char=provenance.end_char
                    AND token.representation_version=2
             )
       )::BIGINT AS numeric_trigger_coordinate_count,
       count(*) FILTER (
           WHERE provenance.occurrence_role=2
             AND provenance.start_char IS NOT NULL
             AND provenance.end_char IS NOT NULL
             AND EXISTS (
                 SELECT 1
                   FROM execution.semantic_parser_token AS token
                  WHERE token.document_ref=provenance.document_ref
                    AND token.start_char=provenance.start_char
                    AND token.end_char=provenance.end_char
                    AND token.representation_version=2
             )
       )::BIGINT AS numeric_target_coordinate_count
  FROM resolution.demand AS demand
  LEFT JOIN resolution.demand_occurrence_provenance AS provenance
    ON provenance.demand_ref=demand.demand_ref
 GROUP BY demand.demand_ref,provenance.residual_type_ref;

CREATE OR REPLACE FUNCTION execution.project_resolution_demand_occurrence_to_numeric_pnf(
    selected_demand_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    residual_row RECORD;
    provenance_row RECORD;
    selected_numeric_demand_id BIGINT;
    selected_source_region_id BIGINT;
    selected_run_ref TEXT;
    candidate_count BIGINT;
    selected_numeric_token_id BIGINT;
    token_count BIGINT;
    selected_object_id BIGINT;
    object_count BIGINT;
    inserted_count BIGINT := 0;
BEGIN
    FOR residual_row IN
        SELECT DISTINCT provenance.residual_type_ref,
               demand.subject_kind_ref,
               trigger.document_ref,
               trigger.start_char AS trigger_start_char,
               trigger.end_char AS trigger_end_char
          FROM resolution.demand_occurrence_provenance AS provenance
          JOIN resolution.demand AS demand
            ON demand.demand_ref=provenance.demand_ref
          JOIN resolution.demand_occurrence_provenance AS trigger
            ON trigger.demand_ref=provenance.demand_ref
           AND trigger.residual_type_ref=provenance.residual_type_ref
           AND trigger.occurrence_role=1
         WHERE provenance.demand_ref=selected_demand_ref
           AND trigger.start_char IS NOT NULL
           AND trigger.end_char IS NOT NULL
    LOOP
        -- The exact trigger coordinate identifies the corresponding numeric
        -- demand only if one parser run + sentence region + factor/residual key
        -- survives. Multiple historical runs fail closed rather than being
        -- silently ranked.
        SELECT count(*),min(candidate.demand_id),min(candidate.source_region_id),
               min(candidate.run_ref)
          INTO candidate_count,selected_numeric_demand_id,
               selected_source_region_id,selected_run_ref
          FROM (
              SELECT DISTINCT demand.demand_id,demand.source_region_id,region.run_ref
                FROM execution.semantic_parser_token AS trigger_token
                JOIN execution.semantic_pnf_sentence_region AS sentence_region
                  ON sentence_region.sentence_id=trigger_token.sentence_id
                JOIN execution.semantic_pnf_region AS region
                  ON region.region_id=sentence_region.region_id
                 AND region.run_ref=trigger_token.run_ref
                 AND region.document_ref=trigger_token.document_ref
                JOIN execution.semantic_pnf_demand AS demand
                  ON demand.source_region_id=sentence_region.region_id
                JOIN execution.semantic_symbol AS residual_symbol
                  ON residual_symbol.symbol_id=demand.residual_type_symbol_id
                JOIN execution.semantic_symbol AS factor_type_symbol
                  ON factor_type_symbol.symbol_id=demand.expected_factor_type_symbol_id
               WHERE trigger_token.document_ref=residual_row.document_ref
                 AND trigger_token.start_char=residual_row.trigger_start_char
                 AND trigger_token.end_char=residual_row.trigger_end_char
                 AND trigger_token.representation_version=2
                 AND demand.lexical_symbol_id=trigger_token.lemma_symbol_id
                 AND residual_symbol.kind_id=13
                 AND residual_symbol.symbol_text=residual_row.residual_type_ref
                 AND factor_type_symbol.symbol_text=residual_row.subject_kind_ref
          ) AS candidate;

        IF candidate_count<>1 OR selected_numeric_demand_id IS NULL THEN
            CONTINUE;
        END IF;

        FOR provenance_row IN
            SELECT provenance.*
              FROM resolution.demand_occurrence_provenance AS provenance
             WHERE provenance.demand_ref=selected_demand_ref
               AND provenance.residual_type_ref=residual_row.residual_type_ref
             ORDER BY provenance.occurrence_role,provenance.ordinal,
                      provenance.parser_token_ref
        LOOP
            IF provenance_row.start_char IS NULL
               OR provenance_row.end_char IS NULL THEN
                CONTINUE;
            END IF;

            selected_numeric_token_id := NULL;
            token_count := 0;
            SELECT count(*),min(token.token_id)
              INTO token_count,selected_numeric_token_id
              FROM execution.semantic_parser_token AS token
             WHERE token.run_ref=selected_run_ref
               AND token.document_ref=provenance_row.document_ref
               AND token.start_char=provenance_row.start_char
               AND token.end_char=provenance_row.end_char
               AND token.representation_version=2;
            IF token_count<>1 OR selected_numeric_token_id IS NULL THEN
                CONTINUE;
            END IF;

            selected_object_id := NULL;
            object_count := 0;
            SELECT count(DISTINCT support.object_id),min(support.object_id)
              INTO object_count,selected_object_id
              FROM execution.semantic_pnf_object_token_support AS support
              JOIN execution.semantic_pnf_object AS object
                ON object.object_id=support.object_id
             WHERE support.token_id=selected_numeric_token_id
               AND object.region_id=selected_source_region_id
               AND object.active;
            IF object_count<>1 THEN
                selected_object_id := NULL;
            END IF;

            -- A target without an exact object witness is not H9 authority.
            IF provenance_row.occurrence_role=2
               AND selected_object_id IS NULL THEN
                CONTINUE;
            END IF;

            PERFORM execution.register_numeric_pnf_demand_occurrence(
                selected_numeric_demand_id,
                provenance_row.occurrence_role,
                selected_numeric_token_id,
                selected_object_id,
                provenance_row.ordinal,
                'operational-demand:'||selected_demand_ref
            );
            inserted_count := inserted_count + 1;
        END LOOP;
    END LOOP;

    RETURN inserted_count;
END;
$$;

CREATE OR REPLACE FUNCTION execution.verify_resolution_demand_occurrence_projection()
RETURNS TABLE(check_name TEXT,violation_count BIGINT)
LANGUAGE sql
STABLE
AS $$
    SELECT 'operational_occurrence_document_mismatch'::TEXT,
           count(*)::BIGINT
      FROM resolution.demand_occurrence_provenance AS provenance
      JOIN resolution.demand AS demand
        ON demand.demand_ref=provenance.demand_ref
     WHERE provenance.document_ref<>demand.scope_ref
    UNION ALL
    SELECT 'operational_half_coordinate'::TEXT,
           count(*)::BIGINT
      FROM resolution.demand_occurrence_provenance AS provenance
     WHERE (provenance.start_char IS NULL)<>(provenance.end_char IS NULL)
    UNION ALL
    SELECT 'projected_target_without_exact_object_support'::TEXT,
           count(*)::BIGINT
      FROM execution.semantic_pnf_demand_occurrence_provenance AS target
     WHERE target.occurrence_role=2
       AND target.producer_ref LIKE 'operational-demand:%'
       AND (
           target.object_id IS NULL
           OR NOT EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_object_token_support AS support
                WHERE support.object_id=target.object_id
                  AND support.token_id=target.token_id
           )
       );
$$;

COMMIT;
