BEGIN;

-- 142: the document ancestor carrier is a pure projection of parent_interface_id.
--
-- Migration 043 rebuilt it by deleting the whole document projection and then
-- looping over every interface through rebuild_pnf_interface_ancestors().  Each
-- per-interface call repeated DELETE work against tables that had just been
-- cleared, and binary lifting was materialized one interface at a time.
--
-- Compute the transitive parent chain once per projection.  Powers-of-two
-- distances are exactly the binary-lifting carrier; the nearest ancestor of each
-- region kind is exactly the typed-ancestor carrier.  No semantic source table
-- or receipt changes.
CREATE OR REPLACE FUNCTION execution.rebuild_pnf_document_ancestors(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    rebuilt_count BIGINT := 0;
BEGIN
    -- Preserve the previous return contract: count hierarchy interfaces
    -- reachable from document roots, including the roots themselves.
    WITH RECURSIVE hierarchy(interface_id) AS (
        SELECT interface.interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND interface.parent_interface_id IS NULL
        UNION ALL
        SELECT child.interface_id
          FROM hierarchy
          JOIN execution.semantic_pnf_interface AS child
            ON child.parent_interface_id = hierarchy.interface_id
    )
    SELECT count(*) INTO rebuilt_count FROM hierarchy;

    DELETE FROM execution.semantic_pnf_interface_ancestor AS ancestor
    USING execution.semantic_pnf_interface AS interface,
          execution.semantic_pnf_region AS region
    WHERE ancestor.interface_id = interface.interface_id
      AND interface.region_id = region.region_id
      AND region.run_ref = selected_run_ref
      AND region.document_ref = selected_document_ref;

    DELETE FROM execution.semantic_pnf_interface_typed_ancestor AS ancestor
    USING execution.semantic_pnf_interface AS interface,
          execution.semantic_pnf_region AS region
    WHERE ancestor.interface_id = interface.interface_id
      AND interface.region_id = region.region_id
      AND region.run_ref = selected_run_ref
      AND region.document_ref = selected_document_ref;

    WITH RECURSIVE chain(
        descendant_interface_id,
        ancestor_interface_id,
        distance
    ) AS (
        SELECT child.interface_id,
               child.parent_interface_id,
               1::BIGINT
          FROM execution.semantic_pnf_interface AS child
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = child.region_id
         WHERE region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND child.parent_interface_id IS NOT NULL
        UNION ALL
        SELECT chain.descendant_interface_id,
               parent.parent_interface_id,
               chain.distance + 1
          FROM chain
          JOIN execution.semantic_pnf_interface AS parent
            ON parent.interface_id = chain.ancestor_interface_id
         WHERE parent.parent_interface_id IS NOT NULL
    )
    INSERT INTO execution.semantic_pnf_interface_ancestor
        (interface_id, distance_power, ancestor_interface_id, distance)
    SELECT chain.descendant_interface_id,
           power.distance_power::SMALLINT,
           chain.ancestor_interface_id,
           chain.distance
      FROM chain
      JOIN generate_series(0, 62) AS power(distance_power)
        ON chain.distance = (1::BIGINT << power.distance_power)
    ON CONFLICT (interface_id, distance_power) DO UPDATE SET
        ancestor_interface_id = EXCLUDED.ancestor_interface_id,
        distance = EXCLUDED.distance;

    WITH RECURSIVE chain(
        descendant_interface_id,
        ancestor_interface_id,
        distance
    ) AS (
        SELECT child.interface_id,
               child.parent_interface_id,
               1::BIGINT
          FROM execution.semantic_pnf_interface AS child
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = child.region_id
         WHERE region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND child.parent_interface_id IS NOT NULL
        UNION ALL
        SELECT chain.descendant_interface_id,
               parent.parent_interface_id,
               chain.distance + 1
          FROM chain
          JOIN execution.semantic_pnf_interface AS parent
            ON parent.interface_id = chain.ancestor_interface_id
         WHERE parent.parent_interface_id IS NOT NULL
    ),
    typed AS (
        SELECT DISTINCT ON (
                   chain.descendant_interface_id,
                   ancestor_region.region_kind
               )
               chain.descendant_interface_id,
               ancestor_region.region_kind,
               chain.ancestor_interface_id,
               chain.distance
          FROM chain
          JOIN execution.semantic_pnf_interface AS ancestor_interface
            ON ancestor_interface.interface_id = chain.ancestor_interface_id
          JOIN execution.semantic_pnf_region AS ancestor_region
            ON ancestor_region.region_id = ancestor_interface.region_id
         ORDER BY chain.descendant_interface_id,
                  ancestor_region.region_kind,
                  chain.distance,
                  chain.ancestor_interface_id
    )
    INSERT INTO execution.semantic_pnf_interface_typed_ancestor
        (interface_id, ancestor_region_kind, ancestor_interface_id, distance)
    SELECT descendant_interface_id,
           region_kind,
           ancestor_interface_id,
           distance
      FROM typed
    ON CONFLICT (interface_id, ancestor_region_kind) DO UPDATE SET
        ancestor_interface_id = EXCLUDED.ancestor_interface_id,
        distance = EXCLUDED.distance;

    RETURN rebuilt_count;
END;
$$;

COMMIT;
