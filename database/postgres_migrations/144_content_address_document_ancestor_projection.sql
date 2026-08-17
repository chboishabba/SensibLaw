BEGIN;

-- 144: make the derived document ancestor projection physically idempotent.
--
-- Document closure already triggers a full ancestor rebuild (migration 043),
-- while the current numeric hierarchy planner also requests the same rebuild
-- immediately afterwards.  Keep both semantic call boundaries: generic callers
-- may rely on the trigger, and the planner may explicitly demand the projection.
-- Avoid repeating the recursive work when the source parent relation is exact.
--
-- The fingerprint is execution-local cache state only.  It uses DB-local
-- interface ids because it never participates in portable semantic identity.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_document_ancestor_projection_state (
    run_ref TEXT NOT NULL,
    document_ref TEXT NOT NULL,
    parent_relation_sha256 BYTEA NOT NULL CHECK (octet_length(parent_relation_sha256) = 32),
    interface_count BIGINT NOT NULL CHECK (interface_count >= 0),
    rebuilt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_ref, document_ref)
);

CREATE OR REPLACE FUNCTION execution.rebuild_pnf_document_ancestors(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    rebuilt_count BIGINT := 0;
    current_parent_digest BYTEA;
    previous_parent_digest BYTEA;
    previous_interface_count BIGINT;
BEGIN
    -- Ordered decimal integer pairs with ':' and ',' separators are injective
    -- for positive interface ids and the '-' NULL sentinel.  The digest is only
    -- an execution freshness key; semantic receipts never consume it.
    SELECT digest(
               convert_to(
                   COALESCE(
                       string_agg(
                           interface.interface_id::TEXT || ':' ||
                           COALESCE(interface.parent_interface_id::TEXT, '-'),
                           ',' ORDER BY interface.interface_id
                       ),
                       ''
                   ),
                   'UTF8'
               ),
               'sha256'
           ),
           count(*)
      INTO current_parent_digest, rebuilt_count
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE region.run_ref = selected_run_ref
       AND region.document_ref = selected_document_ref;

    SELECT state.parent_relation_sha256,
           state.interface_count
      INTO previous_parent_digest,
           previous_interface_count
      FROM execution.semantic_pnf_document_ancestor_projection_state AS state
     WHERE state.run_ref = selected_run_ref
       AND state.document_ref = selected_document_ref;

    IF previous_parent_digest = current_parent_digest
       AND previous_interface_count = rebuilt_count THEN
        RETURN rebuilt_count;
    END IF;

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

    INSERT INTO execution.semantic_pnf_document_ancestor_projection_state
        (run_ref, document_ref, parent_relation_sha256,
         interface_count, rebuilt_at)
    VALUES (
        selected_run_ref,
        selected_document_ref,
        current_parent_digest,
        rebuilt_count,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (run_ref, document_ref) DO UPDATE SET
        parent_relation_sha256 = EXCLUDED.parent_relation_sha256,
        interface_count = EXCLUDED.interface_count,
        rebuilt_at = EXCLUDED.rebuilt_at;

    RETURN rebuilt_count;
END;
$$;

COMMIT;
