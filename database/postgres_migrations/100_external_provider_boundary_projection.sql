BEGIN;

-- 100: provider workers must never depend on database-local surrogate ids.
-- Candidate discovery crosses the explicit text boundary as a label string;
-- entity requests cross as provider-local numeric ids (e.g. Wikidata Q number).

DROP FUNCTION IF EXISTS execution.claim_numeric_pnf_external_provider_batch(
    SMALLINT,TEXT,INTEGER,INTEGER
);

CREATE FUNCTION execution.claim_numeric_pnf_external_provider_batch(
    selected_provider_id SMALLINT,
    selected_worker_ref TEXT,
    selected_limit INTEGER DEFAULT 32,
    selected_lease_seconds INTEGER DEFAULT 300
) RETURNS TABLE(
    request_id BIGINT,
    request_kind SMALLINT,
    label_text TEXT,
    provider_subject_numeric_id BIGINT,
    provider_property_numeric_id BIGINT,
    axis_kind SMALLINT,
    request_revision BIGINT
) LANGUAGE plpgsql AS $$
BEGIN
    IF selected_limit < 1 OR selected_limit > 256 THEN
        RAISE EXCEPTION 'selected_limit must be in 1..256';
    END IF;
    IF selected_lease_seconds < 1 THEN
        RAISE EXCEPTION 'selected_lease_seconds must be positive';
    END IF;

    PERFORM execution.refresh_numeric_pnf_external_request_cache_state();

    RETURN QUERY
    WITH picked AS (
        SELECT request.request_id
          FROM execution.semantic_pnf_external_request AS request
         WHERE request.provider_id=selected_provider_id
           AND (
               request.request_state=3
               OR (request.request_state=4 AND request.lease_expires_at<CURRENT_TIMESTAMP)
           )
         ORDER BY request.priority,request.request_id
         FOR UPDATE SKIP LOCKED
         LIMIT selected_limit
    ), leased AS (
        UPDATE execution.semantic_pnf_external_request AS request
           SET request_state=4,
               lease_owner=selected_worker_ref,
               lease_expires_at=CURRENT_TIMESTAMP
                   + make_interval(secs => selected_lease_seconds),
               attempt_count=request.attempt_count+1,
               updated_at=CURRENT_TIMESTAMP
          FROM picked
         WHERE request.request_id=picked.request_id
        RETURNING request.*
    )
    SELECT leased.request_id,
           leased.request_kind,
           label.symbol_text,
           subject.provider_numeric_id,
           leased.provider_property_numeric_id,
           leased.axis_kind,
           leased.request_revision
      FROM leased
      LEFT JOIN execution.semantic_symbol AS label
        ON label.symbol_id=leased.label_symbol_id
      LEFT JOIN execution.semantic_pnf_world_entity_numeric AS subject
        ON subject.world_entity_id=leased.world_entity_id
       AND subject.provider_id=leased.provider_id
     ORDER BY leased.priority,leased.request_id;
END;
$$;

COMMIT;
