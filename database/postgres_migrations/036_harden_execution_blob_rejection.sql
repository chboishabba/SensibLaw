BEGIN;

-- Replace the polymorphic record-field trigger from migration 033 with
-- table-specific WHEN predicates.  The trigger function itself is independent
-- of row shape, so PostgreSQL never resolves a field that does not exist on the
-- current table.
DO $$
DECLARE
    table_name TEXT;
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
        EXECUTE format(
            'DROP TRIGGER IF EXISTS %I ON execution.%I',
            'reject_execution_json_' || table_name,
            table_name
        );
    END LOOP;
END;
$$;

DROP FUNCTION IF EXISTS execution.reject_new_execution_json();

CREATE FUNCTION execution.reject_execution_blob_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'serialized execution authority is forbidden on execution.%',
        TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER reject_execution_blob_semantic_closure_job
BEFORE INSERT OR UPDATE ON execution.semantic_closure_job
FOR EACH ROW WHEN (NEW.input_manifest IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_immutable_delta
BEFORE INSERT OR UPDATE ON execution.semantic_immutable_delta
FOR EACH ROW WHEN (NEW.payload IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_round_manifest
BEFORE INSERT OR UPDATE ON execution.semantic_round_manifest
FOR EACH ROW WHEN (NEW.manifest IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_finalization_cursor
BEFORE INSERT OR UPDATE ON execution.semantic_finalization_cursor
FOR EACH ROW WHEN (NEW.manifest IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_publication
BEFORE INSERT OR UPDATE ON execution.semantic_publication
FOR EACH ROW WHEN (NEW.manifest IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_execution_receipt
BEFORE INSERT OR UPDATE ON execution.semantic_execution_receipt
FOR EACH ROW WHEN (NEW.payload IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_work_item
BEFORE INSERT OR UPDATE ON execution.semantic_work_item
FOR EACH ROW WHEN (NEW.input_manifest IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_work_receipt
BEFORE INSERT OR UPDATE ON execution.semantic_work_receipt
FOR EACH ROW WHEN (NEW.payload IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_stage_cursor
BEFORE INSERT OR UPDATE ON execution.semantic_stage_cursor
FOR EACH ROW WHEN (NEW.cursor_manifest IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_stage_manifest
BEFORE INSERT OR UPDATE ON execution.semantic_stage_manifest
FOR EACH ROW WHEN (NEW.child_work_refs IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

CREATE TRIGGER reject_execution_blob_semantic_outbox
BEFORE INSERT OR UPDATE ON execution.semantic_outbox
FOR EACH ROW WHEN (NEW.payload IS NOT NULL)
EXECUTE FUNCTION execution.reject_execution_blob_write();

COMMIT;
