BEGIN;

-- Existing databases may contain closed structural kinds that predate the
-- sparse closure trigger.  Reconciliation fibres (kind 9) remain parentless
-- evidence lanes; every other non-sentence closed region is reduced in strict
-- bottom-up region-kind order before the root projection is published.
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

-- Migration 047 installed a row trigger that queried the object table and
-- inserted one object-kind lookup row for every exported object.  Replace it
-- with one transition-table insert per export statement.  This matters for
-- sentence-local closure, even though parent frontiers are now sparse.
DROP TRIGGER IF EXISTS semantic_pnf_object_export_kind_index
    ON execution.semantic_pnf_interface_export;

CREATE OR REPLACE FUNCTION execution.index_numeric_pnf_object_exports_batch()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT export.interface_id,
           2,
           object.object_kind_symbol_id,
           0,
           1,
           object.object_id,
           export.rank
      FROM inserted_export AS export
      JOIN execution.semantic_pnf_object AS object
        ON export.target_kind = 1
       AND object.object_id = export.target_id
    ON CONFLICT DO NOTHING;
    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_object_export_kind_index_batch
AFTER INSERT ON execution.semantic_pnf_interface_export
REFERENCING NEW TABLE AS inserted_export
FOR EACH STATEMENT
EXECUTE FUNCTION execution.index_numeric_pnf_object_exports_batch();

COMMIT;
