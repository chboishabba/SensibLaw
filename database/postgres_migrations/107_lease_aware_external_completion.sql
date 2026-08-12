BEGIN;

-- 107: evidence persistence is not request completion.  A worker may have
-- leased under an older freshness floor while another consumer tightens the
-- shared request.  Persist returned evidence immutably, but only the explicit
-- lease-aware completion gate may mark the request acquired and wake H9.

CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_external_evidence(
    selected_request_id BIGINT,
    selected_evidence_digest BYTEA,
    selected_subject_world_entity_id BIGINT,
    selected_provider_property_numeric_id BIGINT,
    selected_axis_kind SMALLINT,
    selected_value_kind SMALLINT,
    selected_value_world_entity_id BIGINT,
    selected_value_symbol_id BIGINT,
    selected_value_numeric BIGINT,
    selected_provider_revision BIGINT,
    selected_source_ref TEXT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE provider_value SMALLINT; evidence_id_value BIGINT;
BEGIN
    SELECT provider_id INTO STRICT provider_value
      FROM execution.semantic_pnf_external_request
     WHERE request_id=selected_request_id;

    INSERT INTO execution.semantic_pnf_external_evidence
        (evidence_digest,request_id,provider_id,subject_world_entity_id,
         provider_property_numeric_id,axis_kind,value_kind,value_world_entity_id,
         value_symbol_id,value_numeric,provider_revision,source_ref)
    VALUES (selected_evidence_digest,selected_request_id,provider_value,
            selected_subject_world_entity_id,selected_provider_property_numeric_id,
            selected_axis_kind,selected_value_kind,selected_value_world_entity_id,
            selected_value_symbol_id,selected_value_numeric,selected_provider_revision,
            selected_source_ref)
    ON CONFLICT(evidence_digest) DO NOTHING
    RETURNING external_evidence_id INTO evidence_id_value;

    IF evidence_id_value IS NULL THEN
        SELECT external_evidence_id INTO STRICT evidence_id_value
          FROM execution.semantic_pnf_external_evidence
         WHERE evidence_digest=selected_evidence_digest;
    END IF;

    -- This is contextual pressure only.  Do not mark the external request
    -- complete or wake consumers here; completion must first validate the lease
    -- freshness contract.
    PERFORM execution.materialize_numeric_pnf_external_context_requirement(
        evidence_id_value,1
    );
    RETURN evidence_id_value;
END;
$$;

-- Simplify the need setter introduced in 103: update the semantic need and let
-- the 106 AFTER UPDATE trigger recompute the exact maximum across all active
-- member fibres. This permits both strengthening and relaxation.
CREATE OR REPLACE FUNCTION execution.set_numeric_pnf_external_need_minimum_source_epoch(
    selected_need_id BIGINT,
    selected_minimum_source_epoch BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
BEGIN
    IF selected_minimum_source_epoch IS NOT NULL
       AND selected_minimum_source_epoch<=0 THEN
        RAISE EXCEPTION 'minimum source epoch must be positive';
    END IF;
    UPDATE execution.semantic_pnf_consumer_external_need
       SET minimum_source_epoch=selected_minimum_source_epoch
     WHERE need_id=selected_need_id;
    RETURN FOUND;
END;
$$;

COMMIT;
