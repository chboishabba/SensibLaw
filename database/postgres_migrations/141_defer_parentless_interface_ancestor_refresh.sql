BEGIN;

-- 141: consumer-sufficient ancestor maintenance.
--
-- Sentence interfaces are closed before their paragraph/adaptive/document
-- parent interfaces exist.  The old implementation deleted both ancestor
-- tables and only then discovered parent_interface_id IS NULL.  That work is
-- semantically inert: no ancestor carrier can be constructed until the parent
-- interface exists, and materialize_numeric_document_hierarchy later performs
-- the authoritative document-wide rebuild after parent assignment.
--
-- Read the only prerequisite first.  Parentless interfaces now pay one indexed
-- parent lookup and zero ancestor-table writes.  Parented interfaces preserve
-- the exact binary-lifting and typed-nearest-ancestor construction.
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
    SELECT parent_interface_id
      INTO parent_id
      FROM execution.semantic_pnf_interface
     WHERE interface_id = selected_interface_id;

    IF parent_id IS NULL THEN
        RETURN;
    END IF;

    DELETE FROM execution.semantic_pnf_interface_ancestor
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_interface_typed_ancestor
     WHERE interface_id = selected_interface_id;

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

COMMIT;
