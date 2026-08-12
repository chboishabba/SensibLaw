BEGIN;

-- 102: unsupported proof-producing identity alignment is a blocked state, not a
-- retryable provider failure.  This prevents repeated zero-network leasing while
-- preserving the external need/request as explicit unresolved provenance.

ALTER TABLE execution.semantic_pnf_external_request
    DROP CONSTRAINT IF EXISTS semantic_pnf_external_request_request_state_check;
ALTER TABLE execution.semantic_pnf_external_request
    ADD CONSTRAINT semantic_pnf_external_request_request_state_check
    CHECK (request_state IN (1,2,3,4,5,6,7));
-- 7 blocked: no proof-producing adapter is currently available.

CREATE OR REPLACE FUNCTION execution.block_numeric_pnf_external_request(
    selected_request_id BIGINT,
    selected_error_ref TEXT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
BEGIN
    UPDATE execution.semantic_pnf_external_request
       SET request_state=7,
           lease_owner=NULL,
           lease_expires_at=NULL,
           last_error_ref=selected_error_ref,
           updated_at=CURRENT_TIMESTAMP
     WHERE request_id=selected_request_id;
    RETURN FOUND;
END;
$$;

-- Cache refresh deliberately excludes state 7.  A blocked request is re-enabled
-- only by an explicit adapter/runtime revision, not by ordinary retry polling.

CREATE OR REPLACE VIEW execution.semantic_pnf_external_call_economy_v1 AS
WITH member AS (
    SELECT request_id,count(*)::BIGINT AS member_count
      FROM execution.semantic_pnf_external_request_member
     GROUP BY request_id
), request_summary AS (
    SELECT request.provider_id,
           count(*)::BIGINT AS unique_external_requests,
           count(*) FILTER (WHERE request.request_state=2)::BIGINT AS cache_satisfied_requests,
           count(*) FILTER (WHERE request.request_state=3)::BIGINT AS provider_ready_requests,
           count(*) FILTER (WHERE request.request_state=4)::BIGINT AS leased_requests,
           count(*) FILTER (WHERE request.request_state=5)::BIGINT AS acquired_requests,
           count(*) FILTER (WHERE request.request_state=7)::BIGINT AS blocked_requests,
           COALESCE(sum(member.member_count),0)::BIGINT AS semantic_request_members
      FROM execution.semantic_pnf_external_request AS request
      LEFT JOIN member USING(request_id)
     GROUP BY request.provider_id
), calls AS (
    SELECT receipt.provider_id,
           COALESCE(sum(receipt.provider_call_count),0)::BIGINT AS fresh_provider_calls,
           COALESCE(sum(receipt.leased_request_count),0)::BIGINT AS leased_request_attempts
      FROM execution.semantic_pnf_external_provider_batch_receipt AS receipt
     GROUP BY receipt.provider_id
)
SELECT summary.provider_id,
       summary.unique_external_requests,
       summary.cache_satisfied_requests,
       summary.provider_ready_requests,
       summary.leased_requests,
       summary.acquired_requests,
       summary.blocked_requests,
       summary.semantic_request_members,
       COALESCE(calls.fresh_provider_calls,0) AS fresh_provider_calls,
       CASE WHEN summary.unique_external_requests=0 THEN NULL
            ELSE summary.semantic_request_members::NUMERIC
                 / summary.unique_external_requests::NUMERIC
       END AS semantic_members_per_unique_request,
       CASE WHEN COALESCE(calls.fresh_provider_calls,0)=0 THEN NULL
            ELSE COALESCE(calls.leased_request_attempts,0)::NUMERIC
                 / calls.fresh_provider_calls::NUMERIC
       END AS requests_per_provider_call
  FROM request_summary AS summary
  LEFT JOIN calls USING(provider_id);

COMMIT;
