BEGIN;

-- Explicit retraction applies to any admitted identity witness, including an
-- external authority alignment.  The immutable witness row is retained.  The
-- current Level-3 substitution and composition frontiers are rebuilt in the
-- same transaction so no stale derived proposition survives the retraction.
CREATE OR REPLACE FUNCTION execution.retract_numeric_pnf_identity_witness(
    selected_witness_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    changed BOOLEAN := FALSE;
    resolved_run_id BIGINT;
    resolved_document_id BIGINT;
BEGIN
    SELECT region.run_id, region.document_id
      INTO resolved_run_id, resolved_document_id
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_object AS source_object
        ON source_object.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = source_object.region_id
     WHERE witness.witness_id = selected_witness_id;

    UPDATE execution.semantic_pnf_identity_witness_admission
       SET admission_state = 3,
           revision = revision + 1,
           updated_at = CURRENT_TIMESTAMP
     WHERE witness_id = selected_witness_id
       AND admission_state <> 3;
    changed := FOUND;

    IF changed
       AND resolved_run_id IS NOT NULL
       AND resolved_document_id IS NOT NULL THEN
        PERFORM execution.refresh_numeric_pnf_identity_substitution_derivations(
            resolved_run_id,
            resolved_document_id
        );
        PERFORM execution.refresh_numeric_pnf_factor_composition_candidates(
            resolved_run_id,
            resolved_document_id,
            16
        );
    END IF;

    RETURN changed;
END;
$$;

-- Re-declare external admission with unambiguous byte-level entity-ref
-- encoding.  Text values cannot contain NUL, so a zero byte safely separates
-- namespace and identifier before hashing without creating a label heuristic.
-- The resulting witness is immediately reflected into the current derived
-- semantic surface; callers do not need a later publication cycle to observe it.
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
    resolved_run_id BIGINT;
    resolved_document_id BIGINT;
    external_ref TEXT;
BEGIN
    IF NULLIF(btrim(selected_authority_namespace), '') IS NULL
       OR NULLIF(btrim(selected_authority_identifier), '') IS NULL THEN
        RAISE EXCEPTION 'external authority namespace and identifier are required';
    END IF;

    SELECT COALESCE(selected_canonical_symbol_id, object.head_symbol_id),
           region.run_id,
           region.document_id
      INTO resolved_symbol_id,
           resolved_run_id,
           resolved_document_id
      FROM execution.semantic_pnf_object AS object
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = object.region_id
     WHERE object.object_id = selected_source_object_id;
    IF resolved_symbol_id IS NULL THEN
        RAISE EXCEPTION 'source object % does not exist', selected_source_object_id;
    END IF;

    external_ref := 'external:' || encode(
        digest(
            convert_to(selected_authority_namespace, 'UTF8')
            || decode('00', 'hex')
            || convert_to(selected_authority_identifier, 'UTF8'),
            'sha256'
        ),
        'hex'
    );

    INSERT INTO execution.semantic_pnf_canonical_entity
        (entity_ref, authority_class, canonical_symbol_id,
         authority_namespace, authority_identifier)
    VALUES (
        external_ref,
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

    IF resolved_entity_id IS NULL THEN
        RAISE EXCEPTION
            'external authority identity %:% conflicts with an existing entity ref',
            selected_authority_namespace,
            selected_authority_identifier;
    END IF;

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

    IF resolved_witness_id IS NULL THEN
        RAISE EXCEPTION
            'external identity witness could not be materialised for object %',
            selected_source_object_id;
    END IF;

    INSERT INTO execution.semantic_pnf_identity_witness_admission
        (witness_id, admission_state, revision)
    VALUES (resolved_witness_id, 2, 1)
    ON CONFLICT (witness_id) DO UPDATE SET
        admission_state = 2,
        revision = execution.semantic_pnf_identity_witness_admission.revision + 1,
        updated_at = CURRENT_TIMESTAMP;

    PERFORM execution.refresh_numeric_pnf_identity_substitution_derivations(
        resolved_run_id,
        resolved_document_id
    );
    PERFORM execution.refresh_numeric_pnf_factor_composition_candidates(
        resolved_run_id,
        resolved_document_id,
        16
    );

    entity_id := resolved_entity_id;
    witness_id := resolved_witness_id;
    RETURN NEXT;
END;
$$;

COMMIT;
