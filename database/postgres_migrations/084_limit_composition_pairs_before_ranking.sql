BEGIN;

-- Migration 082 introduced LATERAL LIMIT, but ranking in the same subquery can
-- still require a complete window sort before LIMIT.  Make the execution order
-- explicit: obtain the deterministic first K raw pairs, then rank only those K.

CREATE OR REPLACE FUNCTION execution.numeric_pnf_bounded_local_composition_pairs(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    max_per_bridge INTEGER
)
RETURNS TABLE (
    source_interface_id BIGINT,
    region_id BIGINT,
    bridge_object_id BIGINT,
    left_factor_id BIGINT,
    right_factor_id BIGINT,
    left_role_symbol_id BIGINT,
    right_role_symbol_id BIGINT,
    candidate_rank SMALLINT
)
LANGUAGE sql
STABLE
AS $$
WITH bridge AS MATERIALIZED (
    SELECT factor.region_id,
           interface.interface_id AS source_interface_id,
           edge.object_id
      FROM execution.semantic_pnf_hyperedge AS edge
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = edge.factor_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = factor.region_id
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id = region.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
     GROUP BY factor.region_id, interface.interface_id, edge.object_id
    HAVING count(*) > 1
)
SELECT bridge.source_interface_id,
       bridge.region_id,
       bridge.object_id,
       pair.left_factor_id,
       pair.right_factor_id,
       pair.left_role_symbol_id,
       pair.right_role_symbol_id,
       pair.candidate_rank
  FROM bridge
  CROSS JOIN LATERAL (
      SELECT limited.left_factor_id,
             limited.right_factor_id,
             limited.left_role_symbol_id,
             limited.right_role_symbol_id,
             (row_number() OVER (
                 ORDER BY limited.left_factor_id,
                          limited.right_factor_id,
                          limited.left_slot_ordinal,
                          limited.right_slot_ordinal
              ) - 1)::SMALLINT AS candidate_rank
        FROM (
            SELECT left_edge.factor_id AS left_factor_id,
                   right_edge.factor_id AS right_factor_id,
                   left_edge.role_symbol_id AS left_role_symbol_id,
                   right_edge.role_symbol_id AS right_role_symbol_id,
                   left_edge.slot_ordinal AS left_slot_ordinal,
                   right_edge.slot_ordinal AS right_slot_ordinal
              FROM execution.semantic_pnf_hyperedge AS left_edge
              JOIN execution.semantic_pnf_factor AS left_factor
                ON left_factor.factor_id = left_edge.factor_id
               AND left_factor.region_id = bridge.region_id
              JOIN execution.semantic_pnf_hyperedge AS right_edge
                ON right_edge.object_id = bridge.object_id
               AND right_edge.factor_id > left_edge.factor_id
              JOIN execution.semantic_pnf_factor AS right_factor
                ON right_factor.factor_id = right_edge.factor_id
               AND right_factor.region_id = bridge.region_id
             WHERE left_edge.object_id = bridge.object_id
             ORDER BY left_edge.factor_id,
                      right_edge.factor_id,
                      left_edge.slot_ordinal,
                      right_edge.slot_ordinal
             LIMIT max_per_bridge
        ) AS limited
  ) AS pair;
$$;

CREATE OR REPLACE FUNCTION execution.numeric_pnf_bounded_entity_composition_pairs(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    max_per_bridge INTEGER
)
RETURNS TABLE (
    source_interface_id BIGINT,
    region_id BIGINT,
    bridge_entity_id BIGINT,
    identity_authority_class SMALLINT,
    left_factor_id BIGINT,
    right_factor_id BIGINT,
    left_role_symbol_id BIGINT,
    right_role_symbol_id BIGINT,
    candidate_rank SMALLINT
)
LANGUAGE sql
STABLE
AS $$
WITH projected_edge AS MATERIALIZED (
    SELECT edge.factor_id,
           edge.slot_ordinal,
           edge.role_symbol_id,
           factor.region_id,
           interface.interface_id AS source_interface_id,
           projection.target_entity_id,
           projection.authority_class
      FROM execution.semantic_pnf_hyperedge AS edge
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = edge.factor_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = factor.region_id
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id = region.region_id
      JOIN execution.semantic_pnf_identity_projection AS projection
        ON projection.source_object_id = edge.object_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
), bridge AS MATERIALIZED (
    SELECT region_id,
           source_interface_id,
           target_entity_id,
           authority_class
      FROM projected_edge
     GROUP BY region_id, source_interface_id,
              target_entity_id, authority_class
    HAVING count(*) > 1
)
SELECT bridge.source_interface_id,
       bridge.region_id,
       bridge.target_entity_id,
       bridge.authority_class,
       pair.left_factor_id,
       pair.right_factor_id,
       pair.left_role_symbol_id,
       pair.right_role_symbol_id,
       pair.candidate_rank
  FROM bridge
  CROSS JOIN LATERAL (
      SELECT limited.left_factor_id,
             limited.right_factor_id,
             limited.left_role_symbol_id,
             limited.right_role_symbol_id,
             (row_number() OVER (
                 ORDER BY limited.left_factor_id,
                          limited.right_factor_id,
                          limited.left_slot_ordinal,
                          limited.right_slot_ordinal
              ) - 1)::SMALLINT AS candidate_rank
        FROM (
            SELECT left_edge.factor_id AS left_factor_id,
                   right_edge.factor_id AS right_factor_id,
                   left_edge.role_symbol_id AS left_role_symbol_id,
                   right_edge.role_symbol_id AS right_role_symbol_id,
                   left_edge.slot_ordinal AS left_slot_ordinal,
                   right_edge.slot_ordinal AS right_slot_ordinal
              FROM projected_edge AS left_edge
              JOIN projected_edge AS right_edge
                ON right_edge.region_id = left_edge.region_id
               AND right_edge.target_entity_id = left_edge.target_entity_id
               AND right_edge.authority_class = left_edge.authority_class
               AND right_edge.factor_id > left_edge.factor_id
             WHERE left_edge.region_id = bridge.region_id
               AND left_edge.target_entity_id = bridge.target_entity_id
               AND left_edge.authority_class = bridge.authority_class
             ORDER BY left_edge.factor_id,
                      right_edge.factor_id,
                      left_edge.slot_ordinal,
                      right_edge.slot_ordinal
             LIMIT max_per_bridge
        ) AS limited
  ) AS pair;
$$;

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_factor_composition_candidates(
    selected_run_id BIGINT,
    selected_document_id BIGINT,
    max_per_bridge INTEGER DEFAULT 16
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    local_inserted BIGINT := 0;
    identity_inserted BIGINT := 0;
BEGIN
    IF max_per_bridge < 1 OR max_per_bridge > 256 THEN
        RAISE EXCEPTION 'max_per_bridge must be between 1 and 256';
    END IF;

    DELETE FROM execution.semantic_pnf_factor_composition_candidate AS candidate
    USING execution.semantic_pnf_region AS region
     WHERE candidate.region_id = region.region_id
       AND region.run_id = selected_run_id
       AND region.document_id = selected_document_id;

    DELETE FROM execution.semantic_pnf_factor_composition_overflow
     WHERE run_id = selected_run_id
       AND document_id = selected_document_id;

    INSERT INTO execution.semantic_pnf_factor_composition_candidate
        (source_interface_id, region_id,
         left_factor_id, right_factor_id,
         left_role_symbol_id, right_role_symbol_id,
         bridge_object_id, bridge_entity_id,
         identity_authority_class, candidate_rank)
    SELECT source_interface_id,
           region_id,
           left_factor_id,
           right_factor_id,
           left_role_symbol_id,
           right_role_symbol_id,
           bridge_object_id,
           NULL,
           NULL,
           candidate_rank
      FROM execution.numeric_pnf_bounded_local_composition_pairs(
          selected_run_id, selected_document_id, max_per_bridge
      )
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS local_inserted = ROW_COUNT;

    WITH bridge AS MATERIALIZED (
        SELECT factor.region_id,
               edge.object_id,
               count(*)::BIGINT AS participant_count
          FROM execution.semantic_pnf_hyperedge AS edge
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = edge.factor_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = factor.region_id
         WHERE region.run_id = selected_run_id
           AND region.document_id = selected_document_id
         GROUP BY factor.region_id, edge.object_id
        HAVING count(*) > 1
    )
    INSERT INTO execution.semantic_pnf_factor_composition_overflow
        (run_id, document_id, region_id, bridge_kind,
         bridge_object_id, bridge_entity_id, identity_authority_class,
         participant_count, possible_pair_count, retained_pair_limit)
    SELECT selected_run_id,
           selected_document_id,
           region_id,
           1,
           object_id,
           NULL,
           NULL,
           participant_count,
           (participant_count * (participant_count - 1)) / 2,
           max_per_bridge::SMALLINT
      FROM bridge
     WHERE (participant_count * (participant_count - 1)) / 2 > max_per_bridge
    ON CONFLICT (run_id, document_id, region_id, bridge_object_id)
        WHERE bridge_kind = 1
    DO UPDATE SET
        participant_count = EXCLUDED.participant_count,
        possible_pair_count = EXCLUDED.possible_pair_count,
        retained_pair_limit = EXCLUDED.retained_pair_limit,
        observed_at = CURRENT_TIMESTAMP;

    INSERT INTO execution.semantic_pnf_factor_composition_candidate
        (source_interface_id, region_id,
         left_factor_id, right_factor_id,
         left_role_symbol_id, right_role_symbol_id,
         bridge_object_id, bridge_entity_id,
         identity_authority_class, candidate_rank)
    SELECT source_interface_id,
           region_id,
           left_factor_id,
           right_factor_id,
           left_role_symbol_id,
           right_role_symbol_id,
           NULL,
           bridge_entity_id,
           identity_authority_class,
           candidate_rank
      FROM execution.numeric_pnf_bounded_entity_composition_pairs(
          selected_run_id, selected_document_id, max_per_bridge
      )
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS identity_inserted = ROW_COUNT;

    WITH projected_edge AS MATERIALIZED (
        SELECT factor.region_id,
               projection.target_entity_id,
               projection.authority_class
          FROM execution.semantic_pnf_hyperedge AS edge
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = edge.factor_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = factor.region_id
          JOIN execution.semantic_pnf_identity_projection AS projection
            ON projection.source_object_id = edge.object_id
         WHERE region.run_id = selected_run_id
           AND region.document_id = selected_document_id
    ), bridge AS (
        SELECT region_id,
               target_entity_id,
               authority_class,
               count(*)::BIGINT AS participant_count
          FROM projected_edge
         GROUP BY region_id, target_entity_id, authority_class
        HAVING count(*) > 1
    )
    INSERT INTO execution.semantic_pnf_factor_composition_overflow
        (run_id, document_id, region_id, bridge_kind,
         bridge_object_id, bridge_entity_id, identity_authority_class,
         participant_count, possible_pair_count, retained_pair_limit)
    SELECT selected_run_id,
           selected_document_id,
           region_id,
           2,
           NULL,
           target_entity_id,
           authority_class,
           participant_count,
           (participant_count * (participant_count - 1)) / 2,
           max_per_bridge::SMALLINT
      FROM bridge
     WHERE (participant_count * (participant_count - 1)) / 2 > max_per_bridge
    ON CONFLICT (run_id, document_id, region_id,
                 bridge_entity_id, identity_authority_class)
        WHERE bridge_kind = 2
    DO UPDATE SET
        participant_count = EXCLUDED.participant_count,
        possible_pair_count = EXCLUDED.possible_pair_count,
        retained_pair_limit = EXCLUDED.retained_pair_limit,
        observed_at = CURRENT_TIMESTAMP;

    RETURN local_inserted + identity_inserted;
END;
$$;

COMMIT;
