-- Transactional outbox for distributed semantic execution.
--
-- Events are emitted by PostgreSQL in the same transaction as semantic
-- admission/publication.  Workers cannot accidentally acknowledge completion
-- without producing the corresponding durable event.

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
    IF NEW.state_ref <> 'committed'
       OR OLD.state_ref = 'committed' THEN
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
                'document_ref', NEW.document_ref,
                'graph_manifest_ref', NEW.graph_manifest_ref,
                'certificate_ref', NEW.certificate_ref,
                'publication_digest', encode(NEW.publication_digest, 'hex'),
                'committed_at', NEW.committed_at
            )
        )
    ON CONFLICT (event_ref) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_publication_outbox
ON execution.publication_build;
CREATE TRIGGER semantic_publication_outbox
AFTER UPDATE OF state_ref ON execution.publication_build
FOR EACH ROW
EXECUTE FUNCTION execution.emit_publication_committed();
