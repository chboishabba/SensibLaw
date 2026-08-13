BEGIN;

-- 115: a contract revision is immutable semantic control history. Re-registering
-- the same revision may only toggle active state; changing selectors, provider
-- coordinates, priority, or freshness requires a new revision.

CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_consumer_world_axis_contract(
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT,
    selected_contract_ref TEXT,
    selected_contract_revision BIGINT,
    selected_active BOOLEAN,
    selected_need_kind SMALLINT,
    selected_provider_id SMALLINT,
    selected_axis_kind SMALLINT,
    selected_provider_property_numeric_id BIGINT,
    selected_need_revision BIGINT,
    selected_priority SMALLINT,
    selected_minimum_source_epoch BIGINT,
    selected_expected_target_kind SMALLINT,
    selected_expected_factor_type_symbol_id BIGINT,
    selected_expected_object_kind_symbol_id BIGINT,
    selected_lexical_symbol_id BIGINT,
    selected_role_symbol_id BIGINT,
    selected_residual_type_symbol_id BIGINT
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE existing execution.semantic_pnf_consumer_world_axis_contract%ROWTYPE;
        resolved_contract_id BIGINT;
BEGIN
    IF selected_contract_ref='' THEN
        RAISE EXCEPTION 'contract_ref must be non-empty';
    END IF;
    IF selected_contract_revision<=0 OR selected_need_revision<=0 OR selected_priority<=0 THEN
        RAISE EXCEPTION 'contract/need revisions and priority must be positive';
    END IF;
    IF selected_minimum_source_epoch IS NOT NULL AND selected_minimum_source_epoch<=0 THEN
        RAISE EXCEPTION 'minimum source epoch must be positive';
    END IF;
    IF selected_expected_target_kind IS NULL
       AND selected_expected_factor_type_symbol_id IS NULL
       AND selected_expected_object_kind_symbol_id IS NULL
       AND selected_lexical_symbol_id IS NULL
       AND selected_role_symbol_id IS NULL
       AND selected_residual_type_symbol_id IS NULL THEN
        RAISE EXCEPTION 'consumer world-axis contract requires at least one numeric demand selector';
    END IF;
    IF selected_need_kind=2 AND (
        selected_axis_kind IS NULL OR selected_provider_property_numeric_id IS NULL
        OR selected_provider_property_numeric_id<=0
    ) THEN
        RAISE EXCEPTION 'property contract requires positive property id and axis';
    END IF;
    IF selected_need_kind IN (1,3) AND (
        selected_axis_kind IS NOT NULL OR selected_provider_property_numeric_id IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'discovery/identity contract cannot carry property-axis coordinates';
    END IF;

    SELECT contract.* INTO existing
      FROM execution.semantic_pnf_consumer_world_axis_contract AS contract
     WHERE contract.consumer_ref=selected_consumer_ref
       AND contract.query_ref=selected_query_ref
       AND contract.policy_ref=selected_policy_ref
       AND contract.contract_ref=selected_contract_ref
       AND contract.contract_revision=selected_contract_revision;

    IF FOUND THEN
        IF existing.need_kind IS DISTINCT FROM selected_need_kind
           OR existing.provider_id IS DISTINCT FROM selected_provider_id
           OR existing.axis_kind IS DISTINCT FROM selected_axis_kind
           OR existing.provider_property_numeric_id IS DISTINCT FROM selected_provider_property_numeric_id
           OR existing.need_revision IS DISTINCT FROM selected_need_revision
           OR existing.priority IS DISTINCT FROM selected_priority
           OR existing.minimum_source_epoch IS DISTINCT FROM selected_minimum_source_epoch
           OR existing.expected_target_kind IS DISTINCT FROM selected_expected_target_kind
           OR existing.expected_factor_type_symbol_id IS DISTINCT FROM selected_expected_factor_type_symbol_id
           OR existing.expected_object_kind_symbol_id IS DISTINCT FROM selected_expected_object_kind_symbol_id
           OR existing.lexical_symbol_id IS DISTINCT FROM selected_lexical_symbol_id
           OR existing.role_symbol_id IS DISTINCT FROM selected_role_symbol_id
           OR existing.residual_type_symbol_id IS DISTINCT FROM selected_residual_type_symbol_id THEN
            RAISE EXCEPTION 'world-axis contract revision is immutable; increment contract_revision';
        END IF;
        UPDATE execution.semantic_pnf_consumer_world_axis_contract
           SET active=selected_active
         WHERE contract_id=existing.contract_id;
        RETURN existing.contract_id;
    END IF;

    INSERT INTO execution.semantic_pnf_consumer_world_axis_contract
        (consumer_ref,query_ref,policy_ref,contract_ref,contract_revision,active,
         need_kind,provider_id,axis_kind,provider_property_numeric_id,need_revision,
         priority,minimum_source_epoch,expected_target_kind,
         expected_factor_type_symbol_id,expected_object_kind_symbol_id,
         lexical_symbol_id,role_symbol_id,residual_type_symbol_id)
    VALUES (selected_consumer_ref,selected_query_ref,selected_policy_ref,
            selected_contract_ref,selected_contract_revision,selected_active,
            selected_need_kind,selected_provider_id,selected_axis_kind,
            selected_provider_property_numeric_id,selected_need_revision,
            selected_priority,selected_minimum_source_epoch,selected_expected_target_kind,
            selected_expected_factor_type_symbol_id,selected_expected_object_kind_symbol_id,
            selected_lexical_symbol_id,selected_role_symbol_id,
            selected_residual_type_symbol_id)
    RETURNING contract_id INTO resolved_contract_id;
    RETURN resolved_contract_id;
END;
$$;

COMMIT;
