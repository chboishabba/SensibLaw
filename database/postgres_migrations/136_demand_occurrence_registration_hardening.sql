BEGIN;

-- 136: exact occurrence registration is document-scoped, not merely offset-
-- scoped. Two documents may share the same numeric character interval.
CREATE OR REPLACE FUNCTION execution.register_numeric_pnf_demand_occurrence(
    selected_demand_id BIGINT,
    selected_occurrence_role SMALLINT,
    selected_token_id BIGINT,
    selected_object_id BIGINT,
    selected_ordinal SMALLINT,
    selected_producer_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_source_region_id BIGINT;
    existing_object_count BIGINT := 0;
BEGIN
    IF selected_occurrence_role NOT IN (1,2,3) THEN
        RAISE EXCEPTION 'invalid demand occurrence role %',selected_occurrence_role;
    END IF;
    IF selected_ordinal<0 THEN
        RAISE EXCEPTION 'negative demand occurrence ordinal %',selected_ordinal;
    END IF;
    IF selected_producer_ref IS NULL OR selected_producer_ref='' THEN
        RAISE EXCEPTION 'demand occurrence producer_ref must be non-empty';
    END IF;

    SELECT demand.source_region_id
      INTO selected_source_region_id
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
      JOIN execution.semantic_parser_token AS token
        ON token.token_id=selected_token_id
       AND token.representation_version=2
       AND token.run_ref=region.run_ref
       AND token.document_ref=region.document_ref
       AND token.start_char>=region.start_char
       AND token.end_char<=region.end_char
     WHERE demand.demand_id=selected_demand_id;

    IF selected_source_region_id IS NULL THEN
        RAISE EXCEPTION
            'token % is not an exact occurrence inside demand % source region',
            selected_token_id,selected_demand_id;
    END IF;

    IF selected_object_id IS NOT NULL THEN
        SELECT count(*) INTO existing_object_count
          FROM execution.semantic_pnf_object_token_support AS support
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id=support.object_id
         WHERE support.object_id=selected_object_id
           AND support.token_id=selected_token_id
           AND object.region_id=selected_source_region_id;
        IF existing_object_count<>1 THEN
            RAISE EXCEPTION
                'object % does not exactly support demand occurrence token % in region %',
                selected_object_id,selected_token_id,selected_source_region_id;
        END IF;
    END IF;

    INSERT INTO execution.semantic_pnf_demand_occurrence_provenance
        (demand_id,occurrence_role,token_id,object_id,ordinal,producer_ref)
    VALUES (
        selected_demand_id,selected_occurrence_role,selected_token_id,
        selected_object_id,selected_ordinal,selected_producer_ref
    )
    ON CONFLICT(demand_id,occurrence_role,token_id,ordinal) DO UPDATE SET
        object_id=EXCLUDED.object_id,
        producer_ref=EXCLUDED.producer_ref;
    RETURN 1;
END;
$$;

CREATE OR REPLACE FUNCTION execution.verify_numeric_pnf_demand_occurrence_provenance()
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE invalid_count BIGINT := 0;
BEGIN
    SELECT count(*) INTO invalid_count
      FROM execution.semantic_pnf_demand_occurrence_provenance AS provenance
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id=provenance.demand_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
      LEFT JOIN execution.semantic_parser_token AS token
        ON token.token_id=provenance.token_id
       AND token.representation_version=2
       AND token.run_ref=region.run_ref
       AND token.document_ref=region.document_ref
       AND token.start_char>=region.start_char
       AND token.end_char<=region.end_char
     WHERE token.token_id IS NULL
        OR (
            provenance.object_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                  FROM execution.semantic_pnf_object_token_support AS support
                  JOIN execution.semantic_pnf_object AS object
                    ON object.object_id=support.object_id
                 WHERE support.object_id=provenance.object_id
                   AND support.token_id=provenance.token_id
                   AND object.region_id=demand.source_region_id
            )
        );

    IF invalid_count<>0 THEN
        RAISE EXCEPTION 'invalid demand occurrence provenance rows: %',invalid_count;
    END IF;
    RETURN TRUE;
END;
$$;

SELECT execution.verify_numeric_pnf_demand_occurrence_provenance();

COMMIT;
