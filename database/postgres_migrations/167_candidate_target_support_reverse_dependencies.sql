BEGIN;

-- 167: candidate membership depends on the exact provenance support of its
-- represented target. Migration 091 backfilled object-target token support once,
-- but later candidate inserts did not maintain the same reverse dependency and
-- factor-target support was absent. Missing reverse edges can make incremental
-- reopening unsound; conservative stale/extra edges merely over-wake.
--
-- Maintain the exact token -> candidate target -> demand dependency set-wise from
-- both write orders: candidate after support, or support after candidate.
-- dependency_kind=2 remains the candidate-target provenance family established
-- by migration 091.

CREATE OR REPLACE FUNCTION execution.index_numeric_pnf_candidate_target_support_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind,source_id,demand_id,dependency_kind)
    SELECT 1,support.token_id,candidate.demand_id,2
      FROM inserted_candidate AS candidate
      JOIN execution.semantic_pnf_object_token_support AS support
        ON candidate.target_kind=1
       AND support.object_id=candidate.target_id
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind,source_id,demand_id,dependency_kind)
    SELECT 1,support.token_id,candidate.demand_id,2
      FROM inserted_candidate AS candidate
      JOIN execution.semantic_pnf_factor_token_support AS support
        ON candidate.target_kind=2
       AND support.factor_id=candidate.target_id
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_candidate_target_support_reverse_dependency_batch
    ON execution.semantic_pnf_demand_candidate;
CREATE TRIGGER semantic_pnf_candidate_target_support_reverse_dependency_batch
AFTER INSERT ON execution.semantic_pnf_demand_candidate
REFERENCING NEW TABLE AS inserted_candidate
FOR EACH STATEMENT
EXECUTE FUNCTION execution.index_numeric_pnf_candidate_target_support_batch();

CREATE OR REPLACE FUNCTION execution.index_numeric_pnf_object_support_candidate_dependencies_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind,source_id,demand_id,dependency_kind)
    SELECT 1,support.token_id,candidate.demand_id,2
      FROM inserted_object_support AS support
      JOIN execution.semantic_pnf_demand_candidate AS candidate
        ON candidate.target_kind=1
       AND candidate.target_id=support.object_id
    ON CONFLICT DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_object_support_candidate_dependency_batch
    ON execution.semantic_pnf_object_token_support;
CREATE TRIGGER semantic_pnf_object_support_candidate_dependency_batch
AFTER INSERT ON execution.semantic_pnf_object_token_support
REFERENCING NEW TABLE AS inserted_object_support
FOR EACH STATEMENT
EXECUTE FUNCTION execution.index_numeric_pnf_object_support_candidate_dependencies_batch();

CREATE OR REPLACE FUNCTION execution.index_numeric_pnf_factor_support_candidate_dependencies_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_reverse_dependency
        (source_kind,source_id,demand_id,dependency_kind)
    SELECT 1,support.token_id,candidate.demand_id,2
      FROM inserted_factor_support AS support
      JOIN execution.semantic_pnf_demand_candidate AS candidate
        ON candidate.target_kind=2
       AND candidate.target_id=support.factor_id
    ON CONFLICT DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_factor_support_candidate_dependency_batch
    ON execution.semantic_pnf_factor_token_support;
CREATE TRIGGER semantic_pnf_factor_support_candidate_dependency_batch
AFTER INSERT ON execution.semantic_pnf_factor_token_support
REFERENCING NEW TABLE AS inserted_factor_support
FOR EACH STATEMENT
EXECUTE FUNCTION execution.index_numeric_pnf_factor_support_candidate_dependencies_batch();

-- Upgrade/backfill both candidate target kinds. Object rows duplicate the 091
-- bootstrap harmlessly; factor rows close the previously unrepresented lane.
INSERT INTO execution.semantic_pnf_reverse_dependency
    (source_kind,source_id,demand_id,dependency_kind)
SELECT 1,support.token_id,candidate.demand_id,2
  FROM execution.semantic_pnf_demand_candidate AS candidate
  JOIN execution.semantic_pnf_object_token_support AS support
    ON candidate.target_kind=1
   AND support.object_id=candidate.target_id
ON CONFLICT DO NOTHING;

INSERT INTO execution.semantic_pnf_reverse_dependency
    (source_kind,source_id,demand_id,dependency_kind)
SELECT 1,support.token_id,candidate.demand_id,2
  FROM execution.semantic_pnf_demand_candidate AS candidate
  JOIN execution.semantic_pnf_factor_token_support AS support
    ON candidate.target_kind=2
   AND support.factor_id=candidate.target_id
ON CONFLICT DO NOTHING;

COMMIT;
