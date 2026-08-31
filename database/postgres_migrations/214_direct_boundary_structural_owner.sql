BEGIN;

-- A repair's durable owner interval records the originally incomplete parser
-- observation, not the completed sentence.  Direct execution publishes the
-- completed sentence under the original structural start-anchor owner, so its
-- end may legitimately exceed both intervals.  Validate that authority rather
-- than treating the evidence-only repair as a semantic owner.
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
          FROM execution.semantic_parser_partition AS repair
          JOIN execution.semantic_parser_partition AS source
            ON source.partition_ref = NEW.source_partition_ref
         WHERE repair.partition_ref = NEW.repair_partition_ref
           AND repair.run_ref = NEW.run_ref
           AND repair.document_ref = NEW.document_ref
           AND (
               EXISTS (
                   SELECT 1
                     FROM execution.semantic_parser_sentence AS sentence
                    WHERE sentence.partition_ref = repair.partition_ref
                      AND sentence.run_ref = NEW.run_ref
                      AND sentence.document_ref = NEW.document_ref
                      AND sentence.start_char <= NEW.suspected_start_char
                      AND sentence.end_char >= NEW.suspected_end_char
               )
               OR EXISTS (
                   SELECT 1
                     FROM execution.semantic_pnf_region AS region
                    WHERE region.run_ref = NEW.run_ref
                      AND region.document_ref = NEW.document_ref
                      AND region.region_kind = 1
                      AND region.start_char <= NEW.suspected_start_char
                      AND region.end_char >= NEW.suspected_end_char
                      AND region.start_char >= source.owner_start_char
                      AND region.start_char < source.owner_end_char
               )
           )
    ) THEN
        RAISE EXCEPTION
            'parser boundary obligation % lacks a structural-owner completion witness',
            NEW.obligation_ref;
    END IF;
    NEW.resolved_at := coalesce(NEW.resolved_at, CURRENT_TIMESTAMP);
    RETURN NEW;
END;
$$;

COMMIT;
