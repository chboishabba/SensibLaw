BEGIN;

-- 097: provider results become durable local evidence and wake only the H9
-- fibres that depended on the deduplicated request.  External evidence still has
-- no constructor into canonical identity or ontology truth.

CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_external_request_members(
    selected_request_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
        (demand_id,consumer_ref,query_ref,policy_ref,horizon,work_state)
    SELECT member.demand_id,member.consumer_ref,member.query_ref,member.policy_ref,9,1
      FROM execution.semantic_pnf_external_request_member AS member
     WHERE member.request_id=selected_request_id
    ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)
    DO UPDATE SET work_state=1,completed_at=NULL;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- A provider property may become a contextual candidate requirement only when
-- the provider value has already been mapped to a corpus SymbolId and the request
-- names an explicit context axis.  This is classification/context pressure only.
CREATE OR REPLACE FUNCTION execution.materialize_numeric_pnf_external_context_requirement(
    selected_external_evidence_id BIGINT,
    selected_required_polarity SMALLINT DEFAULT 1
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE evidence RECORD;
BEGIN
    IF selected_required_polarity NOT IN (-1,1) THEN
        RAISE EXCEPTION 'required polarity must be -1 or +1';
    END IF;

    SELECT evidence.* INTO STRICT evidence
      FROM execution.semantic_pnf_external_evidence AS evidence
     WHERE evidence.external_evidence_id=selected_external_evidence_id;

    IF evidence.axis_kind IS NULL OR evidence.value_kind<>2 OR evidence.value_symbol_id IS NULL THEN
        RETURN FALSE;
    END IF;

    INSERT INTO execution.semantic_pnf_world_candidate_requirement
        (world_entity_id,axis_kind,required_symbol_id,required_polarity,
         requirement_revision,evidence_ref)
    VALUES (
        evidence.subject_world_entity_id,
        evidence.axis_kind,
        evidence.value_symbol_id,
        selected_required_polarity,
        COALESCE(evidence.provider_revision,1),
        'external-evidence:' || evidence.external_evidence_id::TEXT
    )
    ON CONFLICT(world_entity_id,axis_kind,required_symbol_id,required_polarity)
    DO UPDATE SET
        requirement_revision=GREATEST(
            execution.semantic_pnf_world_candidate_requirement.requirement_revision,
            EXCLUDED.requirement_revision
        ),
        evidence_ref=EXCLUDED.evidence_ref;
    RETURN TRUE;
END;
$$;

-- Replace 096's evidence recorder to additionally project eligible context facts
-- and wake only member fibres.  The immutable external-evidence row remains the
-- authority for the provider observation.
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
    ON CONFLICT(evidence_digest) DO UPDATE SET request_id=EXCLUDED.request_id
    RETURNING external_evidence_id INTO evidence_id_value;

    -- Only eligible symbol-valued/axis-typed evidence materializes a contextual
    -- requirement. World-entity/numeric values remain cached until an explicit
    -- adapter supplies the representation the consumer needs.
    PERFORM execution.materialize_numeric_pnf_external_context_requirement(
        evidence_id_value,1
    );

    UPDATE execution.semantic_pnf_external_request
       SET request_state=5,lease_owner=NULL,lease_expires_at=NULL,
           last_error_ref=NULL,updated_at=CURRENT_TIMESTAMP
     WHERE request_id=selected_request_id;

    PERFORM execution.wake_numeric_pnf_external_request_members(selected_request_id);
    RETURN evidence_id_value;
END;
$$;

CREATE OR REPLACE FUNCTION execution.complete_numeric_pnf_external_request(
    selected_request_id BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
BEGIN
    UPDATE execution.semantic_pnf_external_request
       SET request_state=5,lease_owner=NULL,lease_expires_at=NULL,
           last_error_ref=NULL,updated_at=CURRENT_TIMESTAMP
     WHERE request_id=selected_request_id;
    IF NOT FOUND THEN RETURN FALSE; END IF;
    PERFORM execution.wake_numeric_pnf_external_request_members(selected_request_id);
    RETURN TRUE;
END;
$$;

-- Cache-hit requests also need no network acquisition, but their consumers must
-- be allowed to resume H9 against the newly visible local cache.
CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_external_cache_hits()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    WITH cache_hit AS (
        SELECT request_id
          FROM execution.semantic_pnf_external_request
         WHERE request_state=2
    )
    INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
        (demand_id,consumer_ref,query_ref,policy_ref,horizon,work_state)
    SELECT member.demand_id,member.consumer_ref,member.query_ref,member.policy_ref,9,1
      FROM cache_hit
      JOIN execution.semantic_pnf_external_request_member AS member USING (request_id)
    ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)
    DO UPDATE SET work_state=1,completed_at=NULL;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

COMMIT;
