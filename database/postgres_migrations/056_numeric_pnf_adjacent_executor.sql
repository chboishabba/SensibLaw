BEGIN;

-- Checked cross-boundary candidate evidence is kept distinct from resolution.
-- A later resolver may consume it, but this executor never changes a demand's
-- resolved_target fields merely because two regions are adjacent.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_adjacent_candidate_evidence (
    pair_interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    target_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_target_kind(kind_id) ON DELETE RESTRICT,
    target_id BIGINT NOT NULL,
    candidate_interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    source_member_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    target_member_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    ordinal SMALLINT NOT NULL CHECK (ordinal BETWEEN 0 AND 255),
    candidate_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pair_interface_id, demand_id, target_kind, target_id),
    UNIQUE (pair_interface_id, demand_id, ordinal),
    CHECK (source_member_region_id <> target_member_region_id)
);

CREATE INDEX IF NOT EXISTS semantic_pnf_adjacent_candidate_demand_idx
    ON execution.semantic_pnf_adjacent_candidate_evidence
       (demand_id, ordinal, pair_interface_id);

CREATE OR REPLACE FUNCTION execution.execute_numeric_pnf_adjacent_work(
    selected_work_id BIGINT,
    selected_lease_token TEXT,
    selected_lease_epoch BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    work_row RECORD;
    pair_row RECORD;
    left_row RECORD;
    right_row RECORD;
    left_interface RECORD;
    right_interface RECORD;
    canonical_parent_interface_id BIGINT;
    selected_pair_interface_id BIGINT;
    next_revision BIGINT;
    pair_digest BYTEA;
    aggregate RECORD;
BEGIN
    SELECT work.work_id,
           work.region_id,
           work.operation_id,
           work.state_id,
           work.lease_token,
           work.lease_epoch
      INTO work_row
      FROM execution.semantic_pnf_work_item AS work
     WHERE work.work_id = selected_work_id
     FOR UPDATE;

    IF work_row.work_id IS NULL THEN
        RAISE EXCEPTION 'adjacent reconciliation work % is missing', selected_work_id;
    END IF;
    IF work_row.operation_id <> 2
       OR work_row.state_id <> 2
       OR work_row.lease_token IS DISTINCT FROM selected_lease_token
       OR work_row.lease_epoch IS DISTINCT FROM selected_lease_epoch THEN
        RAISE EXCEPTION 'adjacent reconciliation work fence changed';
    END IF;

    SELECT * INTO pair_row
      FROM execution.semantic_pnf_region
     WHERE region_id = work_row.region_id
     FOR UPDATE;
    IF pair_row.region_kind NOT IN (2, 4) THEN
        RAISE EXCEPTION 'adjacent reconciliation work has non-pair region %',
            pair_row.region_id;
    END IF;

    SELECT member.*, edge.ordinal
      INTO left_row
      FROM execution.semantic_pnf_region_edge AS edge
      JOIN execution.semantic_pnf_region AS member
        ON member.region_id = edge.source_region_id
     WHERE edge.target_region_id = pair_row.region_id
       AND edge.edge_kind = 1
       AND edge.ordinal = 0;
    SELECT member.*, edge.ordinal
      INTO right_row
      FROM execution.semantic_pnf_region_edge AS edge
      JOIN execution.semantic_pnf_region AS member
        ON member.region_id = edge.source_region_id
     WHERE edge.target_region_id = pair_row.region_id
       AND edge.edge_kind = 1
       AND edge.ordinal = 1;

    IF left_row.region_id IS NULL OR right_row.region_id IS NULL THEN
        RAISE EXCEPTION 'adjacent pair % does not have two ordered members',
            pair_row.region_id;
    END IF;
    IF left_row.closure_state NOT IN (2, 3)
       OR right_row.closure_state NOT IN (2, 3) THEN
        RAISE EXCEPTION 'adjacent pair members are not locally closed';
    END IF;

    SELECT * INTO left_interface
      FROM execution.semantic_pnf_interface
     WHERE region_id = left_row.region_id;
    SELECT * INTO right_interface
      FROM execution.semantic_pnf_interface
     WHERE region_id = right_row.region_id;
    IF left_interface.interface_id IS NULL
       OR right_interface.interface_id IS NULL THEN
        RAISE EXCEPTION 'adjacent pair members lack closed interfaces';
    END IF;

    SELECT parent_interface.interface_id
      INTO canonical_parent_interface_id
      FROM execution.semantic_pnf_region_edge AS support
      JOIN execution.semantic_pnf_interface AS parent_interface
        ON parent_interface.region_id = support.target_region_id
     WHERE support.source_region_id = pair_row.region_id
       AND support.edge_kind = 5
     LIMIT 1;

    SELECT sum(interface.node_count) AS node_count,
           sum(interface.edge_count) + 1 AS edge_count,
           sum(interface.alternative_count) AS alternative_count,
           sum(interface.unresolved_count) AS unresolved_count,
           sum(interface.boundary_demand_weight) AS boundary_demand_weight,
           sum(interface.encoded_byte_count) AS encoded_byte_count,
           sum(interface.rule_count) + 1 AS rule_count,
           max(interface.closure_rounds) + 1 AS closure_rounds,
           sum(interface.query_cost_ns) AS query_cost_ns,
           sum(interface.hierarchy_cost) + 1 AS hierarchy_cost,
           sum(interface.mdl_cost) + 1 AS mdl_cost
      INTO aggregate
      FROM execution.semantic_pnf_interface AS interface
     WHERE interface.interface_id IN (
         left_interface.interface_id,
         right_interface.interface_id
     );

    next_revision := pair_row.graph_revision + 1;
    pair_digest := digest(
        int8send(pair_row.region_id)
        || int8send(left_interface.interface_id)
        || int8send(right_interface.interface_id)
        || int8send(next_revision),
        'sha256'
    );

    INSERT INTO execution.semantic_pnf_interface
        (interface_digest, region_id, parent_interface_id,
         closure_state, graph_revision,
         node_count, edge_count, alternative_count,
         unresolved_count, boundary_demand_weight,
         encoded_byte_count, rule_count, closure_rounds,
         query_cost_ns, promoted_object_count,
         interface_cardinality, hierarchy_cost, mdl_cost)
    VALUES (
        pair_digest,
        pair_row.region_id,
        canonical_parent_interface_id,
        2,
        next_revision,
        aggregate.node_count,
        aggregate.edge_count,
        aggregate.alternative_count,
        aggregate.unresolved_count,
        aggregate.boundary_demand_weight,
        aggregate.encoded_byte_count,
        aggregate.rule_count,
        aggregate.closure_rounds,
        aggregate.query_cost_ns,
        0,
        0,
        aggregate.hierarchy_cost,
        aggregate.mdl_cost
    )
    ON CONFLICT (region_id) DO UPDATE SET
        interface_digest = EXCLUDED.interface_digest,
        parent_interface_id = EXCLUDED.parent_interface_id,
        closure_state = EXCLUDED.closure_state,
        graph_revision = EXCLUDED.graph_revision,
        node_count = EXCLUDED.node_count,
        edge_count = EXCLUDED.edge_count,
        alternative_count = EXCLUDED.alternative_count,
        unresolved_count = EXCLUDED.unresolved_count,
        boundary_demand_weight = EXCLUDED.boundary_demand_weight,
        encoded_byte_count = EXCLUDED.encoded_byte_count,
        rule_count = EXCLUDED.rule_count,
        closure_rounds = EXCLUDED.closure_rounds,
        query_cost_ns = EXCLUDED.query_cost_ns,
        hierarchy_cost = EXCLUDED.hierarchy_cost,
        mdl_cost = EXCLUDED.mdl_cost
    RETURNING interface_id INTO selected_pair_interface_id;

    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score)
    SELECT selected_pair_interface_id,
           export.export_kind,
           export.target_kind,
           export.target_id,
           export.key_symbol_id,
           export.role_symbol_id,
           export.residual_type_symbol_id,
           min(export.rank),
           max(export.promotion_score)
      FROM execution.semantic_pnf_interface_export AS export
     WHERE export.interface_id IN (
         left_interface.interface_id,
         right_interface.interface_id
     )
     GROUP BY export.export_kind,
              export.target_kind,
              export.target_id,
              export.key_symbol_id,
              export.role_symbol_id,
              export.residual_type_symbol_id
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT selected_pair_interface_id,
           lookup.key_kind,
           lookup.key_a,
           lookup.key_b,
           lookup.target_kind,
           lookup.target_id,
           min(lookup.rank)
      FROM execution.semantic_pnf_interface_lookup AS lookup
     WHERE lookup.interface_id IN (
         left_interface.interface_id,
         right_interface.interface_id
     )
     GROUP BY lookup.key_kind,
              lookup.key_a,
              lookup.key_b,
              lookup.target_kind,
              lookup.target_id
    ON CONFLICT DO NOTHING;

    DELETE FROM execution.semantic_pnf_adjacent_candidate_evidence AS evidence
     WHERE evidence.pair_interface_id = selected_pair_interface_id;

    WITH member AS (
        SELECT left_row.region_id AS region_id,
               left_interface.interface_id AS interface_id,
               left_row.start_char AS start_char,
               left_row.end_char AS end_char
        UNION ALL
        SELECT right_row.region_id,
               right_interface.interface_id,
               right_row.start_char,
               right_row.end_char
    ),
    selected_demand AS (
        SELECT demand.*,
               source.region_id AS source_member_region_id,
               opposite.region_id AS target_member_region_id,
               opposite.interface_id AS opposite_interface_id,
               opposite.start_char AS target_start_char,
               opposite.end_char AS target_end_char
          FROM execution.semantic_pnf_demand AS demand
          JOIN member AS source
            ON source.region_id = demand.source_region_id
          JOIN member AS opposite
            ON opposite.region_id <> source.region_id
         WHERE demand.state IN (1, 2)
           AND demand.source_interface_id IS NOT NULL
    ),
    exact_match AS (
        SELECT demand.demand_id,
               demand.source_member_region_id,
               demand.target_member_region_id,
               demand.opposite_interface_id,
               demand.max_candidates,
               lookup.target_kind,
               lookup.target_id,
               lookup.rank,
               COALESCE(object.promotion_score, factor.support_score, 0)
                   AS candidate_score,
               row_number() OVER (
                   PARTITION BY demand.demand_id,
                                lookup.target_kind,
                                lookup.target_id
                   ORDER BY lookup.rank, lookup.target_id
               ) AS target_occurrence
          FROM selected_demand AS demand
          JOIN execution.semantic_pnf_demand_lookup_key AS demand_key
            ON demand_key.demand_id = demand.demand_id
          JOIN execution.semantic_pnf_interface_lookup AS lookup
            ON lookup.interface_id = demand.opposite_interface_id
           AND lookup.key_kind = demand_key.key_kind
           AND lookup.key_a = demand_key.key_a
           AND lookup.key_b = demand_key.key_b
           AND lookup.target_kind = demand_key.target_kind
          LEFT JOIN execution.semantic_pnf_object AS object
            ON lookup.target_kind = 1
           AND object.object_id = lookup.target_id
          LEFT JOIN execution.semantic_pnf_factor AS factor
            ON lookup.target_kind = 2
           AND factor.factor_id = lookup.target_id
          JOIN execution.semantic_pnf_region AS origin
            ON origin.region_id = COALESCE(
                object.region_id,
                factor.region_id
            )
         WHERE origin.start_char >= demand.target_start_char
           AND origin.end_char <= demand.target_end_char
    ),
    bounded AS (
        SELECT exact.*,
               row_number() OVER (
                   PARTITION BY exact.demand_id
                   ORDER BY exact.rank, exact.target_id
               ) - 1 AS ordinal
          FROM exact_match AS exact
         WHERE exact.target_occurrence = 1
    )
    INSERT INTO execution.semantic_pnf_adjacent_candidate_evidence
        (pair_interface_id, demand_id, target_kind, target_id,
         candidate_interface_id, source_member_region_id,
         target_member_region_id, ordinal, candidate_score)
    SELECT selected_pair_interface_id,
           bounded.demand_id,
           bounded.target_kind,
           bounded.target_id,
           bounded.opposite_interface_id,
           bounded.source_member_region_id,
           bounded.target_member_region_id,
           bounded.ordinal,
           bounded.candidate_score
      FROM bounded
     WHERE bounded.ordinal < bounded.max_candidates
    ON CONFLICT DO NOTHING;

    UPDATE execution.semantic_pnf_interface AS interface
       SET interface_cardinality = counts.total_count,
           promoted_object_count = counts.object_count,
           unresolved_count = counts.demand_count
      FROM (
          SELECT count(*) AS total_count,
                 count(*) FILTER (WHERE target_kind = 1) AS object_count,
                 count(*) FILTER (WHERE target_kind = 3) AS demand_count
            FROM execution.semantic_pnf_interface_export
           WHERE interface_id = selected_pair_interface_id
      ) AS counts
     WHERE interface.interface_id = selected_pair_interface_id;

    PERFORM execution.rebuild_pnf_interface_ancestors(selected_pair_interface_id);

    UPDATE execution.semantic_pnf_region
       SET closure_state = 2,
           graph_revision = next_revision,
           closed_at = CURRENT_TIMESTAMP
     WHERE region_id = pair_row.region_id;

    UPDATE execution.semantic_pnf_work_item
       SET state_id = 3,
           lease_owner = NULL,
           lease_token = NULL,
           lease_expires_at = NULL,
           completed_at = CURRENT_TIMESTAMP
     WHERE work_id = selected_work_id
       AND state_id = 2
       AND lease_token IS NOT DISTINCT FROM selected_lease_token
       AND lease_epoch = selected_lease_epoch;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'adjacent reconciliation work fence changed at commit';
    END IF;

    RETURN selected_pair_interface_id;
END;
$$;

COMMIT;
