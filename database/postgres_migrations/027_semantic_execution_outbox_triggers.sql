-- Transactional outbox for distributed semantic execution.
--
-- Events are emitted by PostgreSQL in the same transaction as semantic
-- admission/publication. Workers cannot acknowledge completion without the
-- corresponding durable event.

CREATE OR REPLACE FUNCTION execution.emit_semantic_delta_admitted()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    event_ref_value text;
BEGIN
    IF NEW.admission_state_ref <> 'accepted' THEN
        RETURN NEW;
    END IF;
    event_ref_value := 'semantic-outbox:delta-admitted:' || NEW.delta_ref;
    INSERT INTO execution.semantic_outbox
        (event_ref, aggregate_ref, event_type_ref, payload)
    VALUES
        (
            event_ref_value,
            NEW.owner_ref,
            'semantic.delta.admitted.v1',
            jsonb_build_object(
                'delta_ref', NEW.delta_ref,
                'job_ref', NEW.job_ref,
                'owner_ref', NEW.owner_ref,
                'lease_epoch', NEW.lease_epoch,
                'prior_owner_revision', NEW.prior_owner_revision,
                'resulting_owner_revision', NEW.resulting_owner_revision
            )
        )
    ON CONFLICT (event_ref) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_delta_admission_outbox
ON execution.semantic_delta_admission;
CREATE TRIGGER semantic_delta_admission_outbox
AFTER INSERT ON execution.semantic_delta_admission
FOR EACH ROW
EXECUTE FUNCTION execution.emit_semantic_delta_admitted();

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
