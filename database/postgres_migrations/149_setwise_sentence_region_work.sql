BEGIN;

-- 149: parser partitions already COPY their sentence rows in one statement.
-- The original migration-040 row-level trigger immediately decomposed that
-- batch into one parent lookup plus region/link/edge/work writes per sentence.
-- Preserve the exact same sentence-region/work identities as one transition-
-- table projection over the inserted parser-sentence fibre.

DROP TRIGGER IF EXISTS semantic_numeric_sentence_region
    ON execution.semantic_parser_sentence;

CREATE OR REPLACE FUNCTION execution.project_numeric_sentence_regions()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Upsert every numeric sentence region. The lateral parent choice is the
    -- same ordered enclosing-region rule used by migration 040, evaluated by
    -- PostgreSQL over the inserted sentence relation rather than via one trigger
    -- invocation per row.
    INSERT INTO execution.semantic_pnf_region
        (region_digest, run_ref, document_ref, region_kind,
         start_char, end_char, sequence_no, parent_region_id,
         closure_state, authored_boundary)
    SELECT digest(
               int8send(sentence.sentence_id)
               || int8send(sentence.start_char)
               || int8send(sentence.end_char),
               'sha256'
           ),
           sentence.run_ref,
           sentence.document_ref,
           1,
           sentence.start_char,
           sentence.end_char,
           sentence.start_char,
           parent.region_id,
           1,
           FALSE
      FROM inserted_sentence AS sentence
      LEFT JOIN LATERAL (
          SELECT region.region_id
            FROM execution.semantic_pnf_region AS region
           WHERE region.run_ref = sentence.run_ref
             AND region.document_ref = sentence.document_ref
             AND region.region_kind IN (3, 5, 6, 7, 8, 10)
             AND region.start_char <= sentence.start_char
             AND region.end_char > sentence.start_char
           ORDER BY
             CASE region.region_kind
                 WHEN 3 THEN 1
                 WHEN 5 THEN 2
                 WHEN 6 THEN 3
                 WHEN 7 THEN 4
                 WHEN 8 THEN 5
                 ELSE 6
             END,
             region.end_char - region.start_char
           LIMIT 1
      ) AS parent ON TRUE
     WHERE sentence.representation_version = 2
    ON CONFLICT (
        run_ref, document_ref, region_kind, start_char, end_char
    ) DO UPDATE SET parent_region_id = COALESCE(
        execution.semantic_pnf_region.parent_region_id,
        EXCLUDED.parent_region_id
    );

    INSERT INTO execution.semantic_pnf_sentence_region(sentence_id, region_id)
    SELECT sentence.sentence_id, region.region_id
      FROM inserted_sentence AS sentence
      JOIN execution.semantic_pnf_region AS region
        ON region.run_ref = sentence.run_ref
       AND region.document_ref = sentence.document_ref
       AND region.region_kind = 1
       AND region.start_char = sentence.start_char
       AND region.end_char = sentence.end_char
     WHERE sentence.representation_version = 2
    ON CONFLICT (sentence_id) DO NOTHING;

    INSERT INTO execution.semantic_pnf_region_edge
        (source_region_id, target_region_id, edge_kind, ordinal)
    SELECT region.region_id,
           region.parent_region_id,
           1,
           sentence.start_char
      FROM inserted_sentence AS sentence
      JOIN execution.semantic_pnf_region AS region
        ON region.run_ref = sentence.run_ref
       AND region.document_ref = sentence.document_ref
       AND region.region_kind = 1
       AND region.start_char = sentence.start_char
       AND region.end_char = sentence.end_char
     WHERE sentence.representation_version = 2
       AND region.parent_region_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_work_item
        (work_digest, run_ref, document_ref, region_id,
         operation_id, state_id, priority)
    SELECT digest(
               int8send(region.region_id) || int2send(1::SMALLINT),
               'sha256'
           ),
           sentence.run_ref,
           sentence.document_ref,
           region.region_id,
           1,
           1,
           10
      FROM inserted_sentence AS sentence
      JOIN execution.semantic_pnf_region AS region
        ON region.run_ref = sentence.run_ref
       AND region.document_ref = sentence.document_ref
       AND region.region_kind = 1
       AND region.start_char = sentence.start_char
       AND region.end_char = sentence.end_char
     WHERE sentence.representation_version = 2
    ON CONFLICT (region_id, operation_id) DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_numeric_sentence_region
AFTER INSERT ON execution.semantic_parser_sentence
REFERENCING NEW TABLE AS inserted_sentence
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_sentence_regions();

COMMIT;
