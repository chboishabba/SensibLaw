BEGIN;

-- 145: make the current sparse-frontier architecture physically sparse as well.
--
-- The semantic authority after migrations 062/068/071 is the canonical
-- parent_region_id hierarchy plus a root-only visible/global projection.
-- Adjacent sentence/paragraph fibres (kinds 2/4) and reconciliation fibres
-- (kind 9) are overlapping residual/evidence carriers, not canonical parents.
-- They must therefore never be reduced with the canonical parent reducer.
--
-- Canonical region closure already invokes rebuild_numeric_pnf_parent_frontier.
-- The compatibility document reducer historically rebuilt every closed parent
-- again before root publication. Replace that safety sweep with a durable
-- dirty set. Missing/stale reduction receipts seed the set for upgraded or
-- interrupted databases; canonical recomputation dirties only its canonical
-- parent, yielding a bottom-up dependency closure rather than a document scan.

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_frontier_dirty (
    interface_id BIGINT PRIMARY KEY
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE CASCADE,
    reason_interface_id BIGINT
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE SET NULL,
    dirty_reason TEXT NOT NULL,
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS semantic_pnf_frontier_dirty_reason_idx
    ON execution.semantic_pnf_frontier_dirty
       (reason_interface_id, interface_id);

-- Preserve the exact reducer installed by 062 as the semantic kernel. The new
-- public wrapper adds only dependency bookkeeping around that kernel.
ALTER FUNCTION execution.rebuild_numeric_pnf_parent_frontier(BIGINT)
    RENAME TO rebuild_numeric_pnf_parent_frontier_canonical;

CREATE OR REPLACE FUNCTION execution.enqueue_numeric_pnf_parent_frontier(
    selected_interface_id BIGINT,
    selected_reason TEXT DEFAULT 'child_frontier_changed'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_parent_interface_id BIGINT;
BEGIN
    SELECT interface.parent_interface_id
      INTO selected_parent_interface_id
      FROM execution.semantic_pnf_interface AS interface
     WHERE interface.interface_id = selected_interface_id;

    IF selected_parent_interface_id IS NULL THEN
        RETURN 0;
    END IF;

    INSERT INTO execution.semantic_pnf_frontier_dirty
        (interface_id, reason_interface_id, dirty_reason, enqueued_at)
    VALUES (
        selected_parent_interface_id,
        selected_interface_id,
        selected_reason,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (interface_id) DO UPDATE SET
        reason_interface_id = EXCLUDED.reason_interface_id,
        dirty_reason = EXCLUDED.dirty_reason,
        enqueued_at = LEAST(
            execution.semantic_pnf_frontier_dirty.enqueued_at,
            EXCLUDED.enqueued_at
        );

    RETURN 1;
END;
$$;

CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier(
    selected_interface_id BIGINT
)
RETURNS TABLE (
    output_export_count BIGINT,
    unresolved_demand_count BIGINT,
    resolved_demand_count BIGINT,
    actor_profile_count BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_kind SMALLINT;
BEGIN
    SELECT region.region_kind
      INTO selected_kind
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE interface.interface_id = selected_interface_id;

    IF selected_kind IS NULL THEN
        RAISE EXCEPTION 'numeric PNF interface % disappeared', selected_interface_id;
    END IF;

    IF selected_kind IN (2, 4, 9) THEN
        RAISE EXCEPTION
            'overlapping/evidence interface % kind % cannot use canonical parent reduction',
            selected_interface_id,
            selected_kind;
    END IF;

    RETURN QUERY
    SELECT *
      FROM execution.rebuild_numeric_pnf_parent_frontier_canonical(
          selected_interface_id
      );

    PERFORM execution.enqueue_numeric_pnf_parent_frontier(
        selected_interface_id,
        'canonical_child_frontier_changed'
    );
END;
$$;

-- Closure semantics now respect the topology explicitly. Overlapping fibres
-- retain the interface/evidence constructed by their own executor; they do not
-- masquerade as empty canonical parents merely because they are parentless in
-- the containment spine.
CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_interface_on_close()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_interface_id BIGINT;
BEGIN
    IF NEW.closure_state NOT IN (2, 3)
       OR OLD.closure_state IS NOT DISTINCT FROM NEW.closure_state THEN
        RETURN NEW;
    END IF;

    SELECT interface_id
      INTO selected_interface_id
      FROM execution.semantic_pnf_interface
     WHERE region_id = NEW.region_id;

    IF selected_interface_id IS NULL THEN
        RETURN NEW;
    END IF;

    IF NEW.region_kind IN (2, 4, 9) THEN
        RETURN NEW;
    END IF;

    PERFORM *
      FROM execution.rebuild_numeric_pnf_parent_frontier(
          selected_interface_id
      );
    RETURN NEW;
END;
$$;

-- Replace the complete compatibility sweep with an exact dirty/stale closure.
CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_document_frontiers(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_interface_id BIGINT;
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

    -- Recovery/backfill seed. Fresh canonical closures already have a receipt,
    -- so they are not revisited merely because root publication was requested.
    INSERT INTO execution.semantic_pnf_frontier_dirty
        (interface_id, reason_interface_id, dirty_reason)
    SELECT interface.interface_id,
           NULL,
           CASE
               WHEN receipt.interface_id IS NULL THEN 'missing_reduction_receipt'
               ELSE 'stale_graph_revision'
           END
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
      LEFT JOIN execution.semantic_pnf_frontier_reduction_receipt AS receipt
        ON receipt.interface_id = interface.interface_id
     WHERE region.run_ref = selected_run_ref
       AND region.document_ref = selected_document_ref
       AND region.region_kind NOT IN (1, 2, 4, 9)
       AND interface.closure_state IN (2, 3)
       AND (
           receipt.interface_id IS NULL
           OR receipt.graph_revision IS DISTINCT FROM interface.graph_revision
       )
    ON CONFLICT (interface_id) DO NOTHING;

    LOOP
        selected_interface_id := NULL;
        SELECT dirty.interface_id
          INTO selected_interface_id
          FROM execution.semantic_pnf_frontier_dirty AS dirty
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.interface_id = dirty.interface_id
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND region.region_kind NOT IN (1, 2, 4, 9)
           AND interface.closure_state IN (2, 3)
         ORDER BY region.region_kind,
                  (region.end_char - region.start_char),
                  region.sequence_no,
                  dirty.interface_id
         LIMIT 1;

        EXIT WHEN selected_interface_id IS NULL;

        DELETE FROM execution.semantic_pnf_frontier_dirty
         WHERE interface_id = selected_interface_id;

        PERFORM *
          FROM execution.rebuild_numeric_pnf_parent_frontier(
              selected_interface_id
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
