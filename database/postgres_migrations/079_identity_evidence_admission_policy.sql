BEGIN;

-- Evidence strength is explicit.  Proper-name expansion is generated as useful
-- candidate evidence but cannot bootstrap identity from surname uniqueness alone.
-- It may be admitted only when its target entity already has an independently
-- admitted structural/demand proof.  Apposition, title-role apposition and an
-- explicit alias cue remain locally proof-producing parser evidence.
CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_parser_identity_evidence(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    admitted_count BIGINT := 0;
BEGIN
    UPDATE execution.semantic_pnf_identity_witness_admission AS admission
       SET admission_state = 4,
           revision = admission.revision + 1,
           updated_at = CURRENT_TIMESTAMP
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = source.region_id
     WHERE admission.witness_id = witness.witness_id
       AND admission.admission_state = 2
       AND witness.authority_class = 2
       AND witness.witness_kind IN (1, 2, 3, 4, 6)
       AND witness.demand_id IS NULL
       AND region.run_id = selected_run_id
       AND region.document_id = selected_document_id;

    -- Strong parser evidence may establish a document-local entity base.
    INSERT INTO execution.semantic_pnf_canonical_entity
        (entity_ref, authority_class, canonical_symbol_id, anchor_object_id)
    SELECT DISTINCT
           'document-object:' || encode(target.object_digest, 'hex'),
           2,
           target.head_symbol_id,
           target.object_id
      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
      JOIN execution.semantic_pnf_object AS target
        ON target.object_id = candidate.target_object_id
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.candidate_count = 1
       AND candidate.witness_kind IN (2, 4, 6)
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_identity_witness
        (source_object_id, target_entity_id, witness_kind, authority_class,
         candidate_count)
    SELECT DISTINCT candidate.target_object_id,
           entity.entity_id,
           1,
           2,
           1
      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = candidate.target_object_id
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.candidate_count = 1
       AND candidate.witness_kind IN (2, 4, 6)
    ON CONFLICT DO NOTHING;

    -- Direct structural parser evidence.
    INSERT INTO execution.semantic_pnf_identity_witness
        (source_object_id, target_entity_id, witness_kind, authority_class,
         source_interface_id, candidate_count)
    SELECT candidate.source_object_id,
           entity.entity_id,
           candidate.witness_kind,
           2,
           interface.interface_id,
           1
      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = candidate.target_object_id
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = candidate.source_object_id
      LEFT JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id = source.region_id
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.candidate_count = 1
       AND candidate.witness_kind IN (2, 4, 6)
    ON CONFLICT DO NOTHING;

    -- First admit anchors + strong evidence.  The migration-074 integrity trigger
    -- still enforces candidate_count=1 and authority agreement at the write boundary.
    INSERT INTO execution.semantic_pnf_identity_witness_admission
        (witness_id, admission_state, revision)
    SELECT witness.witness_id, 2, 1
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.entity_id = witness.target_entity_id
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = source.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND witness.authority_class = 2
       AND entity.authority_class = 2
       AND witness.candidate_count = 1
       AND witness.witness_kind IN (1, 2, 4, 6)
       AND witness.demand_id IS NULL
       AND (
           witness.witness_kind = 1
           OR EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
                WHERE candidate.run_id = selected_run_id
                  AND candidate.document_id = selected_document_id
                  AND candidate.evidence_state = 1
                  AND candidate.candidate_count = 1
                  AND candidate.source_object_id = witness.source_object_id
                  AND candidate.target_object_id = entity.anchor_object_id
                  AND candidate.witness_kind = witness.witness_kind
           )
       )
    ON CONFLICT (witness_id) DO UPDATE SET
        admission_state = 2,
        revision = execution.semantic_pnf_identity_witness_admission.revision + 1,
        updated_at = CURRENT_TIMESTAMP;

    -- Corroborated proper-name expansion.  The target entity must already have an
    -- accepted non-anchor identity proof from apposition/title/alias or the typed
    -- demand path (anaphor/unique resolution).  Surname uniqueness alone is not proof.
    INSERT INTO execution.semantic_pnf_identity_witness
        (source_object_id, target_entity_id, witness_kind, authority_class,
         source_interface_id, candidate_count)
    SELECT candidate.source_object_id,
           entity.entity_id,
           3,
           2,
           interface.interface_id,
           1
      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = candidate.target_object_id
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = candidate.source_object_id
      LEFT JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id = source.region_id
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.witness_kind = 3
       AND candidate.candidate_count = 1
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_identity_witness AS corroborating
             JOIN execution.semantic_pnf_identity_witness_admission AS corroborating_admission
               ON corroborating_admission.witness_id = corroborating.witness_id
              AND corroborating_admission.admission_state = 2
            WHERE corroborating.target_entity_id = entity.entity_id
              AND corroborating.witness_kind IN (2, 4, 5, 6, 8)
       )
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_identity_witness_admission
        (witness_id, admission_state, revision)
    SELECT witness.witness_id, 2, 1
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = source.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND witness.authority_class = 2
       AND witness.witness_kind = 3
       AND witness.candidate_count = 1
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_identity_witness AS corroborating
             JOIN execution.semantic_pnf_identity_witness_admission AS corroborating_admission
               ON corroborating_admission.witness_id = corroborating.witness_id
              AND corroborating_admission.admission_state = 2
            WHERE corroborating.target_entity_id = witness.target_entity_id
              AND corroborating.witness_kind IN (2, 4, 5, 6, 8)
       )
    ON CONFLICT (witness_id) DO UPDATE SET
        admission_state = 2,
        revision = execution.semantic_pnf_identity_witness_admission.revision + 1,
        updated_at = CURRENT_TIMESTAMP;

    UPDATE execution.semantic_pnf_identity_evidence_candidate AS candidate
       SET evidence_state = CASE
           WHEN candidate.candidate_count > 1 THEN 3
           WHEN EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_identity_witness AS witness
                 JOIN execution.semantic_pnf_identity_witness_admission AS admission
                   ON admission.witness_id = witness.witness_id
                  AND admission.admission_state = 2
                 JOIN execution.semantic_pnf_canonical_entity AS entity
                   ON entity.entity_id = witness.target_entity_id
                WHERE witness.source_object_id = candidate.source_object_id
                  AND witness.witness_kind = candidate.witness_kind
                  AND entity.anchor_object_id = candidate.target_object_id
           ) THEN 2
           ELSE 1
       END
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state IN (1, 2, 3);

    SELECT count(*) INTO admitted_count
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_identity_witness_admission AS admission
        ON admission.witness_id = witness.witness_id
       AND admission.admission_state = 2
      JOIN execution.semantic_pnf_object AS source
        ON source.object_id = witness.source_object_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = source.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND witness.authority_class = 2
       AND witness.witness_kind IN (2, 3, 4, 6);
    RETURN admitted_count;
END;
$$;

COMMIT;
