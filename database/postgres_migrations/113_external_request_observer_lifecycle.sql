BEGIN;

-- 113: a physical provider request is live only while at least one active
-- semantic need still observes it. Contract withdrawal/narrowing must not leave
-- stale provider-ready work behind, and reactivation must not lose cold cache or
-- request provenance.

ALTER TABLE execution.semantic_pnf_external_request
    DROP CONSTRAINT IF EXISTS semantic_pnf_external_request_request_state_check;
ALTER TABLE execution.semantic_pnf_external_request
    ADD CONSTRAINT semantic_pnf_external_request_request_state_check
    CHECK (request_state IN (1,2,3,4,5,6,7,8));
-- 8 dormant: no active semantic observer currently requires this request.

-- Resolve request members back to the exact currently-active semantic needs
-- they serve. Discovery requests may serve either a discovery need or the
-- discovery phase of a property-enrichment need. Property requests require the
-- exact P/axis pair. Identity requests require an active identity need.
CREATE OR REPLACE VIEW execution.semantic_pnf_external_request_active_member_v1 AS
SELECT DISTINCT member.request_id,member.demand_id,member.consumer_ref,
       member.query_ref,member.policy_ref,member.need_kind
  FROM execution.semantic_pnf_external_request_member AS member
  JOIN execution.semantic_pnf_external_request AS request
    ON request.request_id=member.request_id
  JOIN execution.semantic_pnf_consumer_external_need AS need
    ON need.demand_id=member.demand_id
   AND need.consumer_ref=member.consumer_ref
   AND need.query_ref=member.query_ref
   AND need.policy_ref=member.policy_ref
   AND need.need_kind=member.need_kind
   AND need.provider_id=request.provider_id
   AND need.active
   AND (
       (request.request_kind=1 AND need.need_kind IN (1,2))
       OR
       (request.request_kind=2 AND need.need_kind=2
        AND need.axis_kind=request.axis_kind
        AND need.provider_property_numeric_id=request.provider_property_numeric_id)
       OR
       (request.request_kind=3 AND need.need_kind=3)
   );

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_external_request_observer_state()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0; n BIGINT := 0;
BEGIN
    -- Acquired evidence remains acquired cold history. Every other request with
    -- no active observer becomes dormant, including a lease whose consumer was
    -- withdrawn while the provider call was in flight.
    UPDATE execution.semantic_pnf_external_request AS request
       SET request_state=8,
           lease_owner=NULL,
           lease_expires_at=NULL,
           last_error_ref='no-active-semantic-observer',
           updated_at=CURRENT_TIMESTAMP
     WHERE request.request_state<>5
       AND request.request_state<>8
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_external_request_active_member_v1 AS member
            WHERE member.request_id=request.request_id
       );
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;

    -- A newly reactivated need reopens only the physical request projection.
    -- The ordinary cache probe then decides whether any provider I/O remains.
    UPDATE execution.semantic_pnf_external_request AS request
       SET request_state=1,
           lease_owner=NULL,
           lease_expires_at=NULL,
           last_error_ref=NULL,
           updated_at=CURRENT_TIMESTAMP
     WHERE request.request_state=8
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_external_request_active_member_v1 AS member
            WHERE member.request_id=request.request_id
       );
    GET DIAGNOSTICS n=ROW_COUNT; affected:=affected+n;
    RETURN affected;
END;
$$;

-- Wake only fibres whose semantic need is still active. Historical request
-- membership is retained for provenance but is not execution authority.
CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_external_request_members(
    selected_request_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
        (demand_id,consumer_ref,query_ref,policy_ref,horizon,work_state)
    SELECT member.demand_id,member.consumer_ref,member.query_ref,
           member.policy_ref,9,1
      FROM execution.semantic_pnf_external_request_active_member_v1 AS member
     WHERE member.request_id=selected_request_id
    ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)
    DO UPDATE SET work_state=1,completed_at=NULL;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- Lease-aware completion now also checks observer liveness. Evidence recorded
-- before this gate remains valid cold provenance, but no hot projection/wakeup
-- is permitted once all consumers have withdrawn.
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

-- Cache hits are likewise consumer-observer indexed. A cached physical result
-- cannot reopen a fibre whose need has since been withdrawn.
CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_external_cache_hits()
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE request_row RECORD; affected BIGINT := 0; n BIGINT := 0;
BEGIN
    PERFORM execution.refresh_numeric_pnf_external_request_observer_state();
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
        PERFORM execution.wake_numeric_pnf_external_request_members(request_row.request_id);
        GET DIAGNOSTICS n=ROW_COUNT;
        affected:=affected+n;
    END LOOP;
    RETURN affected;
END;
$$;

-- Extend the call-economy observatory without changing the meaning of existing
-- counters. Dormant requests are visible separately from provider-ready work.
DROP VIEW IF EXISTS execution.semantic_pnf_external_call_economy_v2;
CREATE OR REPLACE VIEW execution.semantic_pnf_external_call_economy_v2 AS
SELECT economy.*,
       COALESCE(dormant.dormant_requests,0)::BIGINT AS dormant_requests
  FROM execution.semantic_pnf_external_call_economy_v1 AS economy
  LEFT JOIN (
      SELECT provider_id,count(*)::BIGINT AS dormant_requests
        FROM execution.semantic_pnf_external_request
       WHERE request_state=8
       GROUP BY provider_id
  ) AS dormant USING(provider_id);

COMMIT;
