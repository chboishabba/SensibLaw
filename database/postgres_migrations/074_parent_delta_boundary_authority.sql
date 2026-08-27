BEGIN;

-- C3a: make the C2 transported parent boundary a first-class canonical input
-- carrier.  This does not yet replace parent-local reconciliation.  It owns
-- only the natural transport/fusion boundary that the existing canonical
-- reducer previously reconstructed by repeatedly joining child regions,
-- interfaces, and exports.
--
-- Formal shape:
--   child boundary delta -> transported parent-local atoms -> parent reducer
-- Parent-local non-monotone semantics (promotion, actor summaries, demand
-- resolution, unique-witness checks) remain outside this function.

CREATE OR REPLACE FUNCTION execution.numeric_pnf_parent_boundary_atoms(
    selected_parent_region_id BIGINT
)
RETURNS TABLE (
    child_region_id BIGINT,
    child_interface_id BIGINT,
    export_kind SMALLINT,
    target_kind SMALLINT,
    target_id BIGINT,
    key_symbol_id BIGINT,
    role_symbol_id BIGINT,
    residual_type_symbol_id BIGINT,
    rank BIGINT,
    promotion_score DOUBLE PRECISION
)
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT projection.child_region_id,
           projection.child_interface_id,
           projection.export_kind,
           projection.target_kind,
           projection.target_id,
           projection.key_symbol_id,
           projection.role_symbol_id,
           projection.residual_type_symbol_id,
           projection.rank,
           projection.promotion_score
      FROM execution.semantic_pnf_parent_delta_projection AS projection
     WHERE projection.parent_region_id = selected_parent_region_id
     ORDER BY projection.child_interface_id,
              projection.export_kind,
              projection.target_kind,
              projection.target_id
$$;

-- The fused boundary is the associative/idempotent image consumed by the
-- parent as a set-like interface.  Child provenance remains available through
-- numeric_pnf_parent_boundary_atoms for parent-local relational summaries.
CREATE OR REPLACE FUNCTION execution.numeric_pnf_parent_fused_boundary(
    selected_parent_region_id BIGINT
)
RETURNS TABLE (
    export_kind SMALLINT,
    target_kind SMALLINT,
    target_id BIGINT,
    key_symbol_id BIGINT,
    role_symbol_id BIGINT,
    residual_type_symbol_id BIGINT,
    rank BIGINT,
    promotion_score DOUBLE PRECISION,
    contributing_child_count BIGINT
)
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT fused.export_kind,
           fused.target_kind,
           fused.target_id,
           fused.key_symbol_id,
           fused.role_symbol_id,
           fused.residual_type_symbol_id,
           fused.rank,
           fused.promotion_score,
           fused.contributing_child_count
      FROM execution.semantic_pnf_parent_delta_fused_export AS fused
     WHERE fused.parent_region_id = selected_parent_region_id
     ORDER BY fused.export_kind, fused.target_kind, fused.target_id
$$;

-- A compact work receipt for the new input carrier.  This deliberately reads
-- only the transported boundary table: no parser tokens, PNF objects, factors,
-- hyperedges, child graph interiors, or global lookup state.
CREATE OR REPLACE FUNCTION execution.measure_numeric_pnf_parent_delta_boundary(
    selected_parent_region_id BIGINT
)
RETURNS TABLE (
    child_interface_count BIGINT,
    transported_atom_count BIGINT,
    fused_atom_count BIGINT,
    object_atom_count BIGINT,
    factor_atom_count BIGINT,
    demand_atom_count BIGINT
)
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT count(DISTINCT projection.child_interface_id),
           count(*),
           (
               SELECT count(*)
                 FROM execution.semantic_pnf_parent_delta_fused_export AS fused
                WHERE fused.parent_region_id = selected_parent_region_id
           ),
           count(*) FILTER (WHERE projection.target_kind = 1),
           count(*) FILTER (WHERE projection.target_kind = 2),
           count(*) FILTER (WHERE projection.target_kind = 3)
      FROM execution.semantic_pnf_parent_delta_projection AS projection
     WHERE projection.parent_region_id = selected_parent_region_id
$$;

-- Certification-only equivalence check against the historical reconstruction
-- query.  Normal execution must not call this function: it intentionally reads
-- the old child-interface/export join so that the new carrier has an
-- independent oracle.  It performs no writes.
CREATE OR REPLACE FUNCTION execution.check_numeric_pnf_parent_boundary_parity(
    selected_parent_region_id BIGINT
)
RETURNS TABLE (
    direct_atom_count BIGINT,
    projected_atom_count BIGINT,
    missing_from_projection BIGINT,
    extra_in_projection BIGINT
)
LANGUAGE sql
STABLE
AS $$
    WITH direct AS (
        SELECT child_region.region_id AS child_region_id,
               child_interface.interface_id AS child_interface_id,
               child_export.export_kind,
               child_export.target_kind,
               child_export.target_id,
               child_export.key_symbol_id,
               child_export.role_symbol_id,
               child_export.residual_type_symbol_id,
               child_export.rank,
               child_export.promotion_score
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
          JOIN execution.semantic_pnf_interface_export AS child_export
            ON child_export.interface_id = child_interface.interface_id
         WHERE child_region.parent_region_id = selected_parent_region_id
           AND child_region.region_kind <> 9
    ), projected AS (
        SELECT child_region_id,
               child_interface_id,
               export_kind,
               target_kind,
               target_id,
               key_symbol_id,
               role_symbol_id,
               residual_type_symbol_id,
               rank,
               promotion_score
          FROM execution.numeric_pnf_parent_boundary_atoms(
              selected_parent_region_id
          )
    )
    SELECT (SELECT count(*) FROM direct),
           (SELECT count(*) FROM projected),
           (
               SELECT count(*)
                 FROM (
                     SELECT * FROM direct
                     EXCEPT ALL
                     SELECT * FROM projected
                 ) AS missing
           ),
           (
               SELECT count(*)
                 FROM (
                     SELECT * FROM projected
                     EXCEPT ALL
                     SELECT * FROM direct
                 ) AS extra
           )
$$;

COMMIT;
