BEGIN;

-- 171: migration 135 established producer-authored demand occurrence provenance
-- as the H9/proof authority seam, but reconstructed it one demand at a time and
-- looped over factor-support tokens. Preserve the exact fail-closed producer
-- semantics as one relational compilation over the affected demand fibre.
--
-- Only rows produced by the numeric-factor producer are replaced. Provenance
-- registered by other explicit producer APIs remains untouched.

DROP TRIGGER IF EXISTS semantic_pnf_demand_occurrence_producer
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.compile_numeric_pnf_demand_occurrence_batch(
    selected_demand_ids BIGINT[]
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected_count BIGINT := 0;
BEGIN
    IF selected_demand_ids IS NULL
       OR cardinality(selected_demand_ids)=0 THEN
        RETURN 0;
    END IF;

    DELETE FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
     WHERE provenance.demand_id=ANY(selected_demand_ids)
       AND provenance.producer_ref LIKE 'numeric-factor:%';

    WITH selected_demand AS MATERIALIZED (
        SELECT demand.demand_id,
               demand.source_region_id,
               demand.expected_factor_type_symbol_id,
               demand.lexical_symbol_id,
               demand.residual_type_symbol_id,
               region.start_char AS region_start_char,
               region.end_char AS region_end_char
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE demand.demand_id=ANY(selected_demand_ids)
           AND demand.expected_factor_type_symbol_id IS NOT NULL
           AND demand.lexical_symbol_id IS NOT NULL
    ), producer_match AS MATERIALIZED (
        SELECT DISTINCT demand.demand_id,
               demand.source_region_id,
               demand.region_start_char,
               demand.region_end_char,
               demand.residual_type_symbol_id,
               factor.factor_id,
               support.token_id
          FROM selected_demand AS demand
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.region_id=demand.source_region_id
           AND factor.factor_type_symbol_id=demand.expected_factor_type_symbol_id
          JOIN execution.semantic_pnf_factor_token_support AS support
            ON support.factor_id=factor.factor_id
          JOIN execution.semantic_parser_token AS token
            ON token.token_id=support.token_id
           AND token.representation_version=2
           AND token.lemma_symbol_id=demand.lexical_symbol_id
           AND token.start_char>=demand.region_start_char
           AND token.end_char<=demand.region_end_char
    ), producer AS MATERIALIZED (
        SELECT demand_id,
               min(source_region_id) AS source_region_id,
               min(region_start_char) AS region_start_char,
               min(region_end_char) AS region_end_char,
               min(residual_type_symbol_id) AS residual_type_symbol_id,
               min(factor_id) AS factor_id,
               min(token_id) AS trigger_token_id
          FROM producer_match
         GROUP BY demand_id
        HAVING count(*)=1
    ), support_token AS MATERIALIZED (
        SELECT producer.demand_id,
               producer.source_region_id,
               producer.residual_type_symbol_id,
               producer.factor_id,
               producer.trigger_token_id,
               support.token_id,
               support.ordinal
          FROM producer
          JOIN execution.semantic_pnf_factor_token_support AS support
            ON support.factor_id=producer.factor_id
          JOIN execution.semantic_parser_token AS token
            ON token.token_id=support.token_id
           AND token.representation_version=2
           AND token.start_char>=producer.region_start_char
           AND token.end_char<=producer.region_end_char
    ), token_object AS MATERIALIZED (
        SELECT support.demand_id,
               support.token_id,
               CASE
                 WHEN count(DISTINCT object.object_id)=1
                 THEN min(object.object_id)
                 ELSE NULL
               END AS object_id
          FROM support_token AS support
          LEFT JOIN execution.semantic_pnf_object_token_support AS object_support
            ON object_support.token_id=support.token_id
          LEFT JOIN execution.semantic_pnf_object AS object
            ON object.object_id=object_support.object_id
           AND object.region_id=support.source_region_id
         GROUP BY support.demand_id,support.token_id
    ), trigger_occurrence AS MATERIALIZED (
        SELECT producer.demand_id,
               1::SMALLINT AS occurrence_role,
               producer.trigger_token_id AS token_id,
               token_object.object_id,
               0::SMALLINT AS ordinal,
               'numeric-factor:'||producer.factor_id::TEXT AS producer_ref
          FROM producer
          LEFT JOIN token_object
            ON token_object.demand_id=producer.demand_id
           AND token_object.token_id=producer.trigger_token_id
    ), evidence_occurrence AS MATERIALIZED (
        SELECT support.demand_id,
               3::SMALLINT AS occurrence_role,
               support.token_id,
               token_object.object_id,
               (row_number() OVER (
                   PARTITION BY support.demand_id
                   ORDER BY support.ordinal,support.token_id
               )-1)::SMALLINT AS ordinal,
               'numeric-factor:'||support.factor_id::TEXT AS producer_ref
          FROM support_token AS support
          LEFT JOIN token_object
            ON token_object.demand_id=support.demand_id
           AND token_object.token_id=support.token_id
         WHERE support.token_id<>support.trigger_token_id
    ), target_match AS MATERIALIZED (
        SELECT DISTINCT producer.demand_id,
               support.token_id,
               edge.object_id,
               producer.factor_id
          FROM producer
          JOIN execution.semantic_pnf_demand_target_role_rule AS rule
            ON rule.residual_type_symbol_id=producer.residual_type_symbol_id
          JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.factor_id=producer.factor_id
           AND edge.role_symbol_id=rule.target_role_symbol_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=edge.object_id
           AND object.region_id=producer.source_region_id
          JOIN execution.semantic_pnf_object_token_support AS support
            ON support.object_id=edge.object_id
          JOIN execution.semantic_parser_token AS token
            ON token.token_id=support.token_id
           AND token.representation_version=2
           AND token.start_char>=producer.region_start_char
           AND token.end_char<=producer.region_end_char
    ), target_occurrence AS MATERIALIZED (
        SELECT demand_id,
               2::SMALLINT AS occurrence_role,
               min(token_id) AS token_id,
               min(object_id) AS object_id,
               0::SMALLINT AS ordinal,
               'numeric-factor:'||min(factor_id)::TEXT AS producer_ref
          FROM target_match
         GROUP BY demand_id
        HAVING count(*)=1
    ), occurrence AS (
        SELECT * FROM trigger_occurrence
        UNION ALL
        SELECT * FROM evidence_occurrence
        UNION ALL
        SELECT * FROM target_occurrence
    )
    INSERT INTO execution.semantic_pnf_demand_occurrence_provenance
        (demand_id,occurrence_role,token_id,object_id,ordinal,producer_ref)
    SELECT occurrence.demand_id,
           occurrence.occurrence_role,
           occurrence.token_id,
           occurrence.object_id,
           occurrence.ordinal,
           occurrence.producer_ref
      FROM occurrence
    ON CONFLICT(demand_id,occurrence_role,token_id,ordinal) DO UPDATE SET
        object_id=EXCLUDED.object_id,
        producer_ref=EXCLUDED.producer_ref;
    GET DIAGNOSTICS affected_count=ROW_COUNT;

    RETURN affected_count;
END;
$$;

CREATE OR REPLACE FUNCTION execution.compile_numeric_pnf_inserted_demand_occurrences()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_ids BIGINT[];
BEGIN
    SELECT array_agg(demand_id ORDER BY demand_id)
      INTO selected_ids
      FROM inserted_demand;
    PERFORM execution.compile_numeric_pnf_demand_occurrence_batch(selected_ids);
    RETURN NULL;
END;
$$;

-- Run after zzz_* demand normalizers. The helper reads current numeric demand
-- rows by id, so anaphor lexical surface cleanup and referent-kind normalization
-- are observed before provenance compilation.
CREATE TRIGGER zzzz_semantic_pnf_demand_occurrence_insert_batch
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.compile_numeric_pnf_inserted_demand_occurrences();

CREATE OR REPLACE FUNCTION execution.compile_numeric_pnf_updated_demand_occurrences()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_ids BIGINT[];
BEGIN
    SELECT array_agg(current.demand_id ORDER BY current.demand_id)
      INTO selected_ids
      FROM updated_demand AS current
      JOIN prior_demand AS prior USING(demand_id)
     WHERE current.state IS DISTINCT FROM prior.state
        OR current.source_region_id IS DISTINCT FROM prior.source_region_id
        OR current.expected_factor_type_symbol_id
             IS DISTINCT FROM prior.expected_factor_type_symbol_id
        OR current.lexical_symbol_id IS DISTINCT FROM prior.lexical_symbol_id
        OR current.residual_type_symbol_id
             IS DISTINCT FROM prior.residual_type_symbol_id;

    PERFORM execution.compile_numeric_pnf_demand_occurrence_batch(selected_ids);
    RETURN NULL;
END;
$$;

CREATE TRIGGER zzzz_semantic_pnf_demand_occurrence_update_batch
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.compile_numeric_pnf_updated_demand_occurrences();

COMMIT;
