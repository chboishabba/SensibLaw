BEGIN;

ALTER TABLE execution.semantic_parser_token
    DROP CONSTRAINT IF EXISTS semantic_parser_token_head_token_ref_fkey;
ALTER TABLE execution.semantic_parser_token
    ADD CONSTRAINT semantic_parser_token_head_token_ref_fkey
    FOREIGN KEY (head_token_ref)
    REFERENCES execution.semantic_parser_token(token_ref)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

CREATE OR REPLACE FUNCTION execution.assign_parser_repair_sequence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.partition_kind <> 'boundary_repair' THEN
        RETURN NEW;
    END IF;
    PERFORM pg_advisory_xact_lock(
        hashtextextended(NEW.run_ref || E'\x1f' || NEW.document_ref, 0)
    );
    SELECT coalesce(max(partition.sequence_no), -1) + 1
      INTO NEW.sequence_no
      FROM execution.semantic_parser_partition AS partition
     WHERE partition.run_ref = NEW.run_ref
       AND partition.document_ref = NEW.document_ref;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_repair_sequence
    ON execution.semantic_parser_partition;
CREATE TRIGGER semantic_parser_repair_sequence
BEFORE INSERT ON execution.semantic_parser_partition
FOR EACH ROW
EXECUTE FUNCTION execution.assign_parser_repair_sequence();

CREATE OR REPLACE FUNCTION execution.validate_parser_boundary_resolution()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state <> 'resolved' OR OLD.state = 'resolved' THEN
        RETURN NEW;
    END IF;
    IF NEW.repair_partition_ref IS NULL OR NOT EXISTS (
        SELECT 1
        FROM execution.semantic_parser_sentence AS sentence
        WHERE sentence.partition_ref = NEW.repair_partition_ref
          AND sentence.run_ref = NEW.run_ref
          AND sentence.document_ref = NEW.document_ref
          AND sentence.start_char <= NEW.suspected_start_char
          AND sentence.end_char >= NEW.suspected_end_char
    ) THEN
        RAISE EXCEPTION
            'parser boundary obligation % lacks covering repair sentence',
            NEW.obligation_ref;
    END IF;
    NEW.resolved_at := coalesce(NEW.resolved_at, CURRENT_TIMESTAMP);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_boundary_resolution_guard
    ON execution.semantic_parser_boundary_obligation;
CREATE TRIGGER semantic_parser_boundary_resolution_guard
BEFORE UPDATE OF state
ON execution.semantic_parser_boundary_obligation
FOR EACH ROW
EXECUTE FUNCTION execution.validate_parser_boundary_resolution();

COMMIT;
