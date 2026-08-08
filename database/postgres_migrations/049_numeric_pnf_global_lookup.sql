BEGIN;

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_key_kind (
    kind_id SMALLINT PRIMARY KEY,
    kind_name TEXT NOT NULL UNIQUE
);
INSERT INTO execution.semantic_pnf_key_kind VALUES
    (1, 'factor_type'),
    (2, 'object_kind'),
    (3, 'normalized_symbol'),
    (4, 'role'),
    (5, 'residual_type'),
    (6, 'definition'),
    (7, 'scope')
ON CONFLICT (kind_id) DO UPDATE SET kind_name = EXCLUDED.kind_name;

-- One row per exported key.  Visibility is evaluated from region coordinates
-- and the region DAG at lookup time; ancestor exports are never copied into
-- every descendant interface.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_global_lookup (
    run_ref TEXT NOT NULL,
    document_ref TEXT NOT NULL,
    interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    region_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_region_kind(kind_id) ON DELETE RESTRICT,
    region_start_char BIGINT NOT NULL CHECK (region_start_char >= 0),
    region_end_char BIGINT NOT NULL CHECK (region_end_char >= region_start_char),
    key_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_key_kind(kind_id) ON DELETE RESTRICT,
    key_a BIGINT NOT NULL,
    key_b BIGINT NOT NULL DEFAULT 0,
    target_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_target_kind(kind_id) ON DELETE RESTRICT,
    target_id BIGINT NOT NULL,
    rank BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (
        interface_id, key_kind, key_a, key_b, target_kind, target_id
    )
);

CREATE INDEX IF NOT EXISTS semantic_pnf_global_lookup_exact_idx
    ON execution.semantic_pnf_global_lookup
       (run_ref, document_ref, key_kind, key_a, key_b,
        target_kind, region_end_char DESC, rank, target_id);
CREATE INDEX IF NOT EXISTS semantic_pnf_global_lookup_target_idx
    ON execution.semantic_pnf_global_lookup
       (run_ref, document_ref, target_kind, target_id, interface_id);
CREATE INDEX IF NOT EXISTS semantic_pnf_global_lookup_region_idx
    ON execution.semantic_pnf_global_lookup
       (run_ref, document_ref, region_start_char, region_end_char, region_kind);

CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    inserted_count BIGINT;
BEGIN
    DELETE FROM execution.semantic_pnf_global_lookup
     WHERE run_ref = selected_run_ref
       AND document_ref = selected_document_ref;

    INSERT INTO execution.semantic_pnf_global_lookup
        (run_ref, document_ref, interface_id, region_id, region_kind,
         region_start_char, region_end_char,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT region.run_ref,
           region.document_ref,
           lookup.interface_id,
           region.region_id,
           region.region_kind,
           region.start_char,
           region.end_char,
           lookup.key_kind,
           lookup.key_a,
           lookup.key_b,
           lookup.target_kind,
           lookup.target_id,
           lookup.rank
      FROM execution.semantic_pnf_interface_lookup AS lookup
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = lookup.interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE region.run_ref = selected_run_ref
       AND region.document_ref = selected_document_ref
       AND interface.closure_state IN (2, 3)
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    RETURN inserted_count;
END;
$$;

-- Preserve the existing call surface while removing the quadratic visibility
-- closure.  Callers now receive the linear global-index row count.
CREATE OR REPLACE FUNCTION execution.refresh_pnf_visible_lookup(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE sql
AS $$
    SELECT execution.refresh_pnf_global_lookup(
        selected_run_ref,
        selected_document_ref
    )
$$;

DROP TRIGGER IF EXISTS semantic_pnf_visible_demand_planning
    ON execution.semantic_pnf_visible_lookup;

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
                   ORDER BY candidate.structural_distance,
                            candidate.index_rank,
                            candidate.target_id
               ) - 1,
               candidate.target_kind,
               candidate.target_id,
               candidate.source_interface_id,
               candidate.structural_distance,
               candidate.index_rank,
               candidate.candidate_score
          FROM LATERAL (
              SELECT DISTINCT ON (global.target_kind, global.target_id)
                     global.target_kind,
                     global.target_id,
                     global.interface_id AS source_interface_id,
                     abs(
                         COALESCE(demand_row.source_start_char, 0)
                         - global.region_end_char
                     ) AS structural_distance,
                     global.rank AS index_rank,
                     COALESCE(object.promotion_score, factor.support_score, 0)
                         AS candidate_score
                FROM execution.semantic_pnf_global_lookup AS global
                LEFT JOIN execution.semantic_pnf_object AS object
                  ON global.target_kind = 1
                 AND object.object_id = global.target_id
                LEFT JOIN execution.semantic_pnf_factor AS factor
                  ON global.target_kind = 2
                 AND factor.factor_id = global.target_id
               WHERE global.run_ref = selected_run_ref
                 AND global.document_ref = selected_document_ref
                 AND global.target_kind = demand_row.expected_target_kind
                 AND global.target_id <> demand_row.demand_id
                 AND (
                     (
                         demand_row.residual_type_symbol_id = anaphor_residual_id
                         AND global.target_kind = 1
                         AND global.region_id <> demand_row.source_region_id
                         AND (
                             pronoun_kind_id IS NULL
                             OR object.object_kind_symbol_id <> pronoun_kind_id
                         )
                         AND global.region_end_char
                             <= COALESCE(
                                 demand_row.source_start_char,
                                 global.region_end_char
                             )
                     )
                     OR (
                         demand_row.expected_factor_type_symbol_id IS NOT NULL
                         AND global.key_kind = 1
                         AND global.key_a
                             = demand_row.expected_factor_type_symbol_id
                     )
                     OR (
                         demand_row.expected_object_kind_symbol_id IS NOT NULL
                         AND global.key_kind = 2
                         AND global.key_a
                             = demand_row.expected_object_kind_symbol_id
                     )
                     OR (
                         demand_row.lexical_symbol_id IS NOT NULL
                         AND global.key_kind = 3
                         AND global.key_a = demand_row.lexical_symbol_id
                     )
                     OR (
                         global.key_kind = 5
                         AND global.key_a
                             = demand_row.residual_type_symbol_id
                     )
                 )
               ORDER BY global.target_kind,
                        global.target_id,
                        structural_distance,
                        global.rank
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

CREATE OR REPLACE FUNCTION execution.plan_demands_after_global_lookup_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected RECORD;
BEGIN
    FOR selected IN
        SELECT DISTINCT run_ref, document_ref
          FROM inserted_global
    LOOP
        PERFORM execution.plan_numeric_pnf_demand_candidates(
            selected.run_ref,
            selected.document_ref
        );
    END LOOP;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_global_demand_planning
    ON execution.semantic_pnf_global_lookup;
CREATE TRIGGER semantic_pnf_global_demand_planning
AFTER INSERT ON execution.semantic_pnf_global_lookup
REFERENCING NEW TABLE AS inserted_global
FOR EACH STATEMENT
EXECUTE FUNCTION execution.plan_demands_after_global_lookup_refresh();

COMMIT;
