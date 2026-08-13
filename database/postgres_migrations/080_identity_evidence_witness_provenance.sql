BEGIN;

-- Parser evidence and demand evidence may use the same witness kinds (notably
-- resolution_anchor).  Current admission therefore cannot be safely refreshed by
-- witness kind alone.  Link every parser-produced witness to the exact candidate
-- that justified it and only retract/re-admit through this relation.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_identity_evidence_witness (
    candidate_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_identity_evidence_candidate(candidate_id)
        ON DELETE CASCADE,
    witness_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_identity_witness(witness_id)
        ON DELETE RESTRICT,
    witness_role SMALLINT NOT NULL CHECK (witness_role IN (1, 2)),
    PRIMARY KEY (candidate_id, witness_id, witness_role)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_identity_evidence_witness_current_idx
    ON execution.semantic_pnf_identity_evidence_witness(witness_id, candidate_id);

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
    -- Retract only witnesses whose current authority came from parser evidence in
    -- this document.  Typed-demand anchors/anaphor witnesses are untouched.
    UPDATE execution.semantic_pnf_identity_witness_admission AS admission
       SET admission_state = 4,
           revision = admission.revision + 1,
           updated_at = CURRENT_TIMESTAMP
      FROM execution.semantic_pnf_identity_evidence_witness AS provenance
      JOIN execution.semantic_pnf_identity_evidence_candidate AS candidate
        ON candidate.candidate_id = provenance.candidate_id
     WHERE admission.witness_id = provenance.witness_id
       AND admission.admission_state = 2
       AND candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id;

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

    -- Strong evidence: create/reuse anchor and source witnesses.
    INSERT INTO execution.semantic_pnf_identity_witness
        (source_object_id, target_entity_id, witness_kind, authority_class,
         candidate_count)
    SELECT DISTINCT candidate.target_object_id,
           entity.entity_id, 1, 2, 1
      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = candidate.target_object_id
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.candidate_count = 1
       AND candidate.witness_kind IN (2, 4, 6)
    ON CONFLICT DO NOTHING;

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

    INSERT INTO execution.semantic_pnf_identity_evidence_witness
        (candidate_id, witness_id, witness_role)
    SELECT candidate.candidate_id,
           anchor.witness_id,
           1
      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = candidate.target_object_id
      JOIN execution.semantic_pnf_identity_witness AS anchor
        ON anchor.source_object_id = candidate.target_object_id
       AND anchor.target_entity_id = entity.entity_id
       AND anchor.witness_kind = 1
       AND anchor.authority_class = 2
       AND anchor.candidate_count = 1
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.candidate_count = 1
       AND candidate.witness_kind IN (2, 4, 6)
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_identity_evidence_witness
        (candidate_id, witness_id, witness_role)
    SELECT candidate.candidate_id,
           witness.witness_id,
           2
      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = candidate.target_object_id
      JOIN execution.semantic_pnf_identity_witness AS witness
        ON witness.source_object_id = candidate.source_object_id
       AND witness.target_entity_id = entity.entity_id
       AND witness.witness_kind = candidate.witness_kind
       AND witness.authority_class = 2
       AND witness.candidate_count = 1
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.candidate_count = 1
       AND candidate.witness_kind IN (2, 4, 6)
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_identity_witness_admission
        (witness_id, admission_state, revision)
    SELECT DISTINCT provenance.witness_id, 2, 1
      FROM execution.semantic_pnf_identity_evidence_witness AS provenance
      JOIN execution.semantic_pnf_identity_evidence_candidate AS candidate
        ON candidate.candidate_id = provenance.candidate_id
      JOIN execution.semantic_pnf_identity_witness AS witness
        ON witness.witness_id = provenance.witness_id
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.entity_id = witness.target_entity_id
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.candidate_count = 1
       AND candidate.witness_kind IN (2, 4, 6)
       AND witness.candidate_count = 1
       AND witness.authority_class = entity.authority_class
    ON CONFLICT (witness_id) DO UPDATE SET
        admission_state = 2,
        revision = execution.semantic_pnf_identity_witness_admission.revision + 1,
        updated_at = CURRENT_TIMESTAMP;

    -- Corroborated name expansion.  Its target must already carry an accepted
    -- non-anchor proof independent of this name-expansion candidate.
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

    INSERT INTO execution.semantic_pnf_identity_evidence_witness
        (candidate_id, witness_id, witness_role)
    SELECT candidate.candidate_id,
           witness.witness_id,
           2
      FROM execution.semantic_pnf_identity_evidence_candidate AS candidate
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.anchor_object_id = candidate.target_object_id
      JOIN execution.semantic_pnf_identity_witness AS witness
        ON witness.source_object_id = candidate.source_object_id
       AND witness.target_entity_id = entity.entity_id
       AND witness.witness_kind = 3
       AND witness.authority_class = 2
       AND witness.candidate_count = 1
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
    SELECT provenance.witness_id, 2, 1
      FROM execution.semantic_pnf_identity_evidence_witness AS provenance
      JOIN execution.semantic_pnf_identity_evidence_candidate AS candidate
        ON candidate.candidate_id = provenance.candidate_id
      JOIN execution.semantic_pnf_identity_witness AS witness
        ON witness.witness_id = provenance.witness_id
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state = 1
       AND candidate.witness_kind = 3
       AND candidate.candidate_count = 1
       AND provenance.witness_role = 2
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
                 FROM execution.semantic_pnf_identity_evidence_witness AS provenance
                 JOIN execution.semantic_pnf_identity_witness_admission AS admission
                   ON admission.witness_id = provenance.witness_id
                  AND admission.admission_state = 2
                WHERE provenance.candidate_id = candidate.candidate_id
                  AND provenance.witness_role = 2
           ) THEN 2
           ELSE 1
       END
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND candidate.evidence_state IN (1, 2, 3);

    SELECT count(DISTINCT provenance.witness_id)
      INTO admitted_count
      FROM execution.semantic_pnf_identity_evidence_witness AS provenance
      JOIN execution.semantic_pnf_identity_evidence_candidate AS candidate
        ON candidate.candidate_id = provenance.candidate_id
      JOIN execution.semantic_pnf_identity_witness_admission AS admission
        ON admission.witness_id = provenance.witness_id
       AND admission.admission_state = 2
     WHERE candidate.run_id = selected_run_id
       AND candidate.document_id = selected_document_id
       AND provenance.witness_role = 2;
    RETURN admitted_count;
END;
$$;

COMMIT;
