BEGIN;

-- 161: a pronoun is the type of the *surface occurrence*, not evidence that its
-- referent is itself a pronoun. Migration 045 historically copied
-- mention.pronoun into expected_object_kind_symbol_id for anaphor_unresolved
-- demands. The old 047/053 special anaphor planners happened to ignore that
-- coordinate; the later sparse frontier reducer correctly treats an expected
-- object kind as a real constraint, exposing the modelling error.
--
-- Generic anaphora therefore carry:
--   source object kind        = mention.pronoun
--   surface lexical evidence  = pronoun lemma
--   expected referent kind    = NULL unless some independent producer supplies
--                               a stronger referent-type fact.
--
-- This migration only removes the accidental self-kind constraint. It does not
-- infer person/agent/entity from pronoun morphology and does not resolve a
-- referent.

CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_referent_kind_inserted()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE execution.semantic_pnf_demand AS demand
       SET expected_object_kind_symbol_id=NULL
      FROM inserted_demand AS inserted
      JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
        ON constant.singleton
     WHERE demand.demand_id=inserted.demand_id
       AND inserted.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
       AND inserted.expected_object_kind_symbol_id=constant.pronoun_object_kind_symbol_id;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_anaphor_referent_kind_insert
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_anaphor_referent_kind_insert
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_referent_kind_inserted();

CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_referent_kind_updated()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed AS MATERIALIZED (
        SELECT current.demand_id,
               current.residual_type_symbol_id,
               current.expected_object_kind_symbol_id
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING(demand_id)
         WHERE current.residual_type_symbol_id IS DISTINCT FROM prior.residual_type_symbol_id
            OR current.expected_object_kind_symbol_id
                 IS DISTINCT FROM prior.expected_object_kind_symbol_id
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET expected_object_kind_symbol_id=NULL
      FROM changed
      JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
        ON constant.singleton
     WHERE demand.demand_id=changed.demand_id
       AND changed.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
       AND changed.expected_object_kind_symbol_id=constant.pronoun_object_kind_symbol_id;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_anaphor_referent_kind_update
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_anaphor_referent_kind_update
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_referent_kind_updated();

-- Repair historical migration-045 rows without changing any stronger typed
-- anaphor demand whose expected kind is something other than mention.pronoun.
UPDATE execution.semantic_pnf_demand AS demand
   SET expected_object_kind_symbol_id=NULL
  FROM execution.semantic_pnf_anaphor_projection_constant AS constant
 WHERE constant.singleton
   AND demand.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
   AND demand.expected_object_kind_symbol_id=constant.pronoun_object_kind_symbol_id;

COMMIT;
