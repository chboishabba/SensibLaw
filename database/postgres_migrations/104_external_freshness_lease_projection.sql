BEGIN;

-- 104: carry the strongest consumer freshness floor through the provider lease
-- so the snapshot/live transport can honor it rather than reusing a stale
-- snapshot after PostgreSQL correctly rejected the stale cache row.

DROP FUNCTION IF EXISTS execution.claim_numeric_pnf_external_provider_batch(
    SMALLINT,TEXT,INTEGER,INTEGER
);

CREATE OR REPLACE FUNCTION execution.claim_numeric_pnf_external_provider_batch(
    selected_provider_id SMALLINT,
    selected_worker_ref TEXT,
    selected_limit INTEGER DEFAULT 32,
    selected_lease_seconds INTEGER DEFAULT 300
) RETURNS TABLE(
    request_id BIGINT,
    request_kind SMALLINT,
    label_symbol_id BIGINT,
    world_entity_id BIGINT,
    provider_property_numeric_id BIGINT,
    axis_kind SMALLINT,
    request_revision BIGINT,
    minimum_source_epoch BIGINT
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
    SELECT leased.request_id,leased.request_kind,leased.label_symbol_id,
           leased.world_entity_id,leased.provider_property_numeric_id,
           leased.axis_kind,leased.request_revision,leased.minimum_source_epoch
      FROM leased
     ORDER BY leased.priority,leased.request_id;
END;
$$;

-- Candidate discovery has its own source provenance because a label->QID fibre
-- can be useful while still too old for a freshness-sensitive consumer.
CREATE OR REPLACE FUNCTION execution.set_numeric_pnf_label_candidate_source(
    selected_label_symbol_id BIGINT,
    selected_world_entity_id BIGINT,
    selected_source_epoch BIGINT,
    selected_source_ref TEXT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
BEGIN
    IF selected_source_epoch IS NOT NULL AND selected_source_epoch<=0 THEN
        RAISE EXCEPTION 'candidate source epoch must be positive';
    END IF;
    IF selected_source_ref IS NOT NULL AND btrim(selected_source_ref)='' THEN
        RAISE EXCEPTION 'candidate source ref cannot be blank';
    END IF;
    UPDATE execution.semantic_pnf_label_world_candidate
       SET source_epoch=selected_source_epoch,
           source_ref=selected_source_ref
     WHERE label_symbol_id=selected_label_symbol_id
       AND world_entity_id=selected_world_entity_id
       AND (
           source_epoch IS NULL
           OR selected_source_epoch IS NULL
           OR selected_source_epoch>=source_epoch
       );
    RETURN FOUND;
END;
$$;

COMMIT;
