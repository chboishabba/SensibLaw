BEGIN;

-- 108: cold external evidence retains full acquisition history, while the hot
-- contextual projection for a request sees only evidence satisfying that
-- request's current freshness floor.  Evidence persistence itself remains
-- projection-free; successful lease-aware completion or a cache hit performs
-- the active projection.

CREATE OR REPLACE FUNCTION execution.materialize_numeric_pnf_external_context_for_request(
    selected_request_id BIGINT,
    selected_required_polarity SMALLINT DEFAULT 1
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE request RECORD; evidence RECORD; affected BIGINT := 0; n BIGINT := 0;
BEGIN
    IF selected_required_polarity NOT IN (-1,1) THEN
        RAISE EXCEPTION 'required polarity must be -1 or +1';
    END IF;
    SELECT request.* INTO STRICT request
      FROM execution.semantic_pnf_external_request AS request
     WHERE request.request_id=selected_request_id;
    IF request.request_kind<>2 OR request.axis_kind IS NULL THEN
        RETURN 0;
    END IF;

    FOR evidence IN
        SELECT evidence.*
          FROM execution.semantic_pnf_external_evidence AS evidence
         WHERE evidence.provider_id=request.provider_id
           AND evidence.subject_world_entity_id=request.world_entity_id
           AND evidence.provider_property_numeric_id=request.provider_property_numeric_id
           AND evidence.value_kind=2
           AND evidence.value_symbol_id IS NOT NULL
           AND (
               request.minimum_source_epoch IS NULL
               OR evidence.source_epoch>=request.minimum_source_epoch
           )
         ORDER BY evidence.source_epoch DESC NULLS LAST,evidence.external_evidence_id
    LOOP
        INSERT INTO execution.semantic_pnf_world_candidate_requirement
            (world_entity_id,axis_kind,required_symbol_id,required_polarity,
             requirement_revision,evidence_ref)
        VALUES (
            request.world_entity_id,
            request.axis_kind,
            evidence.value_symbol_id,
            selected_required_polarity,
            COALESCE(evidence.provider_revision,1),
            'external-evidence:' || evidence.external_evidence_id::TEXT
                || ':request:' || selected_request_id::TEXT
        )
        ON CONFLICT(world_entity_id,axis_kind,required_symbol_id,required_polarity)
        DO UPDATE SET
            requirement_revision=GREATEST(
                execution.semantic_pnf_world_candidate_requirement.requirement_revision,
                EXCLUDED.requirement_revision
            ),
            evidence_ref=EXCLUDED.evidence_ref;
        GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;
    END LOOP;
    RETURN affected;
END;
$$;

-- Cold evidence persistence only.  No request state change, wakeup, or active
-- contextual projection occurs until the lease freshness contract is validated.
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
    RETURN evidence_id_value;
END;
$$;

CREATE OR REPLACE FUNCTION execution.complete_numeric_pnf_external_request(
    selected_request_id BIGINT,
    leased_minimum_source_epoch BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE current_floor BIGINT;
BEGIN
    SELECT minimum_source_epoch INTO STRICT current_floor
      FROM execution.semantic_pnf_external_request
     WHERE request_id=selected_request_id
     FOR UPDATE;

    IF current_floor IS DISTINCT FROM leased_minimum_source_epoch THEN
        UPDATE execution.semantic_pnf_external_request
           SET request_state=1,lease_owner=NULL,lease_expires_at=NULL,
               last_error_ref='freshness-contract-changed-during-lease',
               updated_at=CURRENT_TIMESTAMP
         WHERE request_id=selected_request_id;
        RETURN FALSE;
    END IF;

    -- Only evidence satisfying the accepted current contract enters the hot
    -- contextual projection.  Empty results project nothing and therefore do
    -- not become negative semantic evidence.
    PERFORM execution.materialize_numeric_pnf_external_context_for_request(
        selected_request_id,1
    );

    UPDATE execution.semantic_pnf_external_request
       SET request_state=5,lease_owner=NULL,lease_expires_at=NULL,
           last_error_ref=NULL,updated_at=CURRENT_TIMESTAMP
     WHERE request_id=selected_request_id;
    PERFORM execution.wake_numeric_pnf_external_request_members(selected_request_id);
    RETURN TRUE;
END;
$$;

-- Retain 099's cache-hit behaviour, now using the freshness-filtered projection.
CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_external_cache_hits()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE request RECORD; affected BIGINT := 0; n BIGINT := 0;
BEGIN
    FOR request IN
        SELECT request_id
          FROM execution.semantic_pnf_external_request
         WHERE request_state=2
         ORDER BY request_id
    LOOP
        PERFORM execution.materialize_numeric_pnf_external_context_for_request(
            request.request_id,1
        );
        INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
            (demand_id,consumer_ref,query_ref,policy_ref,horizon,work_state)
        SELECT member.demand_id,member.consumer_ref,member.query_ref,
               member.policy_ref,9,1
          FROM execution.semantic_pnf_external_request_member AS member
         WHERE member.request_id=request.request_id
        ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)
        DO UPDATE SET work_state=1,completed_at=NULL;
        GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;
    END LOOP;
    RETURN affected;
END;
$$;

COMMIT;
