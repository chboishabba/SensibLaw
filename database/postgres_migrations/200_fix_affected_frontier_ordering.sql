BEGIN;

-- Migration 197/199 used SELECT DISTINCT while ordering by an expression that
-- was not part of the select list. PostgreSQL correctly rejects that query at
-- runtime. Keep the affected-key carrier and bottom-up ordering unchanged,
-- but project the span length as the explicit ordering coordinate.
CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_document_frontiers(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected RECORD;
    reduced_count BIGINT := 0;
    selected_run_id BIGINT;
    selected_document_id BIGINT;
    started_at TIMESTAMPTZ := clock_timestamp();
BEGIN
    SELECT run_id INTO selected_run_id
      FROM execution.semantic_pnf_run_identity
     WHERE run_ref = selected_run_ref;
    SELECT document_id INTO selected_document_id
      FROM execution.semantic_pnf_document_identity
     WHERE document_ref = selected_document_ref;

    FOR selected IN
        WITH RECURSIVE eligible AS (
            SELECT interface.interface_id,
                   interface.parent_interface_id,
                   interface.graph_revision,
                   region.region_kind,
                   region.start_char,
                   region.end_char,
                   region.sequence_no,
                   receipt.graph_revision AS receipt_graph_revision,
                   receipt.reduced_at
              FROM execution.semantic_pnf_interface AS interface
              JOIN execution.semantic_pnf_region AS region
                ON region.region_id = interface.region_id
              LEFT JOIN execution.semantic_pnf_frontier_reduction_receipt AS receipt
                ON receipt.interface_id = interface.interface_id
             WHERE region.run_ref = selected_run_ref
               AND region.document_ref = selected_document_ref
               AND region.region_kind NOT IN (1, 2, 4, 9)
               AND interface.closure_state IN (2, 3)
        ),
        dirty AS (
            SELECT candidate.interface_id
              FROM eligible AS candidate
             WHERE candidate.reduced_at IS NULL
                OR candidate.receipt_graph_revision IS DISTINCT FROM
                   candidate.graph_revision
                OR EXISTS (
                    SELECT 1
                      FROM execution.semantic_pnf_region AS child_region
                      JOIN execution.semantic_pnf_interface AS child_interface
                        ON child_interface.region_id = child_region.region_id
                     WHERE child_interface.parent_interface_id = candidate.interface_id
                       AND child_region.region_kind NOT IN (2, 4, 9)
                       AND child_region.closed_at IS NOT NULL
                       AND child_region.closed_at > candidate.reduced_at
                )
                OR EXISTS (
                    SELECT 1
                      FROM execution.semantic_pnf_interface AS child_interface
                      JOIN execution.semantic_pnf_region AS child_region
                        ON child_region.region_id = child_interface.region_id
                      JOIN execution.semantic_pnf_frontier_reduction_receipt AS child_receipt
                        ON child_receipt.interface_id = child_interface.interface_id
                     WHERE child_interface.parent_interface_id = candidate.interface_id
                       AND child_region.region_kind NOT IN (2, 4, 9)
                       AND child_receipt.reduced_at > candidate.reduced_at
                )
        ),
        affected(interface_id) AS (
            SELECT dirty.interface_id
              FROM dirty
            UNION
            SELECT parent.interface_id
              FROM affected
              JOIN execution.semantic_pnf_interface AS child
                ON child.interface_id = affected.interface_id
              JOIN eligible AS parent
                ON parent.interface_id = child.parent_interface_id
        )
        SELECT DISTINCT candidate.interface_id,
               candidate.region_kind,
               candidate.start_char,
               candidate.end_char,
               candidate.end_char - candidate.start_char AS span_length,
               candidate.sequence_no
          FROM affected
          JOIN eligible AS candidate
            ON candidate.interface_id = affected.interface_id
         ORDER BY candidate.region_kind,
                  span_length,
                  candidate.sequence_no,
                  candidate.interface_id
    LOOP
        PERFORM *
          FROM execution.rebuild_numeric_pnf_parent_frontier(
              selected.interface_id
          );
        reduced_count := reduced_count + 1;
    END LOOP;

    INSERT INTO execution.semantic_pnf_frontier_stage_receipt
        (run_id, document_id, stage_name, row_count, elapsed_ms)
    VALUES (
        selected_run_id,
        selected_document_id,
        'sparse_frontier_reduction',
        reduced_count,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (run_id, document_id, stage_name) DO UPDATE SET
        row_count = EXCLUDED.row_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        completed_at = CURRENT_TIMESTAMP;

    RETURN reduced_count;
END;
$$;

COMMENT ON FUNCTION execution.reduce_numeric_pnf_document_frontiers(TEXT, TEXT) IS
    'Delta-fed canonical frontier coordinator with explicit span-length ordering; excludes overlapping adjacent evidence fibres (kinds 2/4) from dirty seeding, upward closure, and parent reduction.';

COMMIT;
