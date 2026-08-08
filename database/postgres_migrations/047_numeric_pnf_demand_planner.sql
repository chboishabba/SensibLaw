BEGIN;

ALTER TABLE execution.semantic_pnf_demand
    ADD COLUMN IF NOT EXISTS source_start_char BIGINT,
    ADD COLUMN IF NOT EXISTS candidate_count SMALLINT NOT NULL DEFAULT 0
        CHECK (candidate_count BETWEEN 0 AND 256);

CREATE OR REPLACE FUNCTION execution.assign_numeric_pnf_demand_position()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.source_start_char IS NULL THEN
        SELECT end_char
          INTO NEW.source_start_char
          FROM execution.semantic_pnf_region
         WHERE region_id = NEW.source_region_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_position
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_position
BEFORE INSERT OR UPDATE OF source_region_id
ON execution.semantic_pnf_demand
FOR EACH ROW
EXECUTE FUNCTION execution.assign_numeric_pnf_demand_position();

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_demand_candidate (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    ordinal SMALLINT NOT NULL CHECK (ordinal BETWEEN 0 AND 255),
    target_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_target_kind(kind_id) ON DELETE RESTRICT,
    target_id BIGINT NOT NULL,
    source_interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    ancestor_distance BIGINT NOT NULL CHECK (ancestor_distance >= 0),
    index_rank BIGINT NOT NULL DEFAULT 0,
    candidate_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (demand_id, ordinal),
    UNIQUE (demand_id, target_kind, target_id)
);

CREATE INDEX IF NOT EXISTS semantic_pnf_demand_candidate_target_idx
    ON execution.semantic_pnf_demand_candidate
       (target_kind, target_id, demand_id);

CREATE OR REPLACE FUNCTION execution.index_numeric_pnf_object_export()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    object_kind_id BIGINT;
BEGIN
    IF NEW.target_kind <> 1 THEN
        RETURN NEW;
    END IF;
    SELECT object_kind_symbol_id
      INTO object_kind_id
      FROM execution.semantic_pnf_object
     WHERE object_id = NEW.target_id;
    IF object_kind_id IS NOT NULL THEN
        INSERT INTO execution.semantic_pnf_interface_lookup
            (interface_id, key_kind, key_a, key_b,
             target_kind, target_id, rank)
        VALUES (
            NEW.interface_id,
            2,
            object_kind_id,
            0,
            NEW.target_kind,
            NEW.target_id,
            NEW.rank
        )
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_object_export_kind_index
    ON execution.semantic_pnf_interface_export;
CREATE TRIGGER semantic_pnf_object_export_kind_index
AFTER INSERT ON execution.semantic_pnf_interface_export
FOR EACH ROW
EXECUTE FUNCTION execution.index_numeric_pnf_object_export();

CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    demand_row RECORD;
    inserted_total BIGINT := 0;
    inserted_for_demand BIGINT;
    anaphor_residual_id BIGINT;
    pronoun_kind_id BIGINT;
BEGIN
    SELECT symbol_id
      INTO anaphor_residual_id
      FROM execution.semantic_symbol
     WHERE kind_id = 13
       AND symbol_text = 'anaphor_unresolved';
    SELECT symbol_id
      INTO pronoun_kind_id
      FROM execution.semantic_symbol
     WHERE kind_id = 14
       AND symbol_text = 'mention.pronoun';

    FOR demand_row IN
        SELECT demand.*
          FROM execution.semantic_pnf_demand AS demand
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE source_region.run_ref = selected_run_ref
           AND source_region.document_ref = selected_document_ref
           AND demand.source_interface_id IS NOT NULL
           AND demand.state IN (1, 2)
         ORDER BY demand.demand_id
    LOOP
        DELETE FROM execution.semantic_pnf_demand_candidate
         WHERE demand_id = demand_row.demand_id;

        INSERT INTO execution.semantic_pnf_demand_candidate
            (demand_id, ordinal, target_kind, target_id,
             source_interface_id, ancestor_distance,
             index_rank, candidate_score)
        SELECT demand_row.demand_id,
               row_number() OVER (
                   ORDER BY candidate.ancestor_distance,
                            candidate.index_rank,
                            candidate.target_id
               ) - 1,
               candidate.target_kind,
               candidate.target_id,
               candidate.source_interface_id,
               candidate.ancestor_distance,
               candidate.index_rank,
               candidate.candidate_score
          FROM LATERAL (
              SELECT DISTINCT ON (visible.target_kind, visible.target_id)
                     visible.target_kind,
                     visible.target_id,
                     visible.source_interface_id,
                     visible.ancestor_distance,
                     visible.rank AS index_rank,
                     COALESCE(object.promotion_score, factor.support_score, 0)
                         AS candidate_score
                FROM execution.semantic_pnf_visible_lookup AS visible
                LEFT JOIN execution.semantic_pnf_object AS object
                  ON visible.target_kind = 1
                 AND object.object_id = visible.target_id
                LEFT JOIN execution.semantic_pnf_factor AS factor
                  ON visible.target_kind = 2
                 AND factor.factor_id = visible.target_id
                LEFT JOIN execution.semantic_pnf_region AS target_region
                  ON target_region.region_id = COALESCE(
                      object.region_id,
                      factor.region_id
                  )
               WHERE visible.interface_id = demand_row.source_interface_id
                 AND visible.target_kind = demand_row.expected_target_kind
                 AND (
                     (
                         demand_row.residual_type_symbol_id
                             = anaphor_residual_id
                         AND visible.target_kind = 1
                         AND target_region.region_id
                             <> demand_row.source_region_id
                         AND (
                             pronoun_kind_id IS NULL
                             OR object.object_kind_symbol_id <> pronoun_kind_id
                         )
                         AND target_region.end_char
                             <= demand_row.source_start_char
                     )
                     OR (
                         demand_row.expected_factor_type_symbol_id IS NOT NULL
                         AND visible.key_kind = 1
                         AND visible.key_a
                             = demand_row.expected_factor_type_symbol_id
                     )
                     OR (
                         demand_row.expected_object_kind_symbol_id IS NOT NULL
                         AND visible.key_kind = 2
                         AND visible.key_a
                             = demand_row.expected_object_kind_symbol_id
                     )
                     OR (
                         demand_row.lexical_symbol_id IS NOT NULL
                         AND visible.key_kind = 3
                         AND visible.key_a = demand_row.lexical_symbol_id
                     )
                     OR (
                         visible.key_kind = 5
                         AND visible.key_a
                             = demand_row.residual_type_symbol_id
                     )
                 )
               ORDER BY visible.target_kind,
                        visible.target_id,
                        visible.ancestor_distance,
                        visible.rank
               LIMIT demand_row.max_candidates
          ) AS candidate;

        GET DIAGNOSTICS inserted_for_demand = ROW_COUNT;
        inserted_total := inserted_total + inserted_for_demand;
        UPDATE execution.semantic_pnf_demand
           SET candidate_count = inserted_for_demand,
               state = CASE
                   WHEN inserted_for_demand > 0 THEN 2
                   ELSE state
               END
         WHERE demand_id = demand_row.demand_id;
    END LOOP;

    UPDATE execution.semantic_pnf_demand AS demand
       SET state = 3
      FROM execution.semantic_pnf_region AS source_region
     WHERE source_region.region_id = demand.source_region_id
       AND source_region.run_ref = selected_run_ref
       AND source_region.document_ref = selected_document_ref
       AND demand.state = 1
       AND demand.candidate_count = 0
       AND EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_region AS document_region
            WHERE document_region.run_ref = selected_run_ref
              AND document_region.document_ref = selected_document_ref
              AND document_region.region_kind = 10
              AND document_region.closure_state = 3
       );
    RETURN inserted_total;
END;
$$;

CREATE INDEX IF NOT EXISTS semantic_pnf_visible_lookup_target_idx
    ON execution.semantic_pnf_visible_lookup
       (interface_id, target_kind, ancestor_distance, rank, target_id);

COMMIT;
