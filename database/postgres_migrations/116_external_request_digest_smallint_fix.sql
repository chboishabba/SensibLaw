BEGIN;

-- Keep the request digest byte layout stable while preserving SMALLINT typing
-- through COALESCE. PostgreSQL otherwise widens the NULL fallback literal to
-- INTEGER, which makes int2send fail at runtime.
CREATE OR REPLACE FUNCTION execution.ensure_numeric_pnf_external_request(
    selected_provider_id SMALLINT,
    selected_request_kind SMALLINT,
    selected_label_symbol_id BIGINT,
    selected_world_entity_id BIGINT,
    selected_provider_property_numeric_id BIGINT,
    selected_axis_kind SMALLINT,
    selected_request_revision BIGINT,
    selected_priority SMALLINT DEFAULT 100
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE digest_value BYTEA; resolved_request_id BIGINT;
BEGIN
    digest_value := digest(
        int2send(selected_provider_id)
        || int2send(selected_request_kind)
        || int8send(COALESCE(selected_label_symbol_id,0))
        || int8send(COALESCE(selected_world_entity_id,0))
        || int8send(COALESCE(selected_provider_property_numeric_id,0))
        || int2send(COALESCE(selected_axis_kind,0::smallint))
        || int8send(selected_request_revision),
        'sha256'
    );

    INSERT INTO execution.semantic_pnf_external_request
        (request_digest,provider_id,request_kind,label_symbol_id,world_entity_id,
         provider_property_numeric_id,axis_kind,request_revision,priority)
    VALUES (digest_value,selected_provider_id,selected_request_kind,
            selected_label_symbol_id,selected_world_entity_id,
            selected_provider_property_numeric_id,selected_axis_kind,
            selected_request_revision,selected_priority)
    ON CONFLICT(request_digest) DO UPDATE SET
        priority=LEAST(execution.semantic_pnf_external_request.priority,EXCLUDED.priority),
        updated_at=CURRENT_TIMESTAMP
    RETURNING request_id INTO resolved_request_id;
    RETURN resolved_request_id;
END;
$$;

COMMIT;
