BEGIN;

-- Select at most one immediate closed neighbour on each side. A single global
-- LIMIT could choose two candidates from the same side and miss a boundary when
-- regions close out of authored order.
CREATE OR REPLACE FUNCTION execution.materialize_numeric_pnf_adjacent_regions()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    sibling RECORD;
    pair_kind SMALLINT;
    left_id BIGINT;
    right_id BIGINT;
BEGIN
    IF NEW.region_kind NOT IN (1, 3)
       OR NEW.closure_state NOT IN (2, 3)
       OR OLD.closure_state IS NOT DISTINCT FROM NEW.closure_state THEN
        RETURN NEW;
    END IF;

    pair_kind := CASE NEW.region_kind WHEN 1 THEN 2 ELSE 4 END;

    FOR sibling IN
        SELECT candidate.*
          FROM (
              (
                  SELECT region_id, sequence_no, start_char, end_char
                    FROM execution.semantic_pnf_region
                   WHERE run_ref = NEW.run_ref
                     AND document_ref = NEW.document_ref
                     AND region_kind = NEW.region_kind
                     AND parent_region_id IS NOT DISTINCT FROM NEW.parent_region_id
                     AND closure_state IN (2, 3)
                     AND region_id <> NEW.region_id
                     AND end_char <= NEW.start_char
                   ORDER BY end_char DESC, sequence_no DESC, region_id DESC
                   LIMIT 1
              )
              UNION ALL
              (
                  SELECT region_id, sequence_no, start_char, end_char
                    FROM execution.semantic_pnf_region
                   WHERE run_ref = NEW.run_ref
                     AND document_ref = NEW.document_ref
                     AND region_kind = NEW.region_kind
                     AND parent_region_id IS NOT DISTINCT FROM NEW.parent_region_id
                     AND closure_state IN (2, 3)
                     AND region_id <> NEW.region_id
                     AND start_char >= NEW.end_char
                   ORDER BY start_char, sequence_no, region_id
                   LIMIT 1
              )
          ) AS candidate
    LOOP
        IF sibling.end_char <= NEW.start_char THEN
            left_id := sibling.region_id;
            right_id := NEW.region_id;
        ELSE
            left_id := NEW.region_id;
            right_id := sibling.region_id;
        END IF;

        IF NOT EXISTS (
            SELECT 1
              FROM execution.semantic_pnf_region AS middle
             WHERE middle.run_ref = NEW.run_ref
               AND middle.document_ref = NEW.document_ref
               AND middle.region_kind = NEW.region_kind
               AND middle.parent_region_id IS NOT DISTINCT FROM NEW.parent_region_id
               AND middle.region_id NOT IN (left_id, right_id)
               AND middle.start_char > (
                   SELECT start_char
                     FROM execution.semantic_pnf_region
                    WHERE region_id = left_id
               )
               AND middle.end_char < (
                   SELECT end_char
                     FROM execution.semantic_pnf_region
                    WHERE region_id = right_id
               )
        ) THEN
            PERFORM execution.ensure_numeric_pnf_adjacent_pair(
                left_id,
                right_id,
                pair_kind
            );
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$;

-- Sentence-pair work may complete before its canonical paragraph interface is
-- created. Bind supporting pair interfaces when that parent interface appears,
-- without turning pair regions into canonical region children.
CREATE OR REPLACE FUNCTION execution.bind_supported_pair_interfaces()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    pair_interface RECORD;
BEGIN
    FOR pair_interface IN
        SELECT interface.interface_id
          FROM execution.semantic_pnf_region_edge AS support
          JOIN execution.semantic_pnf_interface AS interface
            ON interface.region_id = support.source_region_id
         WHERE support.target_region_id = NEW.region_id
           AND support.edge_kind = 5
    LOOP
        UPDATE execution.semantic_pnf_interface
           SET parent_interface_id = NEW.interface_id
         WHERE interface_id = pair_interface.interface_id
           AND parent_interface_id IS DISTINCT FROM NEW.interface_id;
        PERFORM execution.rebuild_pnf_interface_ancestors(
            pair_interface.interface_id
        );
    END LOOP;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_supported_pair_binding
    ON execution.semantic_pnf_interface;
CREATE TRIGGER semantic_pnf_supported_pair_binding
AFTER INSERT ON execution.semantic_pnf_interface
FOR EACH ROW
EXECUTE FUNCTION execution.bind_supported_pair_interfaces();

COMMIT;
