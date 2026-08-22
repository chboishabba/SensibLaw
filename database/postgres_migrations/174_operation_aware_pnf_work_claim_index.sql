BEGIN;

-- 174: strict numeric workers claim one operation at a time. The original
-- partial ready index is ordered by (run_ref, state_id, priority, work_id), but
-- claim_work() also constrains operation_id. On a mixed work frontier that can
-- force a worker to walk ready/leased rows belonging to other operations before
-- finding its own fibre.
--
-- This is a physical access-path change only. Lease ordering remains
-- (priority, work_id), SKIP LOCKED semantics are unchanged, and no semantic or
-- work-state authority moves into the index.
CREATE INDEX IF NOT EXISTS semantic_pnf_work_operation_ready_idx
    ON execution.semantic_pnf_work_item
       (run_ref, operation_id, state_id, priority, work_id)
    WHERE state_id IN (1, 2);

COMMIT;
