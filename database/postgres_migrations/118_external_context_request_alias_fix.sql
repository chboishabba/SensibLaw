BEGIN;

-- 118: avoid the PL/pgSQL variable/table-alias collision in the external
-- context projection. Discovery completions call this function before the
-- request-kind fast return, so the ambiguity is observable on every provider
-- result even when no property projection is needed.

CREATE OR REPLACE FUNCTION execution.materialize_numeric_pnf_external_context_for_request(
    selected_request_id BIGINT,
    selected_required_polarity SMALLINT DEFAULT 1
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE
    selected_request RECORD;
    selected_epoch BIGINT;
    affected BIGINT := 0;
    n BIGINT := 0;
BEGIN
    IF selected_required_polarity NOT IN (-1,1) THEN
        RAISE EXCEPTION 'required polarity must be -1 or +1';
    END IF;

    SELECT request_row.* INTO STRICT selected_request
      FROM execution.semantic_pnf_external_request AS request_row
     WHERE request_row.request_id=selected_request_id;
    IF selected_request.request_kind<>2 OR selected_request.axis_kind IS NULL THEN
        RETURN 0;
    END IF;

    SELECT max(evidence.source_epoch)
      INTO selected_epoch
      FROM execution.semantic_pnf_external_evidence AS evidence
     WHERE evidence.provider_id=selected_request.provider_id
       AND evidence.subject_world_entity_id=selected_request.world_entity_id
       AND evidence.provider_property_numeric_id=selected_request.provider_property_numeric_id
       AND evidence.value_kind=2
       AND evidence.value_symbol_id IS NOT NULL
       AND (
           selected_request.minimum_source_epoch IS NULL
           OR evidence.source_epoch>=selected_request.minimum_source_epoch
       );

    DELETE FROM execution.semantic_pnf_world_candidate_requirement AS requirement
     WHERE requirement.world_entity_id=selected_request.world_entity_id
       AND requirement.axis_kind=selected_request.axis_kind
       AND requirement.provider_property_numeric_id=selected_request.provider_property_numeric_id
       AND requirement.external_evidence_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_external_evidence AS evidence
            WHERE evidence.external_evidence_id=requirement.external_evidence_id
              AND evidence.provider_id=selected_request.provider_id
              AND evidence.subject_world_entity_id=selected_request.world_entity_id
              AND evidence.provider_property_numeric_id=selected_request.provider_property_numeric_id
              AND evidence.value_kind=2
              AND evidence.value_symbol_id IS NOT NULL
              AND (
                  (selected_epoch IS NOT NULL AND evidence.source_epoch=selected_epoch)
                  OR
                  (selected_epoch IS NULL
                   AND selected_request.minimum_source_epoch IS NULL
                   AND evidence.source_epoch IS NULL)
              )
       );
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    INSERT INTO execution.semantic_pnf_world_candidate_requirement
        (world_entity_id,axis_kind,required_symbol_id,required_polarity,
         requirement_revision,evidence_ref,external_evidence_id,
         provider_property_numeric_id,source_epoch)
    SELECT selected_request.world_entity_id,
           selected_request.axis_kind,
           evidence.value_symbol_id,
           selected_required_polarity,
           COALESCE(evidence.provider_revision,1),
           'external-evidence:' || evidence.external_evidence_id::TEXT
               || ':request:' || selected_request_id::TEXT,
           evidence.external_evidence_id,
           evidence.provider_property_numeric_id,
           evidence.source_epoch
      FROM execution.semantic_pnf_external_evidence AS evidence
     WHERE evidence.provider_id=selected_request.provider_id
       AND evidence.subject_world_entity_id=selected_request.world_entity_id
       AND evidence.provider_property_numeric_id=selected_request.provider_property_numeric_id
       AND evidence.value_kind=2
       AND evidence.value_symbol_id IS NOT NULL
       AND (
           (selected_epoch IS NOT NULL AND evidence.source_epoch=selected_epoch)
           OR
           (selected_epoch IS NULL
            AND selected_request.minimum_source_epoch IS NULL
            AND evidence.source_epoch IS NULL)
       )
    ON CONFLICT(world_entity_id,axis_kind,required_symbol_id,required_polarity)
    DO UPDATE SET
        requirement_revision=GREATEST(
            execution.semantic_pnf_world_candidate_requirement.requirement_revision,
            EXCLUDED.requirement_revision
        ),
        evidence_ref=EXCLUDED.evidence_ref,
        external_evidence_id=EXCLUDED.external_evidence_id,
        provider_property_numeric_id=EXCLUDED.provider_property_numeric_id,
        source_epoch=EXCLUDED.source_epoch;
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    RETURN affected;
END;
$$;

COMMIT;
