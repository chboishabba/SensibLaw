BEGIN;

-- C1: hierarchy construction closes many non-sentence interfaces inside one
-- transaction.  Their semantic frontier must still be rebuilt by the existing
-- canonical reducer, but rebuilding once per closure creates avoidable repeated
-- publication work.  A transaction-local flag lets the hierarchy planner defer
-- only non-sentence trigger reductions while preserving immediate sentence
-- closure semantics.
CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_interface_on_close()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_interface_id BIGINT;
    defer_frontier_rebuild BOOLEAN := FALSE;
BEGIN
    IF NEW.closure_state NOT IN (2, 3)
       OR OLD.closure_state IS NOT DISTINCT FROM NEW.closure_state THEN
        RETURN NEW;
    END IF;

    defer_frontier_rebuild := COALESCE(
        current_setting('sensiblaw.defer_frontier_rebuild', true),
        'off'
    ) = 'on';

    -- Sentence closure remains immediate.  Only hierarchy fibres may be
    -- deferred, and only when the current transaction opted in explicitly.
    IF NEW.region_kind <> 1 AND defer_frontier_rebuild THEN
        RETURN NEW;
    END IF;

    SELECT interface_id
      INTO selected_interface_id
      FROM execution.semantic_pnf_interface
     WHERE region_id = NEW.region_id;

    IF selected_interface_id IS NOT NULL THEN
        PERFORM *
          FROM execution.rebuild_numeric_pnf_parent_frontier(
              selected_interface_id
          );
    END IF;
    RETURN NEW;
END;
$$;

-- Re-running the document reducer in the same graph revision is now cheap and
-- idempotent.  The reduction receipt is the durable witness that this exact
-- interface revision has already passed through the canonical parent reducer.
-- This permits a two-phase hierarchy build: paragraphs are reduced before MDL
-- segmentation, then only newly-created adaptive/document interfaces are
-- reduced before publication.
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
        SELECT interface.interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND region.region_kind <> 1
           AND region.region_kind <> 9
           AND interface.closure_state IN (2, 3)
           AND NOT EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_frontier_reduction_receipt AS receipt
                WHERE receipt.interface_id = interface.interface_id
                  AND receipt.graph_revision = interface.graph_revision
           )
         ORDER BY region.region_kind,
                  (region.end_char - region.start_char),
                  region.sequence_no,
                  interface.interface_id
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

COMMIT;
