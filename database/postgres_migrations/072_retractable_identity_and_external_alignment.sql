BEGIN;

-- Current identity admission is retractable.  Immutable witness rows remain as
-- proof provenance; the admission relation expresses whether the witness may
-- participate in the current semantic projection.
CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_identity_witnesses(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected_count BIGINT := 0;
BEGIN
    PERFORM execution.refresh_numeric_pnf_demand_source_objects(
        selected_run_id,
        selected_document_id
    );

    -- Withdraw the previous document-derived projection before recomputing it.
    -- Witness evidence remains immutable; only current admission changes.
    UPDATE execution.semantic_pnf_identity_witness_admission AS admission
       SET admission_state = 4,
           revision = admission.revision + 1,
           updated_at = CURRENT_TIMESTAMP
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = source.region_id
     WHERE admission.witness_id = witness.witness_id
       AND admission.admission_state = 2
       AND witness.authority_class = 2
       AND source_region.run_id = selected_run_id
       AND source_region.document_id = selected_document_id;

    INSERT INTO execution.semantic_pnf_canonical_entity
        (entity_ref, authority_class, canonical_symbol_id, anchor_object_id)
    SELECT 'document-object:' || encode(target.object_digest, 'hex'),
           2,
           target.head_symbol_id,
           target.object_id
      FROM execution.semantic_pnf_frontier_resolution AS resolution
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = resolution.demand_id
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = demand.source_region_id
      JOIN execution.semantic_pnf_object AS target
        ON target.object_id = resolution.selected_target_id
     WHERE source_region.run_id = selected_run_id
       AND source_region.document_id = selected_document_id
       AND resolution.outcome_state = 2
       AND resolution.selected_target_kind = 1
       AND resolution.candidate_count = 1
    ON CONFLICT DO NOTHING;

    -- Resolution anchors prove only a document-local entity base.  They do not
    -- assert that the base is a world-unique person or organisation.
    INSERT INTO execution.semantic_pnf_identity_witness
        (source_object_id, target_entity_id, witness_kind, authority_class,
         source_interface_id, demand_id, resolution_interface_id,
         candidate_count)
    SELECT target.object_id,
           entity.entity_id,
           1,
           2,
           resolution.witness_interface_id,
           NULL,
           resolution.interface_id,
           1
      FROM execution.semantic_pnf_frontier_resolution AS resolution
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = resolution.demand_id
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = demand.source_region_id
      JOIN execution.semantic_pnf_object AS target
        ON target.object_id = resolution.selected_target_id
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = target.object_id
     WHERE source_region.run_id = selected_run_id
       AND source_region.document_id = selected_document_id
       AND resolution.outcome_state = 2
       AND resolution.selected_target_kind = 1
       AND resolution.candidate_count = 1
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_identity_witness
        (source_object_id, target_entity_id, witness_kind, authority_class,
         source_interface_id, demand_id, resolution_interface_id,
         candidate_count)
    SELECT demand.source_object_id,
           entity.entity_id,
           CASE
               WHEN residual.symbol_text = 'anaphor_unresolved' THEN 5
               ELSE 8
           END,
           2,
           demand.source_interface_id,
           demand.demand_id,
           resolution.interface_id,
           resolution.candidate_count
      FROM execution.semantic_pnf_frontier_resolution AS resolution
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = resolution.demand_id
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = demand.source_region_id
      JOIN execution.semantic_pnf_object AS target
        ON target.object_id = resolution.selected_target_id
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = target.object_id
      LEFT JOIN execution.semantic_symbol AS residual
        ON residual.symbol_id = demand.residual_type_symbol_id
     WHERE source_region.run_id = selected_run_id
       AND source_region.document_id = selected_document_id
       AND resolution.outcome_state = 2
       AND resolution.selected_target_kind = 1
       AND resolution.candidate_count = 1
       AND demand.source_object_id IS NOT NULL
       AND demand.source_object_id <> target.object_id
    ON CONFLICT DO NOTHING;

    -- Re-admit exactly the witnesses justified by the current unique frontier.
    -- Existing superseded rows are reactivated rather than duplicated.
    INSERT INTO execution.semantic_pnf_identity_witness_admission
        (witness_id, admission_state, revision)
    SELECT witness.witness_id, 2, 1
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = source.region_id
      LEFT JOIN execution.semantic_pnf_frontier_resolution AS resolution
        ON resolution.demand_id = witness.demand_id
       AND resolution.interface_id = witness.resolution_interface_id
     WHERE source_region.run_id = selected_run_id
       AND source_region.document_id = selected_document_id
       AND witness.authority_class = 2
       AND (
           (
               witness.demand_id IS NULL
               AND EXISTS (
                   SELECT 1
                     FROM execution.semantic_pnf_frontier_resolution AS anchor_resolution
                     JOIN execution.semantic_pnf_demand AS anchor_demand
                       ON anchor_demand.demand_id = anchor_resolution.demand_id
                    WHERE anchor_resolution.outcome_state = 2
                      AND anchor_resolution.selected_target_kind = 1
                      AND anchor_resolution.candidate_count = 1
                      AND anchor_resolution.selected_target_id = witness.source_object_id
               )
           )
           OR
           (
               witness.demand_id IS NOT NULL
               AND resolution.outcome_state = 2
               AND resolution.selected_target_kind = 1
               AND resolution.candidate_count = 1
               AND EXISTS (
                   SELECT 1
                     FROM execution.semantic_pnf_canonical_entity AS target_entity
                    WHERE target_entity.entity_id = witness.target_entity_id
                      AND target_entity.anchor_object_id = resolution.selected_target_id
               )
           )
       )
    ON CONFLICT (witness_id) DO UPDATE SET
        admission_state = 2,
        revision = execution.semantic_pnf_identity_witness_admission.revision + 1,
        updated_at = CURRENT_TIMESTAMP;

    INSERT INTO execution.semantic_pnf_identity_witness_constraint
        (witness_id, constraint_ordinal, key_kind, key_a, key_b,
         polarity, satisfied)
    SELECT witness.witness_id,
           constraint_row.ordinal,
           constraint_row.key_kind,
           constraint_row.key_a,
           constraint_row.key_b,
           constraint_row.polarity,
           TRUE
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_demand_constraint AS constraint_row
        ON constraint_row.demand_id = witness.demand_id
      JOIN execution.semantic_pnf_identity_witness_admission AS admission
        ON admission.witness_id = witness.witness_id
       AND admission.admission_state = 2
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = source.region_id
     WHERE source_region.run_id = selected_run_id
       AND source_region.document_id = selected_document_id
       AND witness.demand_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    SELECT count(*)
      INTO affected_count
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_identity_witness_admission AS admission
        ON admission.witness_id = witness.witness_id
       AND admission.admission_state = 2
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id = source.region_id
     WHERE source_region.run_id = selected_run_id
       AND source_region.document_id = selected_document_id;

    RETURN affected_count;
END;
$$;

-- Level-3 substitutions are a current materialized projection, not replacement
-- authority.  Rebuild them from accepted witnesses on each semantic refresh so
-- a retracted identity witness cannot leave a stale substituted proposition.
CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_identity_substitution_derivations(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected_count BIGINT := 0;
BEGIN
    DELETE FROM execution.semantic_pnf_factor_derivation AS derivation
    USING execution.semantic_pnf_interface AS interface,
          execution.semantic_pnf_region AS region
     WHERE derivation.rule_ref = 'identity-substitution:v1'
       AND derivation.scope_interface_id = interface.interface_id
       AND interface.region_id = region.region_id
       AND region.run_id = selected_run_id
       AND region.document_id = selected_document_id;

    INSERT INTO execution.semantic_pnf_factor_derivation
        (derivation_ref, rule_ref, derivation_kind, derivation_state,
         epistemic_level, authority_class, scope_interface_id,
         conclusion_factor_type_symbol_id, conclusion_predicate_symbol_id,
         modal_state, temporal_state)
    SELECT 'identity-substitution:' || factor.factor_id::TEXT || ':'
               || projection.authority_class::TEXT,
           'identity-substitution:v1',
           1,
           2,
           3,
           projection.authority_class,
           interface.interface_id,
           factor.factor_type_symbol_id,
           factor.predicate_symbol_id,
           factor.modal_state,
           factor.temporal_state
      FROM execution.semantic_pnf_factor AS factor
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = factor.region_id
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id = region.region_id
      JOIN execution.semantic_pnf_hyperedge AS edge
        ON edge.factor_id = factor.factor_id
      JOIN execution.semantic_pnf_identity_projection AS projection
        ON projection.source_object_id = edge.object_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
     GROUP BY factor.factor_id,
              projection.authority_class,
              interface.interface_id,
              factor.factor_type_symbol_id,
              factor.predicate_symbol_id,
              factor.modal_state,
              factor.temporal_state
    ON CONFLICT (derivation_ref) DO NOTHING;

    INSERT INTO execution.semantic_pnf_factor_derivation_premise
        (derivation_id, premise_ordinal, factor_id)
    SELECT derivation.derivation_id,
           0,
           split_part(derivation.derivation_ref, ':', 2)::BIGINT
      FROM execution.semantic_pnf_factor_derivation AS derivation
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = derivation.scope_interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE derivation.rule_ref = 'identity-substitution:v1'
       AND region.run_id = selected_run_id
       AND region.document_id = selected_document_id
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_factor_derivation_argument
        (derivation_id, slot_ordinal, role_symbol_id, source_object_id,
         local_object_id, identity_entity_id, identity_witness_ids)
    SELECT derivation.derivation_id,
           edge.slot_ordinal,
           edge.role_symbol_id,
           edge.object_id,
           CASE WHEN projection.target_entity_id IS NULL
                THEN edge.object_id ELSE NULL END,
           projection.target_entity_id,
           projection.witness_ids
      FROM execution.semantic_pnf_factor_derivation AS derivation
      JOIN execution.semantic_pnf_factor_derivation_premise AS premise
        ON premise.derivation_id = derivation.derivation_id
       AND premise.premise_ordinal = 0
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = premise.factor_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = factor.region_id
      JOIN execution.semantic_pnf_hyperedge AS edge
        ON edge.factor_id = factor.factor_id
      LEFT JOIN execution.semantic_pnf_identity_projection AS projection
        ON projection.source_object_id = edge.object_id
       AND projection.authority_class = derivation.authority_class
     WHERE derivation.rule_ref = 'identity-substitution:v1'
       AND region.run_id = selected_run_id
       AND region.document_id = selected_document_id
    ON CONFLICT (derivation_id, slot_ordinal) DO NOTHING;

    SELECT count(*)
      INTO affected_count
      FROM execution.semantic_pnf_factor_derivation AS derivation
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = derivation.scope_interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE derivation.rule_ref = 'identity-substitution:v1'
       AND region.run_id = selected_run_id
       AND region.document_id = selected_document_id;

    RETURN affected_count;
END;
$$;

-- Explicit world identity.  This function performs no discovery or fuzzy
-- matching: the caller supplies the authority namespace and identifier.  That
-- authority assertion is stored as a separate witness over the immutable local
-- object and is therefore auditable and retractable independently.
CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_external_identity_alignment(
    selected_source_object_id BIGINT,
    selected_authority_namespace TEXT,
    selected_authority_identifier TEXT,
    selected_canonical_symbol_id BIGINT DEFAULT NULL,
    selected_source_interface_id BIGINT DEFAULT NULL
)
RETURNS TABLE (entity_id BIGINT, witness_id BIGINT)
LANGUAGE plpgsql
AS $$
DECLARE
    resolved_symbol_id BIGINT;
    resolved_entity_id BIGINT;
    resolved_witness_id BIGINT;
BEGIN
    IF NULLIF(btrim(selected_authority_namespace), '') IS NULL
       OR NULLIF(btrim(selected_authority_identifier), '') IS NULL THEN
        RAISE EXCEPTION 'external authority namespace and identifier are required';
    END IF;

    SELECT COALESCE(selected_canonical_symbol_id, object.head_symbol_id)
      INTO resolved_symbol_id
      FROM execution.semantic_pnf_object AS object
     WHERE object.object_id = selected_source_object_id;
    IF resolved_symbol_id IS NULL THEN
        RAISE EXCEPTION 'source object % does not exist', selected_source_object_id;
    END IF;

    INSERT INTO execution.semantic_pnf_canonical_entity
        (entity_ref, authority_class, canonical_symbol_id,
         authority_namespace, authority_identifier)
    VALUES (
        'external:' || encode(
            digest(
                convert_to(
                    selected_authority_namespace || E'\\x00'
                    || selected_authority_identifier,
                    'UTF8'
                ),
                'sha256'
            ),
            'hex'
        ),
        4,
        resolved_symbol_id,
        selected_authority_namespace,
        selected_authority_identifier
    )
    ON CONFLICT DO NOTHING;

    SELECT entity.entity_id
      INTO resolved_entity_id
      FROM execution.semantic_pnf_canonical_entity AS entity
     WHERE entity.authority_class = 4
       AND entity.authority_namespace = selected_authority_namespace
       AND entity.authority_identifier = selected_authority_identifier;

    INSERT INTO execution.semantic_pnf_identity_witness
        (source_object_id, target_entity_id, witness_kind, authority_class,
         source_interface_id, candidate_count)
    VALUES (
        selected_source_object_id,
        resolved_entity_id,
        10,
        4,
        selected_source_interface_id,
        1
    )
    ON CONFLICT DO NOTHING;

    SELECT witness.witness_id
      INTO resolved_witness_id
      FROM execution.semantic_pnf_identity_witness AS witness
     WHERE witness.source_object_id = selected_source_object_id
       AND witness.target_entity_id = resolved_entity_id
       AND witness.witness_kind = 10
       AND witness.authority_class = 4
       AND witness.demand_id IS NULL
       AND witness.resolution_interface_id IS NULL
     ORDER BY witness.witness_id
     LIMIT 1;

    INSERT INTO execution.semantic_pnf_identity_witness_admission
        (witness_id, admission_state, revision)
    VALUES (resolved_witness_id, 2, 1)
    ON CONFLICT (witness_id) DO UPDATE SET
        admission_state = 2,
        revision = execution.semantic_pnf_identity_witness_admission.revision + 1,
        updated_at = CURRENT_TIMESTAMP;

    entity_id := resolved_entity_id;
    witness_id := resolved_witness_id;
    RETURN NEXT;
END;
$$;

COMMIT;
