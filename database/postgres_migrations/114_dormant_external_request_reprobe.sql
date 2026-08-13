BEGIN;

-- 114: observer reactivation is one-pass. A dormant request reopened by an
-- active semantic need is immediately re-probed against the durable cache before
-- cache-hit wakeup/provider leasing decisions.

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
            request_row.request_id,1
        );
        SELECT execution.wake_numeric_pnf_external_request_members(request_row.request_id)
          INTO n;
        affected:=affected+n;
    END LOOP;
    RETURN affected;
END;
$$;

COMMIT;
