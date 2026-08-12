BEGIN;

-- 106: freshness is the exact maximum required by active semantic members, not
-- a permanently monotone property of a physical request.  This both avoids
-- unnecessary live calls after consumers relax/withdraw requirements and fixes
-- property-needs that temporarily fan into candidate-discovery requests.

CREATE OR REPLACE FUNCTION execution.recompute_numeric_pnf_external_request_freshness(
    selected_request_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE old_floor BIGINT; new_floor BIGINT; old_state SMALLINT;
BEGIN
    SELECT request.minimum_source_epoch,request.request_state
      INTO STRICT old_floor,old_state
      FROM execution.semantic_pnf_external_request AS request
     WHERE request.request_id=selected_request_id;

    SELECT max(need.minimum_source_epoch)
      INTO new_floor
      FROM execution.semantic_pnf_external_request_member AS member
      JOIN execution.semantic_pnf_consumer_external_need AS need
        ON need.demand_id=member.demand_id
       AND need.consumer_ref=member.consumer_ref
       AND need.query_ref=member.query_ref
       AND need.policy_ref=member.policy_ref
       AND need.need_kind=member.need_kind
      JOIN execution.semantic_pnf_external_request AS request
        ON request.request_id=member.request_id
     WHERE member.request_id=selected_request_id
       AND need.active
       AND need.provider_id=request.provider_id
       AND (
           -- A property need may first require candidate discovery.  Its
           -- freshness floor therefore applies to the discovery request too.
           (request.request_kind=1 AND need.need_kind IN (1,2))
           OR
           (request.request_kind=2 AND need.need_kind=2
              AND need.axis_kind=request.axis_kind
              AND need.provider_property_numeric_id=request.provider_property_numeric_id)
           OR
           (request.request_kind=3 AND need.need_kind=3)
       );

    IF new_floor IS DISTINCT FROM old_floor THEN
        UPDATE execution.semantic_pnf_external_request
           SET minimum_source_epoch=new_floor,
               -- Do not steal an in-flight lease.  The completing worker must
               -- compare its leased floor against the current floor; if they
               -- differ, completion reopens the request for a new cache probe.
               request_state=CASE
                   WHEN old_state=4 THEN old_state
                   WHEN old_state IN (2,5,6) THEN 1
                   ELSE old_state
               END,
               updated_at=CURRENT_TIMESTAMP
         WHERE request_id=selected_request_id;
    END IF;
    RETURN new_floor;
END;
$$;

CREATE OR REPLACE FUNCTION execution.recompute_numeric_pnf_external_need_requests()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE member_row RECORD;
BEGIN
    FOR member_row IN
        SELECT DISTINCT member.request_id
          FROM execution.semantic_pnf_external_request_member AS member
         WHERE member.demand_id=NEW.demand_id
           AND member.consumer_ref=NEW.consumer_ref
           AND member.query_ref=NEW.query_ref
           AND member.policy_ref=NEW.policy_ref
           AND member.need_kind=NEW.need_kind
    LOOP
        PERFORM execution.recompute_numeric_pnf_external_request_freshness(
            member_row.request_id
        );
    END LOOP;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_external_need_freshness_recompute_trg
    ON execution.semantic_pnf_consumer_external_need;
CREATE TRIGGER semantic_pnf_external_need_freshness_recompute_trg
AFTER UPDATE OF minimum_source_epoch,active
ON execution.semantic_pnf_consumer_external_need
FOR EACH ROW EXECUTE FUNCTION execution.recompute_numeric_pnf_external_need_requests();

-- Replace the member trigger with exact recomputation.  This handles discovery
-- fan-in from property needs and allows future member changes to weaken a floor.
CREATE OR REPLACE FUNCTION execution.strengthen_numeric_pnf_external_request_freshness()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    PERFORM execution.recompute_numeric_pnf_external_request_freshness(
        NEW.request_id
    );
    RETURN NEW;
END;
$$;

-- Completion is conditional on the freshness contract actually leased.  If an
-- active consumer tightened the floor while work was in flight, the stale
-- worker releases the lease and reopens the request rather than claiming it met
-- a contract it never saw.  NULL-safe equality uses IS NOT DISTINCT FROM.
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

    UPDATE execution.semantic_pnf_external_request
       SET request_state=5,lease_owner=NULL,lease_expires_at=NULL,
           last_error_ref=NULL,updated_at=CURRENT_TIMESTAMP
     WHERE request_id=selected_request_id;
    PERFORM execution.wake_numeric_pnf_external_request_members(selected_request_id);
    RETURN TRUE;
END;
$$;

COMMIT;
