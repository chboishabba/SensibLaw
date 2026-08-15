BEGIN;

-- 139: make sparse consumer reopening part of the ordinary evidence-write path.
--
-- The global incremental queue has been auto-woken by evidence insertion since
-- migration 091. Consumer/query fibres already had an exact reverse-dependency
-- relation (094), but callers still had to invoke its enqueue function manually.
-- That made delta-local recomputation an optional coordination convention.
--
-- New evidence now wakes only consumer fibres that explicitly registered a
-- dependency on one of this evidence atom's numeric source coordinates:
--   6 evidence id
--   4 source region
--   5 source interface
-- No document/corpus scan and no semantic inference occurs here.
-- Missing dependencies mean zero affected work, not negative evidence.

CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_consumers_on_evidence_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed_source(source_kind,source_id) AS (
        VALUES
            (6::SMALLINT,NEW.evidence_id),
            (4::SMALLINT,NEW.source_region_id),
            (5::SMALLINT,NEW.source_interface_id)
    ), affected AS MATERIALIZED (
        SELECT DISTINCT
               dependency.demand_id,
               dependency.consumer_ref,
               dependency.query_ref,
               dependency.policy_ref,
               dependency.minimum_horizon
          FROM changed_source
          JOIN execution.semantic_pnf_consumer_reverse_dependency AS dependency
            ON dependency.source_kind=changed_source.source_kind
           AND dependency.source_id=changed_source.source_id
         WHERE changed_source.source_id IS NOT NULL
    )
    INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
        (demand_id,consumer_ref,query_ref,policy_ref,horizon,work_state,completed_at)
    SELECT affected.demand_id,
           affected.consumer_ref,
           affected.query_ref,
           affected.policy_ref,
           affected.minimum_horizon,
           1::SMALLINT,
           NULL
      FROM affected
    ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)
    DO UPDATE SET
        work_state=1,
        completed_at=NULL;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_candidate_evidence_consumer_wakeup
    ON execution.semantic_pnf_candidate_evidence;
CREATE TRIGGER semantic_pnf_candidate_evidence_consumer_wakeup
AFTER INSERT ON execution.semantic_pnf_candidate_evidence
FOR EACH ROW
EXECUTE FUNCTION execution.wake_numeric_pnf_consumers_on_evidence_insert();

COMMIT;
