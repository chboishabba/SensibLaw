BEGIN;

-- Hierarchy materialization runs under the existing transaction-local
-- sensiblaw.defer_frontier_rebuild=on publication boundary.  During that
-- transaction _close_parent_interface() and supported-pair binding can call this
-- reducer many times even though migration 142 publishes the complete document
-- ancestor projections set-wise at the end of hierarchy materialization.
--
-- Skip only those intermediate derived-projection rebuilds.  Ordinary callers
-- outside the deferred hierarchy transaction retain the historical exact
-- per-interface behavior.
CREATE OR REPLACE FUNCTION execution.rebuild_pnf_interface_ancestors(
    selected_interface_id BIGINT
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    parent_id BIGINT;
    previous_ancestor BIGINT;
    next_ancestor BIGINT;
    power SMALLINT;
    distance_value BIGINT;
BEGIN
    IF current_setting('sensiblaw.defer_frontier_rebuild', true) = 'on' THEN
        RETURN;
    END IF;

    DELETE FROM execution.semantic_pnf_interface_ancestor
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_interface_typed_ancestor
     WHERE interface_id = selected_interface_id;

    SELECT parent_interface_id
      INTO parent_id
      FROM execution.semantic_pnf_interface
     WHERE interface_id = selected_interface_id;

    IF parent_id IS NULL THEN
        RETURN;
    END IF;

    INSERT INTO execution.semantic_pnf_interface_ancestor
        (interface_id, distance_power, ancestor_interface_id, distance)
    VALUES (selected_interface_id, 0, parent_id, 1);

    previous_ancestor := parent_id;
    distance_value := 2;
    FOR power IN 1..62 LOOP
        SELECT ancestor_interface_id
          INTO next_ancestor
          FROM execution.semantic_pnf_interface_ancestor
         WHERE interface_id = previous_ancestor
           AND distance_power = power - 1;
        IF next_ancestor IS NULL THEN
            EXIT;
        END IF;
        INSERT INTO execution.semantic_pnf_interface_ancestor
            (interface_id, distance_power, ancestor_interface_id, distance)
        VALUES (
            selected_interface_id,
            power,
            next_ancestor,
            distance_value
        )
        ON CONFLICT (interface_id, distance_power) DO UPDATE SET
            ancestor_interface_id = EXCLUDED.ancestor_interface_id,
            distance = EXCLUDED.distance;
        previous_ancestor := next_ancestor;
        distance_value := distance_value * 2;
    END LOOP;

    WITH RECURSIVE chain(interface_id, distance) AS (
        SELECT parent_id, 1::BIGINT
        UNION ALL
        SELECT parent.parent_interface_id, chain.distance + 1
          FROM chain
          JOIN execution.semantic_pnf_interface AS parent
            ON parent.interface_id = chain.interface_id
         WHERE parent.parent_interface_id IS NOT NULL
    ),
    typed AS (
        SELECT DISTINCT ON (region.region_kind)
               region.region_kind,
               chain.interface_id,
               chain.distance
          FROM chain
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.interface_id = chain.interface_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         ORDER BY region.region_kind, chain.distance
    )
    INSERT INTO execution.semantic_pnf_interface_typed_ancestor
        (interface_id, ancestor_region_kind, ancestor_interface_id, distance)
    SELECT selected_interface_id, region_kind, interface_id, distance
      FROM typed
    ON CONFLICT (interface_id, ancestor_region_kind) DO UPDATE SET
        ancestor_interface_id = EXCLUDED.ancestor_interface_id,
        distance = EXCLUDED.distance;
END;
$$;

COMMENT ON FUNCTION execution.rebuild_pnf_interface_ancestors(BIGINT) IS
    'Exact per-interface ancestor reducer; deferred hierarchy publication skips intermediate rebuilds because migration 142 publishes the complete document ancestor projections set-wise at the transaction end.';

COMMIT;
