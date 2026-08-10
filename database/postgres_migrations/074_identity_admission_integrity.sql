BEGIN;

-- An accepted identity witness is a proof object, not merely candidate evidence.
-- Acceptance therefore requires unique multiplicity and authority agreement with
-- the canonical entity base. Historical witness evidence may retain other
-- candidate counts for audit, but it may not remain currently accepted.

-- Clean upgraded databases before installing the admission trigger. Invalid
-- historical admissions are superseded rather than deleted so their provenance
-- remains inspectable.
UPDATE execution.semantic_pnf_identity_witness_admission AS admission
   SET admission_state = 4,
       revision = admission.revision + 1,
       updated_at = CURRENT_TIMESTAMP
  FROM execution.semantic_pnf_identity_witness AS witness
  JOIN execution.semantic_pnf_canonical_entity AS entity
    ON entity.entity_id = witness.target_entity_id
 WHERE admission.witness_id = witness.witness_id
   AND admission.admission_state = 2
   AND (
       witness.candidate_count <> 1
       OR witness.authority_class <> entity.authority_class
   );

CREATE OR REPLACE FUNCTION execution.validate_numeric_pnf_identity_admission()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    witness_candidate_count SMALLINT;
    witness_authority_class SMALLINT;
    entity_authority_class SMALLINT;
BEGIN
    IF NEW.admission_state <> 2 THEN
        RETURN NEW;
    END IF;

    SELECT witness.candidate_count,
           witness.authority_class,
           entity.authority_class
      INTO witness_candidate_count,
           witness_authority_class,
           entity_authority_class
      FROM execution.semantic_pnf_identity_witness AS witness
      JOIN execution.semantic_pnf_canonical_entity AS entity
        ON entity.entity_id = witness.target_entity_id
     WHERE witness.witness_id = NEW.witness_id;

    IF witness_candidate_count IS NULL THEN
        RAISE EXCEPTION 'identity witness % does not exist', NEW.witness_id;
    END IF;
    IF witness_candidate_count <> 1 THEN
        RAISE EXCEPTION
            'accepted identity witness % must have exactly one candidate, found %',
            NEW.witness_id,
            witness_candidate_count;
    END IF;
    IF witness_authority_class <> entity_authority_class THEN
        RAISE EXCEPTION
            'identity witness % authority % does not match target entity authority %',
            NEW.witness_id,
            witness_authority_class,
            entity_authority_class;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_identity_admission_integrity
    ON execution.semantic_pnf_identity_witness_admission;
CREATE TRIGGER semantic_pnf_identity_admission_integrity
BEFORE INSERT OR UPDATE OF admission_state
ON execution.semantic_pnf_identity_witness_admission
FOR EACH ROW
EXECUTE FUNCTION execution.validate_numeric_pnf_identity_admission();

-- Re-declare the current projection fail-closed as well. The trigger prevents
-- new invalid admissions; the view also excludes any historical rows loaded
-- while triggers were intentionally disabled.
CREATE OR REPLACE VIEW execution.semantic_pnf_identity_projection AS
SELECT witness.source_object_id,
       witness.authority_class,
       min(witness.target_entity_id) AS target_entity_id,
       array_agg(witness.witness_id ORDER BY witness.witness_id) AS witness_ids,
       count(*)::BIGINT AS witness_count
  FROM execution.semantic_pnf_identity_witness AS witness
  JOIN execution.semantic_pnf_identity_witness_admission AS admission
    ON admission.witness_id = witness.witness_id
   AND admission.admission_state = 2
  JOIN execution.semantic_pnf_canonical_entity AS entity
    ON entity.entity_id = witness.target_entity_id
   AND entity.authority_class = witness.authority_class
 WHERE witness.candidate_count = 1
 GROUP BY witness.source_object_id, witness.authority_class
HAVING count(DISTINCT witness.target_entity_id) = 1;

COMMIT;
