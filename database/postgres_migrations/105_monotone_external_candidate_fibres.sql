BEGIN;

-- 105: external candidate discovery is monotone evidence accumulation, not a
-- closed-world replacement operation. An empty/newer provider response cannot
-- delete older alternatives merely because they were absent from this read.
-- Candidate identity is (label, world entity); ranking is acquisition-relative.

DO $$
DECLARE constraint_row RECORD;
BEGIN
    FOR constraint_row IN
        SELECT constraint_name.conname
          FROM pg_constraint AS constraint_name
         WHERE constraint_name.conrelid =
                   'execution.semantic_pnf_label_world_candidate'::regclass
           AND constraint_name.contype='u'
           AND pg_get_constraintdef(constraint_name.oid) LIKE
               '%(label_symbol_id, candidate_ordinal, cache_revision)%'
    LOOP
        EXECUTE format(
            'ALTER TABLE execution.semantic_pnf_label_world_candidate DROP CONSTRAINT %I',
            constraint_row.conname
        );
    END LOOP;
END;
$$;

CREATE INDEX IF NOT EXISTS semantic_pnf_label_world_candidate_rank_idx
    ON execution.semantic_pnf_label_world_candidate
       (label_symbol_id,cache_revision,source_epoch DESC NULLS LAST,
        candidate_ordinal,world_entity_id);

-- Explicit helper used by the Python gateway. Newer known-age evidence may
-- refresh rank/source for the same candidate. Unknown-age evidence may fill an
-- unknown-age row, but can never erase a known source epoch/reference.
CREATE OR REPLACE FUNCTION execution.upsert_numeric_pnf_label_world_candidate(
    selected_label_symbol_id BIGINT,
    selected_world_entity_id BIGINT,
    selected_candidate_ordinal INTEGER,
    selected_cache_revision BIGINT,
    selected_source_epoch BIGINT,
    selected_source_ref TEXT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
BEGIN
    IF selected_candidate_ordinal<0 THEN
        RAISE EXCEPTION 'candidate ordinal must be non-negative';
    END IF;
    IF selected_source_epoch IS NOT NULL AND selected_source_epoch<=0 THEN
        RAISE EXCEPTION 'candidate source epoch must be positive';
    END IF;
    IF selected_source_ref IS NOT NULL AND btrim(selected_source_ref)='' THEN
        RAISE EXCEPTION 'candidate source ref cannot be blank';
    END IF;

    INSERT INTO execution.semantic_pnf_label_world_candidate
        (label_symbol_id,world_entity_id,candidate_ordinal,cache_revision,
         source_epoch,source_ref)
    VALUES (
        selected_label_symbol_id,selected_world_entity_id,
        selected_candidate_ordinal,selected_cache_revision,
        selected_source_epoch,selected_source_ref
    )
    ON CONFLICT(label_symbol_id,world_entity_id) DO UPDATE SET
        candidate_ordinal=CASE
            WHEN execution.semantic_pnf_label_world_candidate.source_epoch IS NULL
                 AND EXCLUDED.source_epoch IS NULL
            THEN EXCLUDED.candidate_ordinal
            WHEN EXCLUDED.source_epoch IS NOT NULL
                 AND (
                     execution.semantic_pnf_label_world_candidate.source_epoch IS NULL
                     OR EXCLUDED.source_epoch>=execution.semantic_pnf_label_world_candidate.source_epoch
                 )
            THEN EXCLUDED.candidate_ordinal
            ELSE execution.semantic_pnf_label_world_candidate.candidate_ordinal
        END,
        cache_revision=GREATEST(
            execution.semantic_pnf_label_world_candidate.cache_revision,
            EXCLUDED.cache_revision
        ),
        source_epoch=CASE
            WHEN EXCLUDED.source_epoch IS NOT NULL
                 AND (
                     execution.semantic_pnf_label_world_candidate.source_epoch IS NULL
                     OR EXCLUDED.source_epoch>=execution.semantic_pnf_label_world_candidate.source_epoch
                 )
            THEN EXCLUDED.source_epoch
            ELSE execution.semantic_pnf_label_world_candidate.source_epoch
        END,
        source_ref=CASE
            WHEN execution.semantic_pnf_label_world_candidate.source_epoch IS NULL
                 AND EXCLUDED.source_epoch IS NULL
                 AND EXCLUDED.source_ref IS NOT NULL
            THEN EXCLUDED.source_ref
            WHEN EXCLUDED.source_epoch IS NOT NULL
                 AND (
                     execution.semantic_pnf_label_world_candidate.source_epoch IS NULL
                     OR EXCLUDED.source_epoch>=execution.semantic_pnf_label_world_candidate.source_epoch
                 )
            THEN EXCLUDED.source_ref
            ELSE execution.semantic_pnf_label_world_candidate.source_ref
        END;
    RETURN TRUE;
END;
$$;

COMMIT;
