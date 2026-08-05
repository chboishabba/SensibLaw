-- Transactional publication outbox for distributed semantic execution.
--
-- Strict delta admission is defined by migration 028 and receives its matching
-- trigger in migration 030, after that compatibility table exists.

DROP TRIGGER IF EXISTS semantic_delta_admission_outbox
ON execution.semantic_delta_admission;
DROP FUNCTION IF EXISTS execution.emit_semantic_delta_admitted();

CREATE OR REPLACE FUNCTION execution.emit_publication_committed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    event_ref_value text;
BEGIN
    IF NEW.state <> 'committed'
       OR OLD.state = 'committed' THEN
        RETURN NEW;
    END IF;
    event_ref_value := 'semantic-outbox:publication-committed:' || NEW.publication_ref;
    INSERT INTO execution.semantic_outbox
        (event_ref, aggregate_ref, event_type_ref, payload)
    VALUES
        (
            event_ref_value,
            NEW.document_ref,
            'semantic.publication.committed.v1',
            jsonb_build_object(
                'publication_ref', NEW.publication_ref,
                'run_ref', NEW.run_ref,
                'document_ref', NEW.document_ref,
                'manifest_sha256', encode(NEW.manifest_sha256, 'hex'),
                'committed_at', CURRENT_TIMESTAMP
            )
        )
    ON CONFLICT (event_ref) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_publication_outbox
ON execution.semantic_publication;
CREATE TRIGGER semantic_publication_outbox
AFTER UPDATE OF state ON execution.semantic_publication
FOR EACH ROW
EXECUTE FUNCTION execution.emit_publication_committed();
