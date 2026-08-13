BEGIN;

-- 120: harden the structural admission cut from 119.
-- 1. Avoid an unassigned PL/pgSQL RECORD when explicit registration has no
--    structural anchor.
-- 2. Identity alignment requires an occurrence-attached world candidate, not
--    merely a same-label candidate elsewhere in the corpus cache.

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_attached_world_candidate_v1 AS
SELECT DISTINCT demand.demand_id,demand.source_object_id,
       attachment.label_symbol_id,attachment.world_entity_id
  FROM execution.semantic_pnf_demand AS demand
  JOIN execution.semantic_pnf_object_token_support AS support
    ON support.object_id=demand.source_object_id
  JOIN execution.semantic_pnf_mention_world_attachment AS attachment
    ON attachment.token_id=support.token_id
   AND attachment.attachment_state=1
 WHERE demand.source_object_id IS NOT NULL;

-- Keep the 119 column order and append the stronger identity diagnostic.
DROP VIEW IF EXISTS execution.semantic_pnf_h9_external_admission_summary_v1;
DROP VIEW IF EXISTS execution.semantic_pnf_h9_external_admission_v1;
CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_v1 AS
WITH h9 AS MATERIALIZED (
    SELECT work.demand_id,work.consumer_ref,work.query_ref,work.policy_ref,
           demand.source_object_id,demand.expected_target_kind,
           demand.expected_factor_type_symbol_id,demand.expected_object_kind_symbol_id,
           demand.lexical_symbol_id,demand.role_symbol_id,demand.residual_type_symbol_id
      FROM execution.semantic_pnf_consumer_horizon_work_queue AS work
      JOIN execution.semantic_pnf_demand AS demand ON demand.demand_id=work.demand_id
     WHERE work.horizon=9 AND work.work_state=1
), matched AS MATERIALIZED (
    SELECT h9.*,contract.contract_id,contract.need_kind,contract.provider_id,
           contract.axis_kind,contract.provider_property_numeric_id,
           contract.need_revision,contract.priority,contract.minimum_source_epoch,
           anchor.source_object_id AS anchor_object_id,anchor.label_symbol_id,
           anchor.anchor_kind,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_h9_entity_bearing_v1 AS b
                    WHERE b.demand_id=h9.demand_id) AS entity_bearing,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS c
                    WHERE c.label_symbol_id=anchor.label_symbol_id) AS has_world_candidate,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_h9_attached_world_candidate_v1 AS a
                    WHERE a.demand_id=h9.demand_id
                      AND a.label_symbol_id=anchor.label_symbol_id) AS has_attached_world_candidate,
           execution.numeric_pnf_consumer_stop_at_horizon(
               h9.demand_id,h9.consumer_ref,h9.query_ref,h9.policy_ref,6::SMALLINT
           ) AS consumer_sufficient,
           EXISTS (SELECT 1 FROM execution.semantic_pnf_frontier_resolution AS p
                    WHERE p.demand_id=h9.demand_id AND p.outcome_state=2
                      AND p.candidate_count=1) AS deductively_resolved
      FROM h9
      LEFT JOIN execution.semantic_pnf_consumer_world_axis_contract_current_v1 AS contract
        ON contract.consumer_ref=h9.consumer_ref
       AND contract.query_ref=h9.query_ref
       AND contract.policy_ref=h9.policy_ref AND contract.active
       AND (contract.expected_target_kind IS NULL OR contract.expected_target_kind=h9.expected_target_kind)
       AND (contract.expected_factor_type_symbol_id IS NULL OR contract.expected_factor_type_symbol_id=h9.expected_factor_type_symbol_id)
       AND (contract.expected_object_kind_symbol_id IS NULL OR contract.expected_object_kind_symbol_id=h9.expected_object_kind_symbol_id)
       AND (contract.lexical_symbol_id IS NULL OR contract.lexical_symbol_id=h9.lexical_symbol_id)
       AND (contract.role_symbol_id IS NULL OR contract.role_symbol_id=h9.role_symbol_id)
       AND (contract.residual_type_symbol_id IS NULL OR contract.residual_type_symbol_id=h9.residual_type_symbol_id)
      LEFT JOIN execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS anchor
        ON anchor.demand_id=h9.demand_id
)
SELECT matched.*,
       CASE
         WHEN contract_id IS NULL OR consumer_sufficient OR deductively_resolved THEN FALSE
         WHEN source_object_id IS NULL OR NOT entity_bearing OR label_symbol_id IS NULL THEN FALSE
         WHEN need_kind=2 AND NOT has_world_candidate THEN FALSE
         WHEN need_kind=3 AND NOT has_attached_world_candidate THEN FALSE
         ELSE TRUE
       END AS admitted,
       CASE
         WHEN contract_id IS NULL THEN 10
         WHEN consumer_sufficient THEN 15
         WHEN deductively_resolved THEN 16
         WHEN source_object_id IS NULL THEN 11
         WHEN NOT entity_bearing THEN 12
         WHEN label_symbol_id IS NULL THEN 13
         WHEN need_kind=2 AND NOT has_world_candidate THEN 14
         WHEN need_kind=3 AND NOT has_attached_world_candidate THEN 14
         WHEN need_kind=1 THEN 1 WHEN need_kind=2 THEN 2 WHEN need_kind=3 THEN 3
       END::SMALLINT AS admission_reason
  FROM matched;

CREATE OR REPLACE VIEW execution.semantic_pnf_h9_external_admission_summary_v1 AS
SELECT consumer_ref,query_ref,policy_ref,admission_reason,admitted,
       count(*)::BIGINT AS admission_rows,
       count(DISTINCT demand_id)::BIGINT AS demand_count
  FROM execution.semantic_pnf_h9_external_admission_v1
 GROUP BY consumer_ref,query_ref,policy_ref,admission_reason,admitted;

CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_consumer_external_need(
    selected_demand_id BIGINT,selected_consumer_ref TEXT,selected_query_ref TEXT,
    selected_policy_ref TEXT,selected_need_kind SMALLINT,selected_provider_id SMALLINT,
    selected_axis_kind SMALLINT,selected_provider_property_numeric_id BIGINT,
    selected_priority SMALLINT,selected_need_revision BIGINT,selected_active BOOLEAN
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE resolved_need_id BIGINT;
        selected_anchor_object_id BIGINT;
        selected_label_symbol_id BIGINT;
BEGIN
    IF selected_need_kind NOT IN (1,2,3) THEN RAISE EXCEPTION 'external need kind must be discovery, property, or identity'; END IF;
    IF selected_priority<=0 THEN RAISE EXCEPTION 'external need priority must be positive'; END IF;
    IF selected_need_kind=2 AND (selected_axis_kind IS NULL OR selected_provider_property_numeric_id IS NULL OR selected_provider_property_numeric_id<=0) THEN
        RAISE EXCEPTION 'property need requires positive property id and axis';
    END IF;
    IF selected_need_kind<>2 AND (selected_axis_kind IS NOT NULL OR selected_provider_property_numeric_id IS NOT NULL) THEN
        RAISE EXCEPTION 'discovery/identity need cannot carry property-axis coordinates';
    END IF;

    SELECT anchor.source_object_id,anchor.label_symbol_id
      INTO selected_anchor_object_id,selected_label_symbol_id
      FROM execution.semantic_pnf_h9_preferred_entity_anchor_v1 AS anchor
     WHERE anchor.demand_id=selected_demand_id;

    IF selected_active AND (selected_anchor_object_id IS NULL OR selected_label_symbol_id IS NULL) THEN
        RAISE EXCEPTION 'external need requires entity-bearing structural label anchor';
    END IF;
    IF selected_active AND selected_need_kind=2 AND NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
         WHERE candidate.label_symbol_id=selected_label_symbol_id
    ) THEN
        RAISE EXCEPTION 'property need requires represented world candidate';
    END IF;
    IF selected_active AND selected_need_kind=3 AND NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_h9_attached_world_candidate_v1 AS attached
         WHERE attached.demand_id=selected_demand_id
           AND attached.label_symbol_id=selected_label_symbol_id
    ) THEN
        RAISE EXCEPTION 'identity need requires occurrence-attached world candidate';
    END IF;

    INSERT INTO execution.semantic_pnf_consumer_external_need
        (demand_id,consumer_ref,query_ref,policy_ref,need_kind,provider_id,
         axis_kind,provider_property_numeric_id,priority,need_revision,active,
         anchor_object_id,label_symbol_id)
    VALUES (selected_demand_id,selected_consumer_ref,selected_query_ref,selected_policy_ref,
            selected_need_kind,selected_provider_id,selected_axis_kind,
            selected_provider_property_numeric_id,selected_priority,selected_need_revision,
            selected_active,selected_anchor_object_id,selected_label_symbol_id)
    ON CONFLICT DO NOTHING;

    SELECT need.need_id INTO STRICT resolved_need_id
      FROM execution.semantic_pnf_consumer_external_need AS need
     WHERE need.demand_id=selected_demand_id AND need.consumer_ref=selected_consumer_ref
       AND need.query_ref=selected_query_ref AND need.policy_ref=selected_policy_ref
       AND need.need_kind=selected_need_kind AND need.provider_id=selected_provider_id
       AND COALESCE(need.axis_kind,0)=COALESCE(selected_axis_kind,0)
       AND COALESCE(need.provider_property_numeric_id,0)=COALESCE(selected_provider_property_numeric_id,0)
       AND need.need_revision=selected_need_revision;

    UPDATE execution.semantic_pnf_consumer_external_need
       SET anchor_object_id=selected_anchor_object_id,label_symbol_id=selected_label_symbol_id
     WHERE need_id=resolved_need_id;

    INSERT INTO execution.semantic_pnf_consumer_external_need_origin
        (need_id,origin_kind,contract_id,active,priority,minimum_source_epoch)
    VALUES (resolved_need_id,1,NULL,selected_active,selected_priority,NULL)
    ON CONFLICT(need_id) WHERE origin_kind=1 DO UPDATE SET
        active=EXCLUDED.active,priority=EXCLUDED.priority,updated_at=CURRENT_TIMESTAMP;
    PERFORM execution.recompute_numeric_pnf_external_need_from_origins(resolved_need_id);
    RETURN resolved_need_id;
END;
$$;

COMMIT;
