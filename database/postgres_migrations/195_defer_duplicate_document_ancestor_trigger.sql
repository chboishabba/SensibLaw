BEGIN;

-- Numeric hierarchy materialization already establishes a transaction-local
-- deferred-publication boundary with sensiblaw.defer_frontier_rebuild=on, closes
-- the document interface, and then explicitly publishes canonical document
-- ancestors once the complete hierarchy has been formed.
--
-- Historically the document closure_state transition also fired an immediate
-- full ancestor rebuild, so hierarchy materialization rebuilt the same document
-- ancestor authority twice in one transaction.  Suppress only that trigger-time
-- publication while the existing deferred-publication boundary is active.  The
-- explicit final rebuild remains authoritative.
CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_ancestors_on_document_close()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF current_setting('sensiblaw.defer_frontier_rebuild', true) = 'on' THEN
        RETURN NEW;
    END IF;

    IF NEW.region_kind = 10
       AND NEW.closure_state = 3
       AND OLD.closure_state IS DISTINCT FROM NEW.closure_state THEN
        PERFORM execution.rebuild_pnf_document_ancestors(
            NEW.run_ref,
            NEW.document_ref
        );
    END IF;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION execution.refresh_numeric_pnf_ancestors_on_document_close() IS
    'Publishes document ancestor authority on ordinary document close; hierarchy materialization defers this trigger-time duplicate and performs one explicit canonical document rebuild after the hierarchy is complete.';

COMMIT;
