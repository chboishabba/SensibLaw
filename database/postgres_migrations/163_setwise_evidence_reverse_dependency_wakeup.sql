BEGIN;

-- 163: migration 091 expanded every candidate-evidence row through one PL/pgSQL
-- trigger into evidence/region/interface reverse-dependency edges plus one
-- incremental wakeup. These are direct projections of the inserted evidence
-- relation and factorize exactly.

DROP TRIGGER IF EXISTS semantic_pnf_candidate_evidence_reverse_dependency
    ON execution.semantic_pnf_candidate_evidence;

CREATE OR REPLACE FUNCTION execution.index_numeric_pnf_evidence_reverse_dependency_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind,source_id,demand_id,dependency_kind)
    SELECT 6,evidence.evidence_id,evidence.demand_id,3
      FROM inserted_evidence AS evidence
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind,source_id,demand_id,dependency_kind)
    SELECT 4,evidence.source_region_id,evidence.demand_id,3
      FROM inserted_evidence AS evidence
     WHERE evidence.source_region_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind,source_id,demand_id,dependency_kind)
    SELECT 5,evidence.source_interface_id,evidence.demand_id,3
      FROM inserted_evidence AS evidence
     WHERE evidence.source_interface_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_incremental_work_queue
        (source_kind,source_id,demand_id,horizon)
    SELECT 6,evidence.evidence_id,evidence.demand_id,evidence.horizon
      FROM inserted_evidence AS evidence
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_candidate_evidence_reverse_dependency_batch
AFTER INSERT ON execution.semantic_pnf_candidate_evidence
REFERENCING NEW TABLE AS inserted_evidence
FOR EACH STATEMENT
EXECUTE FUNCTION execution.index_numeric_pnf_evidence_reverse_dependency_batch();

COMMIT;
