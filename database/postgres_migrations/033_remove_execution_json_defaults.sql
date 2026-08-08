BEGIN;

-- The typed execution path must not create even empty JSONB values through
-- legacy defaults. Historical columns remain nullable only for migration
-- compatibility; new code writes NULL and typed replacement columns.
--
-- Blob-write rejection is installed by migration 036 using table-specific
-- WHEN predicates. It deliberately does not live here: one polymorphic trigger
-- function must never dereference fields that do not exist on every row type.
ALTER TABLE execution.semantic_run
    ALTER COLUMN lifecycle_history DROP DEFAULT,
    ALTER COLUMN lifecycle_history DROP NOT NULL;

ALTER TABLE execution.semantic_kernel_registration
    ALTER COLUMN metadata DROP DEFAULT,
    ALTER COLUMN metadata DROP NOT NULL;

ALTER TABLE execution.semantic_lifecycle_event
    ALTER COLUMN detail DROP DEFAULT,
    ALTER COLUMN detail DROP NOT NULL;

ALTER TABLE execution.semantic_worker_receipt
    ALTER COLUMN payload DROP DEFAULT,
    ALTER COLUMN payload DROP NOT NULL;

ALTER TABLE execution.semantic_work_attempt_v2
    ADD COLUMN IF NOT EXISTS error_reason TEXT;

ALTER TABLE execution.semantic_work_item
    ADD COLUMN IF NOT EXISTS last_error_reason TEXT;

COMMIT;
