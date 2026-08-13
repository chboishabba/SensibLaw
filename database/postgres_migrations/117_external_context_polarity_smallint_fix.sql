BEGIN;

-- 117: keep the required-polarity coordinate typed as SMALLINT at the
-- completion/cache-wakeup call sites.  The underlying function has always
-- accepted SMALLINT; uncast integer literals fail only when a real provider
-- result reaches completion.

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

    IF NOT EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_external_request_active_member_v1 AS member
         WHERE member.request_id=selected_request_id
    ) THEN
        UPDATE execution.semantic_pnf_external_request
           SET request_state=8,lease_owner=NULL,lease_expires_at=NULL,
               last_error_ref='no-active-semantic-observer',
               updated_at=CURRENT_TIMESTAMP
         WHERE request_id=selected_request_id;
        RETURN FALSE;
    END IF;

    IF current_floor IS DISTINCT FROM leased_minimum_source_epoch THEN
        UPDATE execution.semantic_pnf_external_request
           SET request_state=1,lease_owner=NULL,lease_expires_at=NULL,
               last_error_ref='freshness-contract-changed-during-lease',
               updated_at=CURRENT_TIMESTAMP
         WHERE request_id=selected_request_id;
        RETURN FALSE;
    END IF;

    PERFORM execution.materialize_numeric_pnf_external_context_for_request(
        selected_request_id,1::smallint
    );

    UPDATE execution.semantic_pnf_external_request
       SET request_state=5,lease_owner=NULL,lease_expires_at=NULL,
           last_error_ref=NULL,updated_at=CURRENT_TIMESTAMP
     WHERE request_id=selected_request_id;
    PERFORM execution.wake_numeric_pnf_external_request_members(selected_request_id);
    RETURN TRUE;
END;
$$;

CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_external_cache_hits()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE request_row RECORD; affected BIGINT := 0; n BIGINT := 0;
BEGIN
    PERFORM execution.refresh_numeric_pnf_external_request_observer_state();
    PERFORM execution.refresh_numeric_pnf_external_request_cache_state();

    FOR request_row IN
        SELECT request.request_id
          FROM execution.semantic_pnf_external_request AS request
         WHERE request.request_state=2
           AND EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_external_request_active_member_v1 AS member
                WHERE member.request_id=request.request_id
           )
         ORDER BY request.request_id
    LOOP
        PERFORM execution.materialize_numeric_pnf_external_context_for_request(
            request_row.request_id,1::smallint
        );
        SELECT execution.wake_numeric_pnf_external_request_members(request_row.request_id)
          INTO n;
        affected:=affected+n;
    END LOOP;
    RETURN affected;
END;
$$;

COMMIT;
