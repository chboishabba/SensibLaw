BEGIN;

-- 143: do not maintain an ancestor projection before its hierarchy consumer
-- exists.
--
-- During hierarchy construction _close_parent_interface() assigns paragraph and
-- adaptive parents and calls rebuild_pnf_interface_ancestors() for the affected
-- interfaces.  No hierarchy consumer reads those intermediate ancestor rows.
-- The document-close trigger (migration 043) rebuilds the complete projection
-- after the document region becomes CLOSED, and migration 142 makes that final
-- projection set-wise.
--
-- Adjacent pair interfaces created *after* document closure still require their
-- targeted ancestor projection immediately, so the fast path is conditional on
-- document closure rather than on region kind.
CREATE OR REPLACE FUNCTION execution.rebuild_pnf_interface_ancestors(
    selected_interface_id BIGINT
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    parent_id BIGINT;
    selected_run_ref TEXT;
    selected_document_ref TEXT;
    document_is_closed BOOLEAN := FALSE;
    previous_ancestor BIGINT;
    next_ancestor BIGINT;
    power SMALLINT;
    distance_value BIGINT;
BEGIN
    SELECT interface.parent_interface_id,
           region.run_ref,
           region.document_ref
      INTO parent_id, selected_run_ref, selected_document_ref
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE interface.interface_id = selected_interface_id;

    IF parent_id IS NULL THEN
        RETURN;
    END IF;

    SELECT EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_region AS document_region
         WHERE document_region.run_ref = selected_run_ref
           AND document_region.document_ref = selected_document_ref
           AND document_region.region_kind = 10
           AND document_region.closure_state = 3
    ) INTO document_is_closed;

    -- Parent assignment is still in flux.  The document-close projection is the
    -- first consumer-safe point at which these rows become authoritative.
    IF NOT document_is_closed THEN
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
