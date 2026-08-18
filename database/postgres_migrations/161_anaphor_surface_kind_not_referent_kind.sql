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
--
-- IMPORTANT: normalize the row BEFORE it is written.  The previous form used an
-- AFTER trigger which UPDATEd execution.semantic_pnf_demand from a trigger on
-- execution.semantic_pnf_demand.  That corrective write re-entered every UPDATE
-- projection on the table, including demand source-object projection, and a
-- clean migration replay could recurse until PostgreSQL exhausted its stack.
-- Row normalization is the semantic operation we actually need: downstream
-- INSERT/UPDATE projections see the canonical row once, with no corrective
-- second write and therefore no trigger cycle.

CREATE OR REPLACE FUNCTION execution.normalize_numeric_pnf_anaphor_referent_kind()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    constant_row execution.semantic_pnf_anaphor_projection_constant%ROWTYPE;
BEGIN
    IF NEW.expected_object_kind_symbol_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT constant.*
      INTO constant_row
      FROM execution.semantic_pnf_anaphor_projection_constant AS constant
     WHERE constant.singleton;

    IF NEW.residual_type_symbol_id=constant_row.anaphor_residual_type_symbol_id
       AND NEW.expected_object_kind_symbol_id=constant_row.pronoun_object_kind_symbol_id
    THEN
        NEW.expected_object_kind_symbol_id := NULL;
    END IF;

    RETURN NEW;
END;
$$;

-- Drop both historical spellings so replay/upgrades cannot leave an AFTER
-- self-update trigger active alongside the canonical BEFORE-row normalizer.
DROP TRIGGER IF EXISTS semantic_pnf_anaphor_referent_kind_insert
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_zz_anaphor_referent_kind_insert
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_anaphor_referent_kind_update
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_zz_anaphor_referent_kind_update
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_anaphor_referent_kind_insert_before
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_anaphor_referent_kind_update_before
    ON execution.semantic_pnf_demand;

CREATE TRIGGER semantic_pnf_anaphor_referent_kind_insert_before
BEFORE INSERT ON execution.semantic_pnf_demand
FOR EACH ROW
WHEN (NEW.expected_object_kind_symbol_id IS NOT NULL)
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_referent_kind();

CREATE TRIGGER semantic_pnf_anaphor_referent_kind_update_before
BEFORE UPDATE OF residual_type_symbol_id, expected_object_kind_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW
WHEN (
    NEW.expected_object_kind_symbol_id IS NOT NULL
    AND (
        NEW.residual_type_symbol_id IS DISTINCT FROM OLD.residual_type_symbol_id
        OR NEW.expected_object_kind_symbol_id
             IS DISTINCT FROM OLD.expected_object_kind_symbol_id
    )
)
EXECUTE FUNCTION execution.normalize_numeric_pnf_anaphor_referent_kind();

-- Repair historical migration-045 rows without changing any stronger typed
-- anaphor demand whose expected kind is something other than mention.pronoun.
-- This is one ordinary data migration UPDATE.  The BEFORE normalizer does not
-- issue another write, so all downstream UPDATE projections are entered at most
-- once for this statement.
UPDATE execution.semantic_pnf_demand AS demand
   SET expected_object_kind_symbol_id=NULL
  FROM execution.semantic_pnf_anaphor_projection_constant AS constant
 WHERE constant.singleton
   AND demand.residual_type_symbol_id=constant.anaphor_residual_type_symbol_id
   AND demand.expected_object_kind_symbol_id=constant.pronoun_object_kind_symbol_id;

COMMIT;
