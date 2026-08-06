BEGIN;

-- The typed execution path must not create even empty JSONB values through
-- legacy defaults.  Historical columns remain nullable only for migration
-- compatibility; new code writes NULL and typed replacement columns.
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

-- Prevent the typed authority tables from accidentally receiving blob state.
-- Legacy rows are tolerated, but any new/updated strict row must leave the
-- deprecated columns NULL.
CREATE OR REPLACE FUNCTION execution.reject_new_execution_json()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'semantic_closure_job' AND NEW.input_manifest IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.input_manifest', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_immutable_delta' AND NEW.payload IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.payload', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_round_manifest' AND NEW.manifest IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.manifest', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_finalization_cursor' AND NEW.manifest IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.manifest', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_publication' AND NEW.manifest IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.manifest', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_execution_receipt' AND NEW.payload IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.payload', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_work_item' AND NEW.input_manifest IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.input_manifest', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_work_receipt' AND NEW.payload IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.payload', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_stage_cursor' AND NEW.cursor_manifest IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.cursor_manifest', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_stage_manifest' AND NEW.child_work_refs IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.child_work_refs', TG_TABLE_NAME;
    ELSIF TG_TABLE_NAME = 'semantic_outbox' AND NEW.payload IS NOT NULL THEN
        RAISE EXCEPTION 'JSON execution authority is forbidden: %.payload', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    table_name TEXT;
    trigger_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'semantic_closure_job',
        'semantic_immutable_delta',
        'semantic_round_manifest',
        'semantic_finalization_cursor',
        'semantic_publication',
        'semantic_execution_receipt',
        'semantic_work_item',
        'semantic_work_receipt',
        'semantic_stage_cursor',
        'semantic_stage_manifest',
        'semantic_outbox'
    ]
    LOOP
        trigger_name := 'reject_execution_json_' || table_name;
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON execution.%I', trigger_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE INSERT OR UPDATE ON execution.%I '
            'FOR EACH ROW EXECUTE FUNCTION execution.reject_new_execution_json()',
            trigger_name,
            table_name
        );
    END LOOP;
END;
$$;

COMMIT;
