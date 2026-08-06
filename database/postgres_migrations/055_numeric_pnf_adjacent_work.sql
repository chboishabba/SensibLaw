BEGIN;

-- Adjacent scales are overlapping execution fibres, not replacement parents.
-- The canonical sentence/paragraph containment spine remains unchanged; each
-- pair receives its own region, membership edges and fenced work item.
CREATE OR REPLACE FUNCTION execution.ensure_numeric_pnf_adjacent_pair(
    selected_left_region_id BIGINT,
    selected_right_region_id BIGINT,
    selected_pair_kind SMALLINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    left_region RECORD;
    right_region RECORD;
    pair_region_id BIGINT;
    pair_digest BYTEA;
BEGIN
    SELECT * INTO left_region
      FROM execution.semantic_pnf_region
     WHERE region_id = selected_left_region_id;
    SELECT * INTO right_region
      FROM execution.semantic_pnf_region
     WHERE region_id = selected_right_region_id;

    IF left_region.region_id IS NULL OR right_region.region_id IS NULL THEN
        RAISE EXCEPTION 'adjacent PNF pair references a missing region';
    END IF;
    IF left_region.run_ref IS DISTINCT FROM right_region.run_ref
       OR left_region.document_ref IS DISTINCT FROM right_region.document_ref THEN
        RAISE EXCEPTION 'adjacent PNF pair crosses run/document identity';
    END IF;
    IF left_region.parent_region_id IS DISTINCT FROM right_region.parent_region_id THEN
        RAISE EXCEPTION 'adjacent PNF pair must share a canonical parent';
    END IF;
    IF left_region.region_kind = 1 AND selected_pair_kind <> 2 THEN
        RAISE EXCEPTION 'sentence adjacency requires adjacent_sentence kind';
    END IF;
    IF left_region.region_kind = 3 AND selected_pair_kind <> 4 THEN
        RAISE EXCEPTION 'paragraph adjacency requires adjacent_paragraph kind';
    END IF;
    IF left_region.region_kind <> right_region.region_kind
       OR left_region.region_kind NOT IN (1, 3) THEN
        RAISE EXCEPTION 'adjacent PNF members must share sentence/paragraph kind';
    END IF;
    IF left_region.closure_state NOT IN (2, 3)
       OR right_region.closure_state NOT IN (2, 3) THEN
        RAISE EXCEPTION 'adjacent PNF members must be locally closed';
    END IF;
    IF left_region.end_char > right_region.start_char THEN
        RAISE EXCEPTION 'adjacent PNF members are reversed or overlap unexpectedly';
    END IF;

    pair_digest := digest(
        int8send(left_region.region_id)
        || int8send(right_region.region_id)
        || int2send(selected_pair_kind),
        'sha256'
    );

    INSERT INTO execution.semantic_pnf_region
        (region_digest, run_ref, document_ref, region_kind,
         start_char, end_char, sequence_no, parent_region_id,
         closure_state, authored_boundary)
    VALUES (
        pair_digest,
        left_region.run_ref,
        left_region.document_ref,
        selected_pair_kind,
        left_region.start_char,
        right_region.end_char,
        left_region.sequence_no,
        left_region.parent_region_id,
        1,
        FALSE
    )
    ON CONFLICT (
        run_ref, document_ref, region_kind, start_char, end_char
    ) DO UPDATE SET
        parent_region_id = EXCLUDED.parent_region_id
    RETURNING region_id INTO pair_region_id;

    INSERT INTO execution.semantic_pnf_region_edge
        (source_region_id, target_region_id, edge_kind, ordinal)
    VALUES
        (left_region.region_id, pair_region_id, 1, 0),
        (right_region.region_id, pair_region_id, 1, 1),
        (left_region.region_id, right_region.region_id, 2, 0)
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_region_edge
        (source_region_id, target_region_id, edge_kind, ordinal)
    SELECT pair_region_id, left_region.parent_region_id, 1, left_region.sequence_no
     WHERE left_region.parent_region_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_work_item
        (work_digest, run_ref, document_ref, region_id,
         operation_id, state_id, priority)
    VALUES (
        digest(int8send(pair_region_id) || int2send(2::SMALLINT), 'sha256'),
        left_region.run_ref,
        left_region.document_ref,
        pair_region_id,
        2,
        1,
        20
    )
    ON CONFLICT (region_id, operation_id) DO NOTHING;

    RETURN pair_region_id;
END;
$$;

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
        SELECT region_id, sequence_no, start_char, end_char
          FROM execution.semantic_pnf_region
         WHERE run_ref = NEW.run_ref
           AND document_ref = NEW.document_ref
           AND region_kind = NEW.region_kind
           AND parent_region_id IS NOT DISTINCT FROM NEW.parent_region_id
           AND closure_state IN (2, 3)
           AND region_id <> NEW.region_id
           AND (
               end_char <= NEW.start_char
               OR start_char >= NEW.end_char
           )
         ORDER BY
           CASE
               WHEN end_char <= NEW.start_char THEN NEW.start_char - end_char
               ELSE start_char - NEW.end_char
           END,
           sequence_no,
           region_id
         LIMIT 2
    LOOP
        IF sibling.end_char <= NEW.start_char THEN
            left_id := sibling.region_id;
            right_id := NEW.region_id;
        ELSE
            left_id := NEW.region_id;
            right_id := sibling.region_id;
        END IF;

        -- Only immediate authored neighbours are admitted.  A third region may
        -- lie between geometrically separated siblings even if both are closed.
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

DROP TRIGGER IF EXISTS semantic_pnf_adjacent_region_materialization
    ON execution.semantic_pnf_region;
CREATE TRIGGER semantic_pnf_adjacent_region_materialization
AFTER UPDATE OF closure_state
ON execution.semantic_pnf_region
FOR EACH ROW
EXECUTE FUNCTION execution.materialize_numeric_pnf_adjacent_regions();

COMMIT;
