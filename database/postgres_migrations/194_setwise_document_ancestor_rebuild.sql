BEGIN;

-- Hierarchy publication is document-scoped.  The historical implementation
-- deleted document ancestor state and then called rebuild_pnf_interface_ancestors
-- once per interface.  That repeated recursive/iterative work even though the
-- complete parent relation is already available in one transaction.
--
-- Preserve the exact authority surfaces:
--   semantic_pnf_interface_ancestor       = power-of-two binary lifting
--   semantic_pnf_interface_typed_ancestor = nearest ancestor per region kind
-- while rebuilding both from one recursive document relation.
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

    CREATE TEMP TABLE IF NOT EXISTS pg_temp.pnf_document_ancestor_chain (
        interface_id BIGINT NOT NULL,
        ancestor_interface_id BIGINT NOT NULL,
        distance BIGINT NOT NULL,
        ancestor_region_kind SMALLINT NOT NULL,
        PRIMARY KEY (interface_id, ancestor_interface_id)
    ) ON COMMIT DROP;
    TRUNCATE pg_temp.pnf_document_ancestor_chain;

    INSERT INTO pg_temp.pnf_document_ancestor_chain (
        interface_id,
        ancestor_interface_id,
        distance,
        ancestor_region_kind
    )
    WITH RECURSIVE document_interfaces AS (
        SELECT interface.interface_id,
               interface.parent_interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
    ),
    chain(interface_id, ancestor_interface_id, distance) AS (
        SELECT child.interface_id,
               child.parent_interface_id,
               1::BIGINT
          FROM document_interfaces AS child
         WHERE child.parent_interface_id IS NOT NULL
        UNION ALL
        SELECT chain.interface_id,
               parent.parent_interface_id,
               chain.distance + 1
          FROM chain
          JOIN document_interfaces AS parent
            ON parent.interface_id = chain.ancestor_interface_id
         WHERE parent.parent_interface_id IS NOT NULL
    )
    SELECT chain.interface_id,
           chain.ancestor_interface_id,
           chain.distance,
           region.region_kind
      FROM chain
      JOIN execution.semantic_pnf_interface AS ancestor_interface
        ON ancestor_interface.interface_id = chain.ancestor_interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = ancestor_interface.region_id;

    INSERT INTO execution.semantic_pnf_interface_ancestor (
        interface_id,
        distance_power,
        ancestor_interface_id,
        distance
    )
    SELECT chain.interface_id,
           CASE chain.distance
               WHEN 1 THEN 0
               WHEN 2 THEN 1
               WHEN 4 THEN 2
               WHEN 8 THEN 3
               WHEN 16 THEN 4
               WHEN 32 THEN 5
               WHEN 64 THEN 6
               WHEN 128 THEN 7
               WHEN 256 THEN 8
               WHEN 512 THEN 9
               WHEN 1024 THEN 10
               WHEN 2048 THEN 11
               WHEN 4096 THEN 12
               WHEN 8192 THEN 13
               WHEN 16384 THEN 14
               WHEN 32768 THEN 15
               WHEN 65536 THEN 16
               WHEN 131072 THEN 17
               WHEN 262144 THEN 18
               WHEN 524288 THEN 19
               WHEN 1048576 THEN 20
               WHEN 2097152 THEN 21
               WHEN 4194304 THEN 22
               WHEN 8388608 THEN 23
               WHEN 16777216 THEN 24
               WHEN 33554432 THEN 25
               WHEN 67108864 THEN 26
               WHEN 134217728 THEN 27
               WHEN 268435456 THEN 28
               WHEN 536870912 THEN 29
               WHEN 1073741824 THEN 30
               WHEN 2147483648 THEN 31
               WHEN 4294967296 THEN 32
               WHEN 8589934592 THEN 33
               WHEN 17179869184 THEN 34
               WHEN 34359738368 THEN 35
               WHEN 68719476736 THEN 36
               WHEN 137438953472 THEN 37
               WHEN 274877906944 THEN 38
               WHEN 549755813888 THEN 39
               WHEN 1099511627776 THEN 40
               WHEN 2199023255552 THEN 41
               WHEN 4398046511104 THEN 42
               WHEN 8796093022208 THEN 43
               WHEN 17592186044416 THEN 44
               WHEN 35184372088832 THEN 45
               WHEN 70368744177664 THEN 46
               WHEN 140737488355328 THEN 47
               WHEN 281474976710656 THEN 48
               WHEN 562949953421312 THEN 49
               WHEN 1125899906842624 THEN 50
               WHEN 2251799813685248 THEN 51
               WHEN 4503599627370496 THEN 52
               WHEN 9007199254740992 THEN 53
               WHEN 18014398509481984 THEN 54
               WHEN 36028797018963968 THEN 55
               WHEN 72057594037927936 THEN 56
               WHEN 144115188075855872 THEN 57
               WHEN 288230376151711744 THEN 58
               WHEN 576460752303423488 THEN 59
               WHEN 1152921504606846976 THEN 60
               WHEN 2305843009213693952 THEN 61
               WHEN 4611686018427387904 THEN 62
           END::SMALLINT,
           chain.ancestor_interface_id,
           chain.distance
      FROM pg_temp.pnf_document_ancestor_chain AS chain
     WHERE chain.distance > 0
       AND (chain.distance & (chain.distance - 1)) = 0;

    INSERT INTO execution.semantic_pnf_interface_typed_ancestor (
        interface_id,
        ancestor_region_kind,
        ancestor_interface_id,
        distance
    )
    SELECT DISTINCT ON (chain.interface_id, chain.ancestor_region_kind)
           chain.interface_id,
           chain.ancestor_region_kind,
           chain.ancestor_interface_id,
           chain.distance
      FROM pg_temp.pnf_document_ancestor_chain AS chain
     ORDER BY chain.interface_id,
              chain.ancestor_region_kind,
              chain.distance,
              chain.ancestor_interface_id;

    SELECT count(*)
      INTO rebuilt_count
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE region.run_ref = selected_run_ref
       AND region.document_ref = selected_document_ref;

    RETURN rebuilt_count;
END;
$$;

COMMENT ON FUNCTION execution.rebuild_pnf_document_ancestors(TEXT, TEXT) IS
    'Set-wise document hierarchy publication: one recursive ancestor relation feeds exact power-of-two and nearest-typed ancestor authority; replaces per-interface procedural rebuild without changing semantic coordinates.';

COMMIT;
