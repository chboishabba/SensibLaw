BEGIN;

-- 110 fixes the late external-demand planner's zero-work path.
--
-- The prior function body used `need` as both the PL/pgSQL loop record and the
-- table alias in `SELECT need.*`, which caused the record to be referenced
-- before assignment. That made the planner error even when no external needs
-- were present. This version keeps the logic identical but uses distinct names
-- and returns 0 immediately when there is nothing to plan.
CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_external_demands_for_consumer(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT DEFAULT ''
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE external_need RECORD; candidate RECORD; attachment RECORD;
        request_id_value BIGINT; affected BIGINT := 0;
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_consumer_external_need AS need_row
          JOIN execution.semantic_pnf_consumer_horizon_work_queue AS work
            ON work.demand_id=need_row.demand_id
           AND work.consumer_ref=need_row.consumer_ref
           AND work.query_ref=need_row.query_ref
           AND work.policy_ref=need_row.policy_ref
           AND work.horizon=9
           AND work.work_state=1
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id=need_row.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE need_row.active
           AND need_row.consumer_ref=selected_consumer_ref
           AND need_row.query_ref=selected_query_ref
           AND need_row.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
           AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
               need_row.demand_id,need_row.consumer_ref,need_row.query_ref,
               need_row.policy_ref,6::smallint
           )
    ) THEN
        RETURN 0;
    END IF;

    -- Only the consumer-specific unresolved H9 residual may generate an
    -- external request. H3/H6 work and already-sufficient demands are invisible
    -- here.
    FOR external_need IN
        SELECT need_row.*,demand.lexical_symbol_id,demand.source_object_id
          FROM execution.semantic_pnf_consumer_external_need AS need_row
          JOIN execution.semantic_pnf_consumer_horizon_work_queue AS work
            ON work.demand_id=need_row.demand_id
           AND work.consumer_ref=need_row.consumer_ref
           AND work.query_ref=need_row.query_ref
           AND work.policy_ref=need_row.policy_ref
           AND work.horizon=9
           AND work.work_state=1
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id=need_row.demand_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id=demand.source_region_id
         WHERE need_row.active
           AND need_row.consumer_ref=selected_consumer_ref
           AND need_row.query_ref=selected_query_ref
           AND need_row.policy_ref=selected_policy_ref
           AND region.run_id=selected_run_id
           AND region.document_id=selected_document_id
           AND NOT execution.numeric_pnf_consumer_stop_at_horizon(
               need_row.demand_id,need_row.consumer_ref,need_row.query_ref,
               need_row.policy_ref,6::smallint
           )
         ORDER BY need_row.priority,need_row.demand_id
    LOOP
        IF external_need.lexical_symbol_id IS NULL
           AND external_need.need_kind IN (1,2) THEN
            CONTINUE;
        END IF;

        -- Candidate discovery is itself deduplicated by provider+label+revision.
        IF external_need.need_kind IN (1,2)
           AND NOT EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_label_world_candidate AS cached
                WHERE cached.label_symbol_id=external_need.lexical_symbol_id
           ) THEN
            request_id_value := execution.ensure_numeric_pnf_external_request(
                external_need.provider_id,1::smallint,external_need.lexical_symbol_id,NULL,
                NULL,NULL,external_need.need_revision,external_need.priority
            );
            INSERT INTO execution.semantic_pnf_external_request_member
                (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
            VALUES (request_id_value,external_need.demand_id,
                    external_need.consumer_ref,external_need.query_ref,
                    external_need.policy_ref,external_need.need_kind)
            ON CONFLICT DO NOTHING;
            affected:=affected+1;
            CONTINUE;
        END IF;

        IF external_need.need_kind=1 THEN
            -- Existing candidate fibre satisfies discovery without provider work.
            CONTINUE;
        ELSIF external_need.need_kind=2 THEN
            -- Enrich only the property/axis explicitly demanded by the consumer,
            -- and only for candidates already in the local fibre.
            FOR candidate IN
                SELECT candidate.world_entity_id
                  FROM execution.semantic_pnf_label_world_candidate AS candidate
                 WHERE candidate.label_symbol_id=external_need.lexical_symbol_id
                 ORDER BY candidate.candidate_ordinal,candidate.world_entity_id
            LOOP
                request_id_value := execution.ensure_numeric_pnf_external_request(
                    external_need.provider_id,2::smallint,external_need.lexical_symbol_id,
                    candidate.world_entity_id,
                    external_need.provider_property_numeric_id,
                    external_need.axis_kind,external_need.need_revision,
                    external_need.priority
                );
                INSERT INTO execution.semantic_pnf_external_request_member
                    (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
                VALUES (request_id_value,external_need.demand_id,
                        external_need.consumer_ref,external_need.query_ref,
                        external_need.policy_ref,external_need.need_kind)
                ON CONFLICT DO NOTHING;
                affected:=affected+1;
            END LOOP;
        ELSE
            -- Identity alignment is late even inside H9: only a world candidate
            -- already attached to a token supporting this demand's source object
            -- is eligible. Contextual preference still does not prove identity.
            FOR attachment IN
                SELECT DISTINCT attachment.world_entity_id,attachment.label_symbol_id
                  FROM execution.semantic_pnf_object_token_support AS support
                  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
                    ON attachment.token_id=support.token_id
                 WHERE support.object_id=external_need.source_object_id
                   AND attachment.attachment_state=1
            LOOP
                request_id_value := execution.ensure_numeric_pnf_external_request(
                    external_need.provider_id,3::smallint,attachment.label_symbol_id,
                    attachment.world_entity_id,NULL,NULL,external_need.need_revision,
                    external_need.priority
                );
                INSERT INTO execution.semantic_pnf_external_request_member
                    (request_id,demand_id,consumer_ref,query_ref,policy_ref,need_kind)
                VALUES (request_id_value,external_need.demand_id,
                        external_need.consumer_ref,external_need.query_ref,
                        external_need.policy_ref,external_need.need_kind)
                ON CONFLICT DO NOTHING;
                affected:=affected+1;
            END LOOP;
        END IF;
    END LOOP;

    PERFORM execution.refresh_numeric_pnf_external_request_cache_state();
    RETURN affected;
END;
$$;

COMMIT;
