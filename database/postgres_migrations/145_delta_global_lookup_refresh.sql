BEGIN;

-- 145: publish only interfaces changed after the hierarchy-wide lookup refresh.
--
-- The hierarchy phase performs the first authoritative full global lookup
-- publication because that boundary also drives ordinary demand planning.
-- Paragraph adjacency runs afterwards and returns the exact pair interface ids
-- it creates or updates.  Rebuilding the entire document lookup after that is
-- unnecessary: the global lookup is a direct projection of
-- semantic_pnf_interface_lookup for those changed interfaces.
--
-- The function returns the NET row-count change, not the number inserted.  The
-- caller can therefore preserve the exact total-row receipt as
--
--     hierarchy_total + refresh_delta
--
-- even when a recovered/replayed pair interface already had published rows.
CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup_interfaces(
    selected_run_ref TEXT,
    selected_document_ref TEXT,
    selected_interface_ids BIGINT[]
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count BIGINT := 0;
    inserted_count BIGINT := 0;
BEGIN
    IF selected_interface_ids IS NULL
       OR cardinality(selected_interface_ids) = 0 THEN
        RETURN 0;
    END IF;

    -- Ignore foreign/stale ids rather than allowing a caller to delete another
    -- document's projection.  The selected relation is the exact certificate
    -- consumed by both DELETE and INSERT below.
    WITH selected AS (
        SELECT DISTINCT interface.interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE interface.interface_id = ANY(selected_interface_ids)
           AND region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
    )
    DELETE FROM execution.semantic_pnf_global_lookup AS global
    USING selected
    WHERE global.interface_id = selected.interface_id
      AND global.run_ref = selected_run_ref
      AND global.document_ref = selected_document_ref;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    WITH selected AS (
        SELECT DISTINCT interface.interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE interface.interface_id = ANY(selected_interface_ids)
           AND region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND interface.closure_state IN (2, 3)
    )
    INSERT INTO execution.semantic_pnf_global_lookup
        (run_ref, document_ref, interface_id, region_id, region_kind,
         region_start_char, region_end_char,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT region.run_ref,
           region.document_ref,
           lookup.interface_id,
           region.region_id,
           region.region_kind,
           region.start_char,
           region.end_char,
           lookup.key_kind,
           lookup.key_a,
           lookup.key_b,
           lookup.target_kind,
           lookup.target_id,
           lookup.rank
      FROM selected
      JOIN execution.semantic_pnf_interface_lookup AS lookup
        ON lookup.interface_id = selected.interface_id
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = selected.interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    RETURN inserted_count - deleted_count;
END;
$$;

COMMIT;
