BEGIN;

-- 094 corrects two important execution properties from the first 092 cut:
-- 1. contextual fit must never cross-product every witness with every cached
--    world requirement; it is scoped by the mention token's numeric label;
-- 2. consumer/query stopping must never mutate the global proof-required H3/H6/H9
--    queue, because another consumer may legitimately need a deeper horizon.

CREATE OR REPLACE VIEW execution.semantic_pnf_world_context_fit_v1 AS
WITH mention AS MATERIALIZED (
    SELECT witness.context_witness_id,
           witness.token_id,
           token.orth_symbol_id,
           token.lemma_symbol_id
      FROM execution.semantic_pnf_world_context_witness AS witness
      JOIN execution.semantic_parser_token AS token
        ON token.token_id=witness.token_id
       AND token.representation_version=2
), requirement AS MATERIALIZED (
    SELECT candidate.label_symbol_id,
           candidate.world_entity_id,
           requirement.axis_kind,
           requirement.required_symbol_id,
           requirement.required_polarity
      FROM execution.semantic_pnf_label_world_candidate AS candidate
      JOIN execution.semantic_pnf_world_candidate_requirement AS requirement
        ON requirement.world_entity_id=candidate.world_entity_id
), fit AS (
    SELECT mention.context_witness_id,
           mention.token_id,
           requirement.label_symbol_id,
           requirement.world_entity_id,
           count(*)::BIGINT AS requirement_count,
           count(*) FILTER (
               WHERE observed.symbol_id IS NOT NULL
                 AND observed.polarity=requirement.required_polarity
           )::BIGINT AS supporting_count,
           count(*) FILTER (
               WHERE observed.symbol_id IS NOT NULL
                 AND observed.polarity=-requirement.required_polarity
           )::BIGINT AS contradicting_count,
           count(*) FILTER (WHERE observed.symbol_id IS NULL)::BIGINT AS unknown_count
      FROM mention
      JOIN requirement
        ON requirement.label_symbol_id IN (
            mention.orth_symbol_id,
            mention.lemma_symbol_id
        )
      LEFT JOIN execution.semantic_pnf_world_context_axis_symbol AS observed
        ON observed.context_witness_id=mention.context_witness_id
       AND observed.axis_kind=requirement.axis_kind
       AND observed.symbol_id=requirement.required_symbol_id
       AND observed.polarity<>0
     GROUP BY mention.context_witness_id,mention.token_id,
              requirement.label_symbol_id,requirement.world_entity_id
)
SELECT fit.*,
       (fit.supporting_count-fit.contradicting_count) AS signed_margin,
       (fit.requirement_count>0
        AND fit.supporting_count=fit.requirement_count
        AND fit.contradicting_count=0
        AND fit.unknown_count=0) AS requirements_satisfied
  FROM fit;

-- Consumer execution is a projection over the durable semantic demand fibre.
-- It has an independent work queue so a query-specific early stop cannot erase
-- work required by the proof-required/global lane or by another consumer.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_consumer_horizon_work_queue (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    consumer_ref TEXT NOT NULL,
    query_ref TEXT NOT NULL,
    policy_ref TEXT NOT NULL DEFAULT '',
    horizon SMALLINT NOT NULL CHECK (horizon IN (3,6,9)),
    work_state SMALLINT NOT NULL DEFAULT 1 CHECK (work_state IN (1,2,3)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    PRIMARY KEY(demand_id,consumer_ref,query_ref,policy_ref,horizon)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_consumer_horizon_ready_idx
    ON execution.semantic_pnf_consumer_horizon_work_queue
       (consumer_ref,query_ref,policy_ref,horizon,demand_id)
    WHERE work_state=1;

CREATE OR REPLACE FUNCTION execution.seed_numeric_pnf_h3_work_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
        (demand_id,consumer_ref,query_ref,policy_ref,horizon)
    SELECT demand.demand_id,selected_consumer_ref,selected_query_ref,
           selected_policy_ref,3
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE region.run_id=selected_run_id
       AND region.document_id=selected_document_id
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

CREATE OR REPLACE FUNCTION execution.advance_numeric_pnf_horizon_work_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    completed_horizon SMALLINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE next_horizon SMALLINT; affected BIGINT := 0;
BEGIN
    IF completed_horizon NOT IN (3,6) THEN
        RAISE EXCEPTION 'completed_horizon must be 3 or 6';
    END IF;
    next_horizon := CASE completed_horizon WHEN 3 THEN 6 ELSE 9 END;

    UPDATE execution.semantic_pnf_consumer_horizon_work_queue AS work
       SET work_state=2, completed_at=CURRENT_TIMESTAMP
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE work.demand_id=demand.demand_id
       AND work.consumer_ref=selected_consumer_ref
       AND work.query_ref=selected_query_ref
       AND work.policy_ref=selected_policy_ref
       AND work.horizon=completed_horizon
       AND region.run_id=selected_run_id
       AND region.document_id=selected_document_id;

    INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
        (demand_id,consumer_ref,query_ref,policy_ref,horizon)
    SELECT demand.demand_id,selected_consumer_ref,selected_query_ref,
           selected_policy_ref,next_horizon
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id=demand.source_region_id
     WHERE region.run_id=selected_run_id
       AND region.document_id=selected_document_id
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_consumer_horizon_work_queue AS prior
            WHERE prior.demand_id=demand.demand_id
              AND prior.consumer_ref=selected_consumer_ref
              AND prior.query_ref=selected_query_ref
              AND prior.policy_ref=selected_policy_ref
              AND prior.horizon=completed_horizon
              AND prior.work_state=2
       )
       AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
           demand.demand_id,selected_consumer_ref,selected_query_ref,
           selected_policy_ref,completed_horizon
       )
       AND NOT EXISTS (
           SELECT 1 FROM execution.semantic_pnf_frontier_resolution AS proof
            WHERE proof.demand_id=demand.demand_id
              AND proof.outcome_state=2
              AND proof.candidate_count=1
       )
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

-- Consumer-indexed reverse dependencies compile future/query relevance to the
-- same sparse source ids used by the global incremental lane.  Waking one source
-- only enqueues the affected consumer fibres.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_consumer_reverse_dependency (
    source_kind SMALLINT NOT NULL CHECK (source_kind BETWEEN 1 AND 7),
    source_id BIGINT NOT NULL,
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    consumer_ref TEXT NOT NULL,
    query_ref TEXT NOT NULL,
    policy_ref TEXT NOT NULL DEFAULT '',
    minimum_horizon SMALLINT NOT NULL DEFAULT 3 CHECK (minimum_horizon IN (3,6,9)),
    dependency_kind SMALLINT NOT NULL DEFAULT 1,
    PRIMARY KEY(source_kind,source_id,demand_id,consumer_ref,query_ref,policy_ref,dependency_kind)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_consumer_reverse_dependency_source_idx
    ON execution.semantic_pnf_consumer_reverse_dependency
       (source_kind,source_id,consumer_ref,query_ref,policy_ref,demand_id);

CREATE OR REPLACE FUNCTION execution.enqueue_numeric_pnf_affected_consumer_demands(
    selected_source_kind SMALLINT,
    selected_source_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_consumer_horizon_work_queue
        (demand_id,consumer_ref,query_ref,policy_ref,horizon)
    SELECT dependency.demand_id,dependency.consumer_ref,dependency.query_ref,
           dependency.policy_ref,dependency.minimum_horizon
      FROM execution.semantic_pnf_consumer_reverse_dependency AS dependency
     WHERE dependency.source_kind=selected_source_kind
       AND dependency.source_id=selected_source_id
       AND dependency.consumer_ref=selected_consumer_ref
       AND dependency.query_ref=selected_query_ref
       AND dependency.policy_ref=selected_policy_ref
    ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)
    DO UPDATE SET work_state=1,completed_at=NULL;
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected;
END;
$$;

COMMIT;
