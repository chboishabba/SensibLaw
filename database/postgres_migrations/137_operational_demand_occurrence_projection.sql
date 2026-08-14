BEGIN;

-- 137: the ordinary compile_corpus.py path persists resolution.demand, while
-- H3/H6/H9 execute over execution.semantic_pnf_demand.  Preserve the producer
-- occurrence coordinates at the operational boundary and project them into the
-- numeric carrier only when the exact parser token and numeric demand are
-- uniquely identified.
CREATE TABLE IF NOT EXISTS resolution.demand_occurrence_provenance (
    demand_ref TEXT NOT NULL
        REFERENCES resolution.demand(demand_ref) ON DELETE CASCADE,
    residual_type_ref TEXT NOT NULL,
    occurrence_role SMALLINT NOT NULL CHECK (occurrence_role IN (1,2,3)),
    parser_token_ref TEXT NOT NULL,
    numeric_token_id BIGINT
        REFERENCES execution.semantic_parser_token(token_id) ON DELETE SET NULL,
    semantic_role_ref TEXT,
    ordinal SMALLINT NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    producer_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        demand_ref,residual_type_ref,occurrence_role,parser_token_ref,ordinal
    )
);

CREATE INDEX IF NOT EXISTS resolution_demand_occurrence_numeric_token_idx
    ON resolution.demand_occurrence_provenance
       (numeric_token_id,demand_ref,residual_type_ref)
    WHERE numeric_token_id IS NOT NULL;

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
           WHERE provenance.numeric_token_id IS NOT NULL
             AND provenance.occurrence_role=1
       )::BIGINT AS numeric_trigger_count,
       count(*) FILTER (
           WHERE provenance.numeric_token_id IS NOT NULL
             AND provenance.occurrence_role=2
       )::BIGINT AS numeric_target_count
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
    candidate_count BIGINT;
    selected_object_id BIGINT;
    object_count BIGINT;
    inserted_count BIGINT := 0;
BEGIN
    FOR residual_row IN
        SELECT DISTINCT provenance.residual_type_ref,
               demand.subject_kind_ref,
               trigger.numeric_token_id AS trigger_token_id
          FROM resolution.demand_occurrence_provenance AS provenance
          JOIN resolution.demand AS demand
            ON demand.demand_ref=provenance.demand_ref
          JOIN resolution.demand_occurrence_provenance AS trigger
            ON trigger.demand_ref=provenance.demand_ref
           AND trigger.residual_type_ref=provenance.residual_type_ref
           AND trigger.occurrence_role=1
         WHERE provenance.demand_ref=selected_demand_ref
           AND trigger.numeric_token_id IS NOT NULL
    LOOP
        -- The operational demand supplies the exact trigger occurrence.  Use it
        -- only to identify the corresponding numeric demand in the same parser
        -- sentence/PNF region with the same factor type, residual type and
        -- lexical trigger.  Ambiguity is unresolved, never ranked away.
        SELECT count(*),min(candidate.demand_id),min(candidate.source_region_id)
          INTO candidate_count,selected_numeric_demand_id,selected_source_region_id
          FROM (
              SELECT DISTINCT demand.demand_id,demand.source_region_id
                FROM execution.semantic_parser_token AS trigger_token
                JOIN execution.semantic_pnf_sentence_region AS sentence_region
                  ON sentence_region.sentence_id=trigger_token.sentence_id
                JOIN execution.semantic_pnf_demand AS demand
                  ON demand.source_region_id=sentence_region.region_id
                JOIN execution.semantic_symbol AS residual_symbol
                  ON residual_symbol.symbol_id=demand.residual_type_symbol_id
                JOIN execution.semantic_symbol AS factor_type_symbol
                  ON factor_type_symbol.symbol_id=demand.expected_factor_type_symbol_id
               WHERE trigger_token.token_id=residual_row.trigger_token_id
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
               AND provenance.numeric_token_id IS NOT NULL
             ORDER BY provenance.occurrence_role,provenance.ordinal,
                      provenance.parser_token_ref
        LOOP
            selected_object_id := NULL;
            object_count := 0;
            SELECT count(DISTINCT support.object_id),min(support.object_id)
              INTO object_count,selected_object_id
              FROM execution.semantic_pnf_object_token_support AS support
              JOIN execution.semantic_pnf_object AS object
                ON object.object_id=support.object_id
             WHERE support.token_id=provenance_row.numeric_token_id
               AND object.region_id=selected_source_region_id
               AND object.active;

            IF object_count<>1 THEN
                selected_object_id := NULL;
            END IF;

            -- A target without an exact object witness cannot authorize H9.
            IF provenance_row.occurrence_role=2
               AND selected_object_id IS NULL THEN
                CONTINUE;
            END IF;

            PERFORM execution.register_numeric_pnf_demand_occurrence(
                selected_numeric_demand_id,
                provenance_row.occurrence_role,
                provenance_row.numeric_token_id,
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

-- This verifier proves only the transport invariant.  It does not claim that a
-- target exists when the producer did not author one.
CREATE OR REPLACE FUNCTION execution.verify_resolution_demand_occurrence_projection()
RETURNS TABLE(check_name TEXT,violation_count BIGINT)
LANGUAGE sql
STABLE
AS $$
    SELECT 'operational_numeric_token_document_mismatch'::TEXT,
           count(*)::BIGINT
      FROM resolution.demand_occurrence_provenance AS provenance
      JOIN resolution.demand AS demand
        ON demand.demand_ref=provenance.demand_ref
      JOIN execution.semantic_parser_token AS token
        ON token.token_id=provenance.numeric_token_id
     WHERE provenance.numeric_token_id IS NOT NULL
       AND token.document_ref<>demand.scope_ref
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
