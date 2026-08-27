BEGIN;

-- 181: canonical candidate witness reduction.
--
-- E0d parity diagnosis exposed a pre-existing reducer ambiguity. A single
-- (demand_id,target_kind,target_id) may be produced by several actor-profile
-- witnesses. Migration 062 deduplicated those rows by structural distance,
-- index rank and source interface, but did not include candidate_score in the
-- witness tie-break. When those coordinates tied, PostgreSQL was free to retain
-- any witness. Migration 178 changed physical exposure order and thereby made
-- the latent ambiguity observable as different persisted candidate scores over
-- an otherwise identical candidate target/evidence relation.
--
-- Migration 086 already classifies candidate_score as planner/execution state,
-- not semantic signed evidence. Even so, DASHI future-language safety requires
-- the execution quotient to be deterministic wherever that score can influence
-- later bounded selection. Canonicalize the representative before target
-- ranking by preferring the highest score among equally-near witnesses.
--
-- This does not change candidate membership, typed constraints, recency,
-- structural distance or final resolution semantics. It only removes an
-- under-specified representative choice inside one target fibre.

DO $migration$
DECLARE
    source_body TEXT;
    patched_body TEXT;
    old_order TEXT := E'                   ORDER BY candidate.structural_distance,\n'
        || E'                            candidate.index_rank,\n'
        || E'                            candidate.source_interface_id\n';
    new_order TEXT := E'                   ORDER BY candidate.structural_distance,\n'
        || E'                            candidate.candidate_score DESC,\n'
        || E'                            candidate.index_rank,\n'
        || E'                            candidate.source_interface_id\n';
BEGIN
    SELECT procedure.prosrc
      INTO source_body
      FROM pg_proc AS procedure
      JOIN pg_namespace AS namespace
        ON namespace.oid = procedure.pronamespace
     WHERE namespace.nspname = 'execution'
       AND procedure.proname = 'rebuild_numeric_pnf_parent_frontier_canonical'
       AND procedure.pronargs = 1
       AND procedure.proargtypes[0] = 'int8'::regtype::oid;

    IF source_body IS NULL THEN
        RAISE EXCEPTION
            'migration 181 cannot find execution.rebuild_numeric_pnf_parent_frontier_canonical(bigint)';
    END IF;

    IF strpos(source_body, new_order) > 0 THEN
        RETURN;
    END IF;

    IF strpos(source_body, old_order) = 0 THEN
        RAISE EXCEPTION
            'migration 181 refuses to patch an unrecognised candidate witness ordering';
    END IF;

    patched_body := replace(source_body, old_order, new_order);

    IF patched_body = source_body THEN
        RAISE EXCEPTION
            'migration 181 candidate witness replacement made no change';
    END IF;

    IF strpos(patched_body, old_order) > 0 THEN
        RAISE EXCEPTION
            'migration 181 found more than one unresolved legacy witness ordering';
    END IF;

    EXECUTE
        'CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier_canonical('
        || 'selected_interface_id BIGINT) '
        || 'RETURNS TABLE ('
        || 'output_export_count BIGINT, '
        || 'unresolved_demand_count BIGINT, '
        || 'resolved_demand_count BIGINT, '
        || 'actor_profile_count BIGINT) '
        || 'LANGUAGE plpgsql AS '
        || quote_literal(patched_body);
END;
$migration$;

COMMENT ON FUNCTION execution.rebuild_numeric_pnf_parent_frontier_canonical(BIGINT) IS
'Canonical sparse-frontier reducer. Duplicate witnesses for one candidate target are reduced by structural distance, then highest candidate score, then index/source coordinates before target ranking.';

COMMIT;
