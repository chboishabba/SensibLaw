BEGIN;

-- Candidate generation is deliberately broad but bounded.  This statement
-- trigger applies the full typed-hole conjunction before candidate counts or
-- unique-witness resolution are computed by the enclosing frontier reducer.
CREATE OR REPLACE FUNCTION execution.filter_numeric_pnf_candidate_constraints()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_demand_candidate AS candidate
    USING inserted_candidate AS inserted
    WHERE candidate.demand_id = inserted.demand_id
      AND candidate.ordinal = inserted.ordinal
      AND (
          EXISTS (
              SELECT 1
                FROM execution.semantic_pnf_demand_constraint AS constraint_row
               WHERE constraint_row.demand_id = candidate.demand_id
                 AND constraint_row.required
                 AND constraint_row.polarity = 1
                 AND constraint_row.key_kind <> 5
                 AND NOT (
                     CASE candidate.target_kind
                         WHEN 1 THEN
                             CASE constraint_row.key_kind
                                 WHEN 1 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_actor_profile
                                            AS profile
                                      WHERE profile.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND profile.object_id = candidate.target_id
                                        AND profile.factor_type_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 2 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_object AS object
                                      WHERE object.object_id = candidate.target_id
                                        AND object.object_kind_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 3 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_object AS object
                                      WHERE object.object_id = candidate.target_id
                                        AND object.head_symbol_id
                                            = constraint_row.key_a
                                     UNION ALL
                                     SELECT 1
                                       FROM execution.semantic_pnf_actor_profile
                                            AS profile
                                      WHERE profile.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND profile.object_id = candidate.target_id
                                        AND profile.predicate_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 4 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_actor_profile
                                            AS profile
                                      WHERE profile.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND profile.object_id = candidate.target_id
                                        AND profile.role_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 6 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_interface_lookup
                                            AS lookup
                                      WHERE lookup.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND lookup.target_kind = 1
                                        AND lookup.target_id = candidate.target_id
                                        AND lookup.key_kind = 6
                                        AND lookup.key_a = constraint_row.key_a
                                        AND lookup.key_b = constraint_row.key_b
                                 )
                                 WHEN 7 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_interface_lookup
                                            AS lookup
                                      WHERE lookup.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND lookup.target_kind = 1
                                        AND lookup.target_id = candidate.target_id
                                        AND lookup.key_kind = 7
                                        AND lookup.key_a = constraint_row.key_a
                                        AND lookup.key_b = constraint_row.key_b
                                 )
                                 ELSE TRUE
                             END
                         WHEN 2 THEN
                             CASE constraint_row.key_kind
                                 WHEN 1 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_factor AS factor
                                      WHERE factor.factor_id = candidate.target_id
                                        AND factor.factor_type_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 2 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_hyperedge AS edge
                                       JOIN execution.semantic_pnf_object AS object
                                         ON object.object_id = edge.object_id
                                      WHERE edge.factor_id = candidate.target_id
                                        AND object.object_kind_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 3 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_factor AS factor
                                      WHERE factor.factor_id = candidate.target_id
                                        AND factor.predicate_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 4 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_hyperedge AS edge
                                      WHERE edge.factor_id = candidate.target_id
                                        AND edge.role_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 6 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_interface_lookup
                                            AS lookup
                                      WHERE lookup.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND lookup.target_kind = 2
                                        AND lookup.target_id = candidate.target_id
                                        AND lookup.key_kind = 6
                                        AND lookup.key_a = constraint_row.key_a
                                        AND lookup.key_b = constraint_row.key_b
                                 )
                                 WHEN 7 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_interface_lookup
                                            AS lookup
                                      WHERE lookup.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND lookup.target_kind = 2
                                        AND lookup.target_id = candidate.target_id
                                        AND lookup.key_kind = 7
                                        AND lookup.key_a = constraint_row.key_a
                                        AND lookup.key_b = constraint_row.key_b
                                 )
                                 ELSE TRUE
                             END
                         ELSE TRUE
                     END
                 )
          )
          OR EXISTS (
              SELECT 1
                FROM execution.semantic_pnf_demand_constraint AS constraint_row
               WHERE constraint_row.demand_id = candidate.demand_id
                 AND constraint_row.required
                 AND constraint_row.polarity = -1
                 AND constraint_row.key_kind <> 5
                 AND (
                     CASE candidate.target_kind
                         WHEN 1 THEN
                             CASE constraint_row.key_kind
                                 WHEN 1 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_actor_profile
                                            AS profile
                                      WHERE profile.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND profile.object_id = candidate.target_id
                                        AND profile.factor_type_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 2 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_object AS object
                                      WHERE object.object_id = candidate.target_id
                                        AND object.object_kind_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 3 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_object AS object
                                      WHERE object.object_id = candidate.target_id
                                        AND object.head_symbol_id
                                            = constraint_row.key_a
                                     UNION ALL
                                     SELECT 1
                                       FROM execution.semantic_pnf_actor_profile
                                            AS profile
                                      WHERE profile.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND profile.object_id = candidate.target_id
                                        AND profile.predicate_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 4 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_actor_profile
                                            AS profile
                                      WHERE profile.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND profile.object_id = candidate.target_id
                                        AND profile.role_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 6 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_interface_lookup
                                            AS lookup
                                      WHERE lookup.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND lookup.target_kind = 1
                                        AND lookup.target_id = candidate.target_id
                                        AND lookup.key_kind = 6
                                        AND lookup.key_a = constraint_row.key_a
                                        AND lookup.key_b = constraint_row.key_b
                                 )
                                 WHEN 7 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_interface_lookup
                                            AS lookup
                                      WHERE lookup.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND lookup.target_kind = 1
                                        AND lookup.target_id = candidate.target_id
                                        AND lookup.key_kind = 7
                                        AND lookup.key_a = constraint_row.key_a
                                        AND lookup.key_b = constraint_row.key_b
                                 )
                                 ELSE FALSE
                             END
                         WHEN 2 THEN
                             CASE constraint_row.key_kind
                                 WHEN 1 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_factor AS factor
                                      WHERE factor.factor_id = candidate.target_id
                                        AND factor.factor_type_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 2 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_hyperedge AS edge
                                       JOIN execution.semantic_pnf_object AS object
                                         ON object.object_id = edge.object_id
                                      WHERE edge.factor_id = candidate.target_id
                                        AND object.object_kind_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 3 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_factor AS factor
                                      WHERE factor.factor_id = candidate.target_id
                                        AND factor.predicate_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 4 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_hyperedge AS edge
                                      WHERE edge.factor_id = candidate.target_id
                                        AND edge.role_symbol_id
                                            = constraint_row.key_a
                                 )
                                 WHEN 6 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_interface_lookup
                                            AS lookup
                                      WHERE lookup.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND lookup.target_kind = 2
                                        AND lookup.target_id = candidate.target_id
                                        AND lookup.key_kind = 6
                                        AND lookup.key_a = constraint_row.key_a
                                        AND lookup.key_b = constraint_row.key_b
                                 )
                                 WHEN 7 THEN EXISTS (
                                     SELECT 1
                                       FROM execution.semantic_pnf_interface_lookup
                                            AS lookup
                                      WHERE lookup.interface_id = COALESCE(
                                                candidate.common_scope_interface_id,
                                                candidate.source_interface_id
                                            )
                                        AND lookup.target_kind = 2
                                        AND lookup.target_id = candidate.target_id
                                        AND lookup.key_kind = 7
                                        AND lookup.key_a = constraint_row.key_a
                                        AND lookup.key_b = constraint_row.key_b
                                 )
                                 ELSE FALSE
                             END
                         ELSE FALSE
                     END
                 )
          )
      );
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_typed_candidate_constraints
    ON execution.semantic_pnf_demand_candidate;
CREATE TRIGGER semantic_pnf_typed_candidate_constraints
AFTER INSERT ON execution.semantic_pnf_demand_candidate
REFERENCING NEW TABLE AS inserted_candidate
FOR EACH STATEMENT
EXECUTE FUNCTION execution.filter_numeric_pnf_candidate_constraints();

COMMIT;
