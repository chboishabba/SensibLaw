BEGIN;

-- Sparse fibred frontiers ----------------------------------------------------
--
-- Closed child interiors are never searched globally.  A parent interface
-- contains only:
--   * promoted identity/rule exports;
--   * compressed actor/action summaries;
--   * unresolved typed demands; and
--   * explicit definition/scope exports.
--
-- Parent closure is deterministic and set based.  Global lookup is rebuilt
-- from the closed document frontier only.

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_scope_class (
    scope_class SMALLINT PRIMARY KEY,
    scope_name TEXT NOT NULL UNIQUE
);
INSERT INTO execution.semantic_pnf_scope_class (scope_class, scope_name)
VALUES
    (1, 'local'),
    (2, 'sibling'),
    (3, 'paragraph'),
    (4, 'section'),
    (5, 'document'),
    (6, 'external'),
    (7, 'explicit')
ON CONFLICT (scope_class) DO UPDATE SET scope_name = EXCLUDED.scope_name;

ALTER TABLE execution.semantic_pnf_interface_export
    ADD COLUMN IF NOT EXISTS scope_class SMALLINT NOT NULL DEFAULT 1
        REFERENCES execution.semantic_pnf_scope_class(scope_class)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS origin_interface_id BIGINT
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS outward_required BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE execution.semantic_pnf_interface_export
   SET origin_interface_id = interface_id
 WHERE origin_interface_id IS NULL;

CREATE INDEX IF NOT EXISTS semantic_pnf_interface_export_frontier_idx
    ON execution.semantic_pnf_interface_export
       (interface_id, target_kind, key_symbol_id, role_symbol_id,
        residual_type_symbol_id, scope_class, rank, target_id);

-- A demand is a typed hole, not an invitation to scan every object.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_demand_constraint (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    ordinal SMALLINT NOT NULL CHECK (ordinal BETWEEN 0 AND 31),
    key_kind SMALLINT NOT NULL CHECK (key_kind BETWEEN 1 AND 7),
    key_a BIGINT NOT NULL,
    key_b BIGINT NOT NULL DEFAULT 0,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    polarity SMALLINT NOT NULL DEFAULT 1 CHECK (polarity IN (-1, 0, 1)),
    PRIMARY KEY (demand_id, ordinal),
    UNIQUE (demand_id, key_kind, key_a, key_b, polarity)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_demand_constraint_join_idx
    ON execution.semantic_pnf_demand_constraint
       (key_kind, key_a, key_b, polarity, demand_id);

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_demand_constraints()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_demand_constraint
     WHERE demand_id = NEW.demand_id;

    INSERT INTO execution.semantic_pnf_demand_constraint
        (demand_id, ordinal, key_kind, key_a, key_b, required, polarity)
    SELECT NEW.demand_id,
           row_number() OVER (ORDER BY key_kind, key_a, key_b)::SMALLINT - 1,
           key_kind,
           key_a,
           key_b,
           TRUE,
           1
      FROM (
          SELECT 1::SMALLINT AS key_kind,
                 NEW.expected_factor_type_symbol_id AS key_a,
                 0::BIGINT AS key_b
           WHERE NEW.expected_factor_type_symbol_id IS NOT NULL
          UNION ALL
          SELECT 2::SMALLINT,
                 NEW.expected_object_kind_symbol_id,
                 0::BIGINT
           WHERE NEW.expected_object_kind_symbol_id IS NOT NULL
          UNION ALL
          SELECT 3::SMALLINT,
                 NEW.lexical_symbol_id,
                 0::BIGINT
           WHERE NEW.lexical_symbol_id IS NOT NULL
          UNION ALL
          SELECT 4::SMALLINT,
                 NEW.role_symbol_id,
                 0::BIGINT
           WHERE NEW.role_symbol_id IS NOT NULL
          UNION ALL
          SELECT 5::SMALLINT,
                 NEW.residual_type_symbol_id,
                 0::BIGINT
           WHERE NEW.residual_type_symbol_id IS NOT NULL
      ) AS constraints
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_demand_constraints
    ON execution.semantic_pnf_demand;
CREATE TRIGGER semantic_pnf_demand_constraints
AFTER INSERT OR UPDATE OF
    expected_factor_type_symbol_id,
    expected_object_kind_symbol_id,
    lexical_symbol_id,
    role_symbol_id,
    residual_type_symbol_id
ON execution.semantic_pnf_demand
FOR EACH ROW
EXECUTE FUNCTION execution.refresh_numeric_pnf_demand_constraints();

-- Backfill upgraded databases.
INSERT INTO execution.semantic_pnf_demand_constraint
    (demand_id, ordinal, key_kind, key_a, key_b, required, polarity)
SELECT demand_id,
       row_number() OVER (
           PARTITION BY demand_id
           ORDER BY key_kind, key_a, key_b
       )::SMALLINT - 1,
       key_kind,
       key_a,
       key_b,
       TRUE,
       1
  FROM (
      SELECT demand.demand_id,
             1::SMALLINT AS key_kind,
             demand.expected_factor_type_symbol_id AS key_a,
             0::BIGINT AS key_b
        FROM execution.semantic_pnf_demand AS demand
       WHERE demand.expected_factor_type_symbol_id IS NOT NULL
      UNION ALL
      SELECT demand.demand_id, 2::SMALLINT,
             demand.expected_object_kind_symbol_id, 0::BIGINT
        FROM execution.semantic_pnf_demand AS demand
       WHERE demand.expected_object_kind_symbol_id IS NOT NULL
      UNION ALL
      SELECT demand.demand_id, 3::SMALLINT,
             demand.lexical_symbol_id, 0::BIGINT
        FROM execution.semantic_pnf_demand AS demand
       WHERE demand.lexical_symbol_id IS NOT NULL
      UNION ALL
      SELECT demand.demand_id, 4::SMALLINT,
             demand.role_symbol_id, 0::BIGINT
        FROM execution.semantic_pnf_demand AS demand
       WHERE demand.role_symbol_id IS NOT NULL
      UNION ALL
      SELECT demand.demand_id, 5::SMALLINT,
             demand.residual_type_symbol_id, 0::BIGINT
        FROM execution.semantic_pnf_demand AS demand
       WHERE demand.residual_type_symbol_id IS NOT NULL
  ) AS existing
ON CONFLICT DO NOTHING;

-- Compressed actor fibres: enough relational evidence to answer a typed actor
-- demand without reopening the child graph.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_actor_profile (
    interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE CASCADE,
    object_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_object(object_id)
        ON DELETE CASCADE,
    object_kind_symbol_id BIGINT
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT,
    role_symbol_id BIGINT
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT,
    factor_type_symbol_id BIGINT
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT,
    predicate_symbol_id BIGINT
        REFERENCES execution.semantic_symbol(symbol_id)
        ON DELETE RESTRICT,
    occurrence_count BIGINT NOT NULL DEFAULT 1
        CHECK (occurrence_count > 0),
    first_start_char BIGINT NOT NULL CHECK (first_start_char >= 0),
    last_end_char BIGINT NOT NULL CHECK (last_end_char >= first_start_char),
    promotion_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (
        interface_id, object_id, role_symbol_id,
        factor_type_symbol_id, predicate_symbol_id
    )
);
CREATE INDEX IF NOT EXISTS semantic_pnf_actor_profile_demand_idx
    ON execution.semantic_pnf_actor_profile
       (interface_id, object_kind_symbol_id, role_symbol_id,
        factor_type_symbol_id, predicate_symbol_id,
        last_end_char DESC, promotion_score DESC, object_id);

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_frontier_outcome (
    outcome_state SMALLINT PRIMARY KEY,
    outcome_name TEXT NOT NULL UNIQUE
);
INSERT INTO execution.semantic_pnf_frontier_outcome
    (outcome_state, outcome_name)
VALUES
    (1, 'no_witness'),
    (2, 'resolved_unique'),
    (3, 'ambiguous'),
    (4, 'generic'),
    (5, 'plural'),
    (6, 'inapplicable'),
    (7, 'deferred_world')
ON CONFLICT (outcome_state) DO UPDATE
SET outcome_name = EXCLUDED.outcome_name;

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_frontier_resolution (
    demand_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_demand(demand_id) ON DELETE CASCADE,
    interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE CASCADE,
    outcome_state SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_frontier_outcome(outcome_state)
        ON DELETE RESTRICT,
    candidate_count SMALLINT NOT NULL DEFAULT 0
        CHECK (candidate_count BETWEEN 0 AND 256),
    selected_target_kind SMALLINT,
    selected_target_id BIGINT,
    witness_interface_id BIGINT
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (demand_id, interface_id)
);

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_frontier_reduction_receipt (
    interface_id BIGINT PRIMARY KEY
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE CASCADE,
    graph_revision BIGINT NOT NULL,
    child_interface_count BIGINT NOT NULL,
    input_export_count BIGINT NOT NULL,
    output_export_count BIGINT NOT NULL,
    actor_profile_count BIGINT NOT NULL,
    unresolved_demand_count BIGINT NOT NULL,
    resolved_demand_count BIGINT NOT NULL,
    elapsed_ms DOUBLE PRECISION NOT NULL CHECK (elapsed_ms >= 0),
    reduced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_frontier_stage_receipt (
    run_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_run_identity(run_id)
        ON DELETE CASCADE,
    document_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_document_identity(document_id)
        ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    row_count BIGINT NOT NULL DEFAULT 0,
    elapsed_ms DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (elapsed_ms >= 0),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, document_id, stage_name)
);

-- The old row trigger performs several queries for every copied export.  Parent
-- reduction below is one bounded set operation per closed interface.
DROP TRIGGER IF EXISTS semantic_pnf_parent_export_promotion
    ON execution.semantic_pnf_interface_export;

-- Demand planning must never be launched invisibly by a broad lookup insert.
DROP TRIGGER IF EXISTS semantic_pnf_global_demand_planning
    ON execution.semantic_pnf_global_lookup;
DROP TRIGGER IF EXISTS semantic_pnf_visible_demand_planning
    ON execution.semantic_pnf_visible_lookup;

CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier(
    selected_interface_id BIGINT
)
RETURNS TABLE (
    output_export_count BIGINT,
    unresolved_demand_count BIGINT,
    resolved_demand_count BIGINT,
    actor_profile_count BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_region_id BIGINT;
    selected_region_kind SMALLINT;
    selected_graph_revision BIGINT;
    selected_scope_class SMALLINT;
    threshold_value DOUBLE PRECISION;
    started_at TIMESTAMPTZ := clock_timestamp();
    child_count_value BIGINT := 0;
    input_count_value BIGINT := 0;
    output_count_value BIGINT := 0;
    unresolved_count_value BIGINT := 0;
    resolved_count_value BIGINT := 0;
    actor_count_value BIGINT := 0;
BEGIN
    SELECT interface.region_id,
           region.region_kind,
           interface.graph_revision,
           CASE
               WHEN region.region_kind <= 1 THEN 1
               WHEN region.region_kind <= 2 THEN 2
               WHEN region.region_kind <= 5 THEN 3
               WHEN region.region_kind <= 8 THEN 4
               WHEN region.region_kind = 10 THEN 5
               ELSE 6
           END::SMALLINT,
           profile.promotion_threshold
               + (0.25 * GREATEST(region.region_kind - 1, 0))
      INTO selected_region_id,
           selected_region_kind,
           selected_graph_revision,
           selected_scope_class,
           threshold_value
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
      CROSS JOIN execution.semantic_pnf_mdl_profile AS profile
     WHERE interface.interface_id = selected_interface_id
       AND profile.profile_id = 1;

    IF selected_region_id IS NULL THEN
        RAISE EXCEPTION 'numeric PNF interface % disappeared',
            selected_interface_id;
    END IF;

    IF selected_region_kind = 1 THEN
        SELECT count(*) INTO output_count_value
          FROM execution.semantic_pnf_interface_export
         WHERE interface_id = selected_interface_id;
        SELECT count(*) INTO unresolved_count_value
          FROM execution.semantic_pnf_interface_export AS export
          JOIN execution.semantic_pnf_demand AS demand
            ON export.target_kind = 3
           AND demand.demand_id = export.target_id
         WHERE export.interface_id = selected_interface_id
           AND demand.state IN (1, 3);
        output_export_count := output_count_value;
        unresolved_demand_count := unresolved_count_value;
        resolved_demand_count := 0;
        actor_profile_count := 0;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT count(*),
           COALESCE(sum(child_counts.export_count), 0)
      INTO child_count_value, input_count_value
      FROM (
          SELECT child_interface.interface_id,
                 count(child_export.target_id) AS export_count
            FROM execution.semantic_pnf_region AS child_region
            JOIN execution.semantic_pnf_interface AS child_interface
              ON child_interface.region_id = child_region.region_id
            LEFT JOIN execution.semantic_pnf_interface_export AS child_export
              ON child_export.interface_id = child_interface.interface_id
           WHERE child_region.parent_region_id = selected_region_id
             AND child_region.region_kind <> 9
           GROUP BY child_interface.interface_id
      ) AS child_counts;

    DELETE FROM execution.semantic_pnf_interface_lookup
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_interface_export
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_actor_profile
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_frontier_resolution
     WHERE interface_id = selected_interface_id;

    -- Aggregate already-compressed child actor fibres plus direct child factor
    -- participation.  No child proposition graph is copied.
    WITH child_interface AS (
        SELECT child_interface.interface_id
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
         WHERE child_region.parent_region_id = selected_region_id
           AND child_region.region_kind <> 9
    ),
    profile_source AS (
        SELECT profile.object_id,
               profile.object_kind_symbol_id,
               profile.role_symbol_id,
               profile.factor_type_symbol_id,
               profile.predicate_symbol_id,
               profile.occurrence_count,
               profile.first_start_char,
               profile.last_end_char,
               profile.promotion_score
          FROM child_interface
          JOIN execution.semantic_pnf_actor_profile AS profile
            ON profile.interface_id = child_interface.interface_id
        UNION ALL
        SELECT object.object_id,
               object.object_kind_symbol_id,
               edge.role_symbol_id,
               factor.factor_type_symbol_id,
               factor.predicate_symbol_id,
               1::BIGINT,
               factor_region.start_char,
               factor_region.end_char,
               object.promotion_score
          FROM child_interface
          JOIN execution.semantic_pnf_interface_export AS factor_export
            ON factor_export.interface_id = child_interface.interface_id
           AND factor_export.target_kind = 2
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = factor_export.target_id
          JOIN execution.semantic_pnf_region AS factor_region
            ON factor_region.region_id = factor.region_id
          JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.factor_id = factor.factor_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = edge.object_id
    )
    INSERT INTO execution.semantic_pnf_actor_profile
        (interface_id, object_id, object_kind_symbol_id,
         role_symbol_id, factor_type_symbol_id, predicate_symbol_id,
         occurrence_count, first_start_char, last_end_char, promotion_score)
    SELECT selected_interface_id,
           source.object_id,
           source.object_kind_symbol_id,
           source.role_symbol_id,
           source.factor_type_symbol_id,
           source.predicate_symbol_id,
           sum(source.occurrence_count),
           min(source.first_start_char),
           max(source.last_end_char),
           max(source.promotion_score)
      FROM profile_source AS source
     GROUP BY source.object_id,
              source.object_kind_symbol_id,
              source.role_symbol_id,
              source.factor_type_symbol_id,
              source.predicate_symbol_id
    ON CONFLICT (
        interface_id, object_id, role_symbol_id,
        factor_type_symbol_id, predicate_symbol_id
    ) DO UPDATE SET
        occurrence_count =
            execution.semantic_pnf_actor_profile.occurrence_count
            + EXCLUDED.occurrence_count,
        first_start_char = LEAST(
            execution.semantic_pnf_actor_profile.first_start_char,
            EXCLUDED.first_start_char
        ),
        last_end_char = GREATEST(
            execution.semantic_pnf_actor_profile.last_end_char,
            EXCLUDED.last_end_char
        ),
        promotion_score = GREATEST(
            execution.semantic_pnf_actor_profile.promotion_score,
            EXCLUDED.promotion_score
        );

    -- Keep a one-off low-salience actor summary only when an unresolved typed
    -- demand can actually ask for it at this boundary.
    DELETE FROM execution.semantic_pnf_actor_profile AS profile
     WHERE profile.interface_id = selected_interface_id
       AND profile.promotion_score < COALESCE(threshold_value, 0)
       AND profile.occurrence_count < 2
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_region AS child_region
             JOIN execution.semantic_pnf_interface AS child_interface
               ON child_interface.region_id = child_region.region_id
             JOIN execution.semantic_pnf_interface_export AS demand_export
               ON demand_export.interface_id = child_interface.interface_id
              AND demand_export.target_kind = 3
             JOIN execution.semantic_pnf_demand AS demand
               ON demand.demand_id = demand_export.target_id
            WHERE child_region.parent_region_id = selected_region_id
              AND demand.state IN (1, 3)
              AND demand.expected_target_kind = 1
              AND (
                  demand.expected_object_kind_symbol_id IS NULL
                  OR demand.expected_object_kind_symbol_id
                     = profile.object_kind_symbol_id
              )
              AND (
                  demand.role_symbol_id IS NULL
                  OR demand.role_symbol_id = profile.role_symbol_id
              )
              AND (
                  demand.expected_factor_type_symbol_id IS NULL
                  OR demand.expected_factor_type_symbol_id
                     = profile.factor_type_symbol_id
              )
       );

    -- Unresolved holes always cross the boundary.  Resolved demands disappear.
    WITH child_interface AS (
        SELECT child_interface.interface_id
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
         WHERE child_region.parent_region_id = selected_region_id
           AND child_region.region_kind <> 9
    )
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT selected_interface_id,
           5,
           3,
           demand.demand_id,
           demand.lexical_symbol_id,
           demand.role_symbol_id,
           demand.residual_type_symbol_id,
           min(child_export.rank),
           0,
           GREATEST(
               selected_scope_class,
               max(child_export.scope_class)
           )::SMALLINT,
           min(COALESCE(
               child_export.origin_interface_id,
               child_export.interface_id
           )),
           TRUE
      FROM child_interface
      JOIN execution.semantic_pnf_interface_export AS child_export
        ON child_export.interface_id = child_interface.interface_id
       AND child_export.target_kind = 3
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = child_export.target_id
     WHERE demand.state IN (1, 3)
     GROUP BY demand.demand_id,
              demand.lexical_symbol_id,
              demand.role_symbol_id,
              demand.residual_type_symbol_id
    ON CONFLICT DO NOTHING;

    -- Definitions, scopes, bindings, temporal and modal declarations are
    -- explicitly outward-facing.
    WITH child_interface AS (
        SELECT child_interface.interface_id
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
         WHERE child_region.parent_region_id = selected_region_id
           AND child_region.region_kind <> 9
    )
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT selected_interface_id,
           child_export.export_kind,
           child_export.target_kind,
           child_export.target_id,
           child_export.key_symbol_id,
           child_export.role_symbol_id,
           child_export.residual_type_symbol_id,
           min(child_export.rank),
           max(child_export.promotion_score),
           GREATEST(
               selected_scope_class,
               max(child_export.scope_class)
           )::SMALLINT,
           min(COALESCE(
               child_export.origin_interface_id,
               child_export.interface_id
           )),
           bool_or(child_export.outward_required)
      FROM child_interface
      JOIN execution.semantic_pnf_interface_export AS child_export
        ON child_export.interface_id = child_interface.interface_id
     WHERE child_export.target_kind IN (4, 5)
        OR child_export.export_kind IN (3, 4, 6, 7, 8)
     GROUP BY child_export.export_kind,
              child_export.target_kind,
              child_export.target_id,
              child_export.key_symbol_id,
              child_export.role_symbol_id,
              child_export.residual_type_symbol_id
    ON CONFLICT DO NOTHING;

    -- Concrete actors survive only when salient, recurrent, already selected,
    -- or represented by a retained actor fibre.
    WITH child_interface AS (
        SELECT child_interface.interface_id
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
         WHERE child_region.parent_region_id = selected_region_id
           AND child_region.region_kind <> 9
    ),
    child_object AS (
        SELECT child_export.target_id,
               child_export.key_symbol_id,
               min(child_export.rank) AS rank,
               max(child_export.promotion_score) AS promotion_score,
               count(DISTINCT child_export.interface_id) AS child_occurrences,
               min(COALESCE(
                   child_export.origin_interface_id,
                   child_export.interface_id
               )) AS origin_interface_id
          FROM child_interface
          JOIN execution.semantic_pnf_interface_export AS child_export
            ON child_export.interface_id = child_interface.interface_id
           AND child_export.target_kind = 1
         GROUP BY child_export.target_id, child_export.key_symbol_id
    )
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, rank, promotion_score,
         scope_class, origin_interface_id, outward_required)
    SELECT selected_interface_id,
           1,
           1,
           candidate.target_id,
           candidate.key_symbol_id,
           candidate.rank,
           candidate.promotion_score,
           selected_scope_class,
           candidate.origin_interface_id,
           EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_actor_profile AS profile
                WHERE profile.interface_id = selected_interface_id
                  AND profile.object_id = candidate.target_id
           )
      FROM child_object AS candidate
     WHERE candidate.promotion_score >= COALESCE(threshold_value, 0)
        OR candidate.child_occurrences >= 2
        OR EXISTS (
            SELECT 1
              FROM execution.semantic_pnf_actor_profile AS profile
             WHERE profile.interface_id = selected_interface_id
               AND profile.object_id = candidate.target_id
        )
        OR EXISTS (
            SELECT 1
              FROM execution.semantic_pnf_demand AS demand
             WHERE demand.state = 2
               AND demand.resolved_target_kind = 1
               AND demand.resolved_target_id = candidate.target_id
        )
    ON CONFLICT DO NOTHING;

    -- Full factors are exceptional at a boundary; actor/action summaries carry
    -- ordinary relational evidence.
    WITH child_interface AS (
        SELECT child_interface.interface_id
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
         WHERE child_region.parent_region_id = selected_region_id
           AND child_region.region_kind <> 9
    ),
    child_factor AS (
        SELECT child_export.target_id,
               child_export.key_symbol_id,
               min(child_export.rank) AS rank,
               min(COALESCE(
                   child_export.origin_interface_id,
                   child_export.interface_id
               )) AS origin_interface_id
          FROM child_interface
          JOIN execution.semantic_pnf_interface_export AS child_export
            ON child_export.interface_id = child_interface.interface_id
           AND child_export.target_kind = 2
         GROUP BY child_export.target_id, child_export.key_symbol_id
    )
    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, rank, promotion_score,
         scope_class, origin_interface_id, outward_required)
    SELECT selected_interface_id,
           2,
           2,
           candidate.target_id,
           candidate.key_symbol_id,
           candidate.rank,
           factor.support_score,
           selected_scope_class,
           candidate.origin_interface_id,
           FALSE
      FROM child_factor AS candidate
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = candidate.target_id
     WHERE factor.support_score >= COALESCE(threshold_value, 0)
        OR EXISTS (
            SELECT 1
              FROM execution.semantic_pnf_interface_export AS demand_export
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_id = demand_export.target_id
             WHERE demand_export.interface_id = selected_interface_id
               AND demand_export.target_kind = 3
               AND demand.expected_target_kind = 2
               AND (
                   demand.expected_factor_type_symbol_id IS NULL
                   OR demand.expected_factor_type_symbol_id
                      = factor.factor_type_symbol_id
               )
               AND (
                   demand.lexical_symbol_id IS NULL
                   OR demand.lexical_symbol_id = factor.predicate_symbol_id
               )
        )
    ON CONFLICT DO NOTHING;

    -- Rebuild the searchable projection only from admitted parent exports.
    WITH child_interface AS (
        SELECT child_interface.interface_id
          FROM execution.semantic_pnf_region AS child_region
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
         WHERE child_region.parent_region_id = selected_region_id
           AND child_region.region_kind <> 9
    )
    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT selected_interface_id,
           child_lookup.key_kind,
           child_lookup.key_a,
           child_lookup.key_b,
           child_lookup.target_kind,
           child_lookup.target_id,
           min(child_lookup.rank)
      FROM child_interface
      JOIN execution.semantic_pnf_interface_lookup AS child_lookup
        ON child_lookup.interface_id = child_interface.interface_id
      JOIN execution.semantic_pnf_interface_export AS parent_export
        ON parent_export.interface_id = selected_interface_id
       AND parent_export.target_kind = child_lookup.target_kind
       AND parent_export.target_id = child_lookup.target_id
     GROUP BY child_lookup.key_kind,
              child_lookup.key_a,
              child_lookup.key_b,
              child_lookup.target_kind,
              child_lookup.target_id
    ON CONFLICT DO NOTHING;

    -- Solve only the exported typed holes against this one compressed parent
    -- frontier.  Unique witnesses bind; ambiguity remains explicit.
    DELETE FROM execution.semantic_pnf_demand_candidate AS candidate
     WHERE EXISTS (
         SELECT 1
           FROM execution.semantic_pnf_interface_export AS demand_export
          WHERE demand_export.interface_id = selected_interface_id
            AND demand_export.target_kind = 3
            AND demand_export.target_id = candidate.demand_id
     );

    WITH parent_demand AS (
        SELECT demand.*,
               COALESCE(demand.source_start_char, source_region.end_char)
                   AS demand_position,
               source_region.start_char AS source_region_start,
               source_region.end_char AS source_region_end,
               source_region.parent_region_id AS source_parent_region_id
          FROM execution.semantic_pnf_interface_export AS demand_export
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = demand_export.target_id
          JOIN execution.semantic_pnf_region AS source_region
            ON source_region.region_id = demand.source_region_id
         WHERE demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand.state IN (1, 3)
    ),
    object_candidate AS (
        SELECT demand.demand_id,
               1::SMALLINT AS target_kind,
               profile.object_id AS target_id,
               selected_interface_id AS source_interface_id,
               abs(demand.demand_position - profile.last_end_char)
                   AS structural_distance,
               0::BIGINT AS index_rank,
               profile.promotion_score
                   + ln(1 + profile.occurrence_count)::DOUBLE PRECISION
                   AS candidate_score
          FROM parent_demand AS demand
          JOIN execution.semantic_pnf_actor_profile AS profile
            ON profile.interface_id = selected_interface_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = profile.object_id
         WHERE demand.expected_target_kind = 1
           AND (
               demand.expected_object_kind_symbol_id IS NULL
               OR demand.expected_object_kind_symbol_id
                  = profile.object_kind_symbol_id
           )
           AND (
               demand.role_symbol_id IS NULL
               OR demand.role_symbol_id = profile.role_symbol_id
           )
           AND (
               demand.expected_factor_type_symbol_id IS NULL
               OR demand.expected_factor_type_symbol_id
                  = profile.factor_type_symbol_id
           )
           AND (
               demand.lexical_symbol_id IS NULL
               OR demand.lexical_symbol_id = object.head_symbol_id
               OR demand.lexical_symbol_id = profile.predicate_symbol_id
           )
           AND CASE demand.recency_class
               WHEN 1 THEN
                   profile.first_start_char >= demand.source_region_start
                   AND profile.last_end_char <= demand.source_region_end
               WHEN 2 THEN
                   profile.last_end_char <= demand.demand_position
               WHEN 3 THEN
                   profile.last_end_char <= demand.demand_position
               WHEN 4 THEN TRUE
               WHEN 5 THEN TRUE
               ELSE FALSE
           END
    ),
    factor_candidate AS (
        SELECT demand.demand_id,
               2::SMALLINT AS target_kind,
               factor.factor_id AS target_id,
               selected_interface_id AS source_interface_id,
               abs(demand.demand_position - factor_region.end_char)
                   AS structural_distance,
               factor_export.rank AS index_rank,
               factor.support_score AS candidate_score
          FROM parent_demand AS demand
          JOIN execution.semantic_pnf_interface_export AS factor_export
            ON factor_export.interface_id = selected_interface_id
           AND factor_export.target_kind = 2
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = factor_export.target_id
          JOIN execution.semantic_pnf_region AS factor_region
            ON factor_region.region_id = factor.region_id
         WHERE demand.expected_target_kind = 2
           AND (
               demand.expected_factor_type_symbol_id IS NULL
               OR demand.expected_factor_type_symbol_id
                  = factor.factor_type_symbol_id
           )
           AND (
               demand.lexical_symbol_id IS NULL
               OR demand.lexical_symbol_id = factor.predicate_symbol_id
           )
           AND (
               demand.recency_class IN (4, 5)
               OR factor_region.end_char <= demand.demand_position
           )
    ),
    raw_candidate AS (
        SELECT * FROM object_candidate
        UNION ALL
        SELECT * FROM factor_candidate
    ),
    deduplicated AS (
        SELECT candidate.*,
               row_number() OVER (
                   PARTITION BY candidate.demand_id,
                                candidate.target_kind,
                                candidate.target_id
                   ORDER BY candidate.structural_distance,
                            candidate.index_rank,
                            candidate.source_interface_id
               ) AS target_occurrence
          FROM raw_candidate AS candidate
    ),
    ranked AS (
        SELECT candidate.*,
               row_number() OVER (
                   PARTITION BY candidate.demand_id
                   ORDER BY candidate.structural_distance,
                            candidate.candidate_score DESC,
                            candidate.index_rank,
                            candidate.target_id
               ) - 1 AS candidate_ordinal
          FROM deduplicated AS candidate
         WHERE candidate.target_occurrence = 1
    )
    INSERT INTO execution.semantic_pnf_demand_candidate
        (demand_id, ordinal, target_kind, target_id,
         source_interface_id, ancestor_distance,
         index_rank, candidate_score,
         common_scope_interface_id, validation_state)
    SELECT ranked.demand_id,
           ranked.candidate_ordinal::SMALLINT,
           ranked.target_kind,
           ranked.target_id,
           ranked.source_interface_id,
           ranked.structural_distance,
           ranked.index_rank,
           ranked.candidate_score,
           selected_interface_id,
           2
      FROM ranked
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = ranked.demand_id
     WHERE ranked.candidate_ordinal < demand.max_candidates
     ORDER BY ranked.demand_id, ranked.candidate_ordinal
    ON CONFLICT DO NOTHING;

    WITH parent_demand AS (
        SELECT demand.demand_id
          FROM execution.semantic_pnf_interface_export AS demand_export
          JOIN execution.semantic_pnf_demand AS demand
            ON demand.demand_id = demand_export.target_id
         WHERE demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand.state IN (1, 3)
    ),
    counts AS (
        SELECT parent_demand.demand_id,
               count(candidate.demand_id)::SMALLINT AS candidate_count
          FROM parent_demand
          LEFT JOIN execution.semantic_pnf_demand_candidate AS candidate
            ON candidate.demand_id = parent_demand.demand_id
         GROUP BY parent_demand.demand_id
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET candidate_count = counts.candidate_count,
           state = CASE
               WHEN demand.state = 3 AND counts.candidate_count > 0 THEN 1
               ELSE demand.state
           END
      FROM counts
     WHERE demand.demand_id = counts.demand_id;

    WITH unique_candidate AS (
        SELECT candidate.demand_id,
               min(candidate.target_kind) AS target_kind,
               min(candidate.target_id) AS target_id,
               min(candidate.source_interface_id) AS source_interface_id
          FROM execution.semantic_pnf_demand_candidate AS candidate
          JOIN execution.semantic_pnf_interface_export AS demand_export
            ON demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand_export.target_id = candidate.demand_id
         GROUP BY candidate.demand_id
        HAVING count(*) = 1
    )
    UPDATE execution.semantic_pnf_demand AS demand
       SET state = 2,
           resolved_target_kind = unique_candidate.target_kind,
           resolved_target_id = unique_candidate.target_id,
           candidate_count = 1
      FROM unique_candidate
     WHERE demand.demand_id = unique_candidate.demand_id
       AND demand.state IN (1, 3);

    INSERT INTO execution.semantic_pnf_frontier_resolution
        (demand_id, interface_id, outcome_state, candidate_count,
         selected_target_kind, selected_target_id, witness_interface_id)
    SELECT demand.demand_id,
           selected_interface_id,
           CASE
               WHEN demand.state = 2 THEN 2
               WHEN demand.candidate_count = 0
                    AND selected_region_kind = 10 THEN 7
               WHEN demand.candidate_count = 0 THEN 1
               ELSE 3
           END,
           demand.candidate_count,
           demand.resolved_target_kind,
           demand.resolved_target_id,
           CASE
               WHEN demand.state = 2 THEN selected_interface_id
               ELSE NULL
           END
      FROM execution.semantic_pnf_interface_export AS demand_export
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = demand_export.target_id
     WHERE demand_export.interface_id = selected_interface_id
       AND demand_export.target_kind = 3
    ON CONFLICT (demand_id, interface_id) DO UPDATE SET
        outcome_state = EXCLUDED.outcome_state,
        candidate_count = EXCLUDED.candidate_count,
        selected_target_kind = EXCLUDED.selected_target_kind,
        selected_target_id = EXCLUDED.selected_target_id,
        witness_interface_id = EXCLUDED.witness_interface_id,
        created_at = CURRENT_TIMESTAMP;

    IF selected_region_kind = 10 THEN
        UPDATE execution.semantic_pnf_demand AS demand
           SET state = 3
          FROM execution.semantic_pnf_interface_export AS demand_export
         WHERE demand_export.interface_id = selected_interface_id
           AND demand_export.target_kind = 3
           AND demand.demand_id = demand_export.target_id
           AND demand.state = 1
           AND demand.candidate_count = 0;
    END IF;

    DELETE FROM execution.semantic_pnf_interface_export AS demand_export
    USING execution.semantic_pnf_demand AS demand
     WHERE demand_export.interface_id = selected_interface_id
       AND demand_export.target_kind = 3
       AND demand.demand_id = demand_export.target_id
       AND demand.state = 2;

    DELETE FROM execution.semantic_pnf_interface_lookup AS lookup
     WHERE lookup.interface_id = selected_interface_id
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_interface_export AS export
            WHERE export.interface_id = lookup.interface_id
              AND export.target_kind = lookup.target_kind
              AND export.target_id = lookup.target_id
       );

    SELECT count(*),
           count(*) FILTER (WHERE export.target_kind = 3)
      INTO output_count_value, unresolved_count_value
      FROM execution.semantic_pnf_interface_export AS export
     WHERE export.interface_id = selected_interface_id;

    SELECT count(*) INTO resolved_count_value
      FROM execution.semantic_pnf_frontier_resolution
     WHERE interface_id = selected_interface_id
       AND outcome_state = 2;

    SELECT count(*) INTO actor_count_value
      FROM execution.semantic_pnf_actor_profile
     WHERE interface_id = selected_interface_id;

    UPDATE execution.semantic_pnf_interface AS interface
       SET interface_cardinality = output_count_value,
           promoted_object_count = (
               SELECT count(*)
                 FROM execution.semantic_pnf_interface_export
                WHERE interface_id = selected_interface_id
                  AND target_kind = 1
           ),
           unresolved_count = unresolved_count_value,
           boundary_demand_weight = unresolved_count_value::DOUBLE PRECISION,
           node_count = output_count_value,
           encoded_byte_count = output_count_value * 64,
           interface_digest = digest(
               convert_to(
                   concat_ws(
                       '|',
                       selected_region_id::TEXT,
                       selected_graph_revision::TEXT,
                       output_count_value::TEXT,
                       unresolved_count_value::TEXT,
                       COALESCE((
                           SELECT string_agg(
                               concat_ws(
                                   ':',
                                   export.export_kind::TEXT,
                                   export.target_kind::TEXT,
                                   export.target_id::TEXT,
                                   COALESCE(export.key_symbol_id, 0)::TEXT,
                                   COALESCE(export.role_symbol_id, 0)::TEXT,
                                   COALESCE(
                                       export.residual_type_symbol_id,
                                       0
                                   )::TEXT
                               ),
                               ',' ORDER BY
                                   export.export_kind,
                                   export.target_kind,
                                   export.target_id
                           )
                             FROM execution.semantic_pnf_interface_export
                                AS export
                            WHERE export.interface_id
                                  = selected_interface_id
                       ), '')
                   ),
                   'UTF8'
               ),
               'sha256'
           )
     WHERE interface.interface_id = selected_interface_id;

    INSERT INTO execution.semantic_pnf_frontier_reduction_receipt
        (interface_id, graph_revision, child_interface_count,
         input_export_count, output_export_count, actor_profile_count,
         unresolved_demand_count, resolved_demand_count, elapsed_ms)
    VALUES (
        selected_interface_id,
        selected_graph_revision,
        child_count_value,
        input_count_value,
        output_count_value,
        actor_count_value,
        unresolved_count_value,
        resolved_count_value,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (interface_id) DO UPDATE SET
        graph_revision = EXCLUDED.graph_revision,
        child_interface_count = EXCLUDED.child_interface_count,
        input_export_count = EXCLUDED.input_export_count,
        output_export_count = EXCLUDED.output_export_count,
        actor_profile_count = EXCLUDED.actor_profile_count,
        unresolved_demand_count = EXCLUDED.unresolved_demand_count,
        resolved_demand_count = EXCLUDED.resolved_demand_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        reduced_at = CURRENT_TIMESTAMP;

    output_export_count := output_count_value;
    unresolved_demand_count := unresolved_count_value;
    resolved_demand_count := resolved_count_value;
    actor_profile_count := actor_count_value;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_interface_on_close()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_interface_id BIGINT;
BEGIN
    IF NEW.closure_state NOT IN (2, 3)
       OR OLD.closure_state IS NOT DISTINCT FROM NEW.closure_state THEN
        RETURN NEW;
    END IF;

    SELECT interface_id
      INTO selected_interface_id
      FROM execution.semantic_pnf_interface
     WHERE region_id = NEW.region_id;

    IF selected_interface_id IS NOT NULL THEN
        PERFORM *
          FROM execution.rebuild_numeric_pnf_parent_frontier(
              selected_interface_id
          );
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_sparse_frontier_on_close
    ON execution.semantic_pnf_region;
CREATE TRIGGER semantic_pnf_sparse_frontier_on_close
AFTER UPDATE OF closure_state
ON execution.semantic_pnf_region
FOR EACH ROW
EXECUTE FUNCTION execution.reduce_numeric_pnf_interface_on_close();

CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_document_frontiers(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected RECORD;
    reduced_count BIGINT := 0;
    selected_run_id BIGINT;
    selected_document_id BIGINT;
    started_at TIMESTAMPTZ := clock_timestamp();
BEGIN
    SELECT run_id INTO selected_run_id
      FROM execution.semantic_pnf_run_identity
     WHERE run_ref = selected_run_ref;
    SELECT document_id INTO selected_document_id
      FROM execution.semantic_pnf_document_identity
     WHERE document_ref = selected_document_ref;

    FOR selected IN
        SELECT interface.interface_id
          FROM execution.semantic_pnf_interface AS interface
          JOIN execution.semantic_pnf_region AS region
            ON region.region_id = interface.region_id
         WHERE region.run_ref = selected_run_ref
           AND region.document_ref = selected_document_ref
           AND region.region_kind IN (3, 5, 6, 7, 8, 10)
           AND interface.closure_state IN (2, 3)
         ORDER BY region.region_kind,
                  region.sequence_no,
                  interface.interface_id
    LOOP
        PERFORM *
          FROM execution.rebuild_numeric_pnf_parent_frontier(
              selected.interface_id
          );
        reduced_count := reduced_count + 1;
    END LOOP;

    INSERT INTO execution.semantic_pnf_frontier_stage_receipt
        (run_id, document_id, stage_name, row_count, elapsed_ms)
    VALUES (
        selected_run_id,
        selected_document_id,
        'sparse_frontier_reduction',
        reduced_count,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (run_id, document_id, stage_name) DO UPDATE SET
        row_count = EXCLUDED.row_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        completed_at = CURRENT_TIMESTAMP;

    RETURN reduced_count;
END;
$$;

-- Incremental, root-only global lookup.  Closed child interiors remain in
-- provenance tables and are never reintroduced into document-wide search.
CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup_ids(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    root_interface_id BIGINT;
    affected_count BIGINT := 0;
    inserted_count BIGINT := 0;
    started_at TIMESTAMPTZ := clock_timestamp();
BEGIN
    SELECT interface.interface_id
      INTO root_interface_id
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND region.region_kind = 10
       AND interface.closure_state IN (2, 3)
     LIMIT 1;

    IF root_interface_id IS NULL THEN
        RETURN 0;
    END IF;

    DELETE FROM execution.semantic_pnf_global_lookup AS global
     WHERE global.run_id = selected_run_id
       AND global.document_id = selected_document_id
       AND (
           global.interface_id <> root_interface_id
           OR NOT EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_interface_lookup AS lookup
                WHERE lookup.interface_id = root_interface_id
                  AND lookup.key_kind = global.key_kind
                  AND lookup.key_a = global.key_a
                  AND lookup.key_b = global.key_b
                  AND lookup.target_kind = global.target_kind
                  AND lookup.target_id = global.target_id
           )
       );
    GET DIAGNOSTICS affected_count = ROW_COUNT;

    INSERT INTO execution.semantic_pnf_global_lookup
        (run_ref, document_ref, run_id, document_id,
         interface_id, region_id, region_kind,
         region_start_char, region_end_char,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT region.run_ref,
           region.document_ref,
           region.run_id,
           region.document_id,
           root_interface_id,
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
        ON interface.interface_id = root_interface_id
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE lookup.interface_id = root_interface_id
    ON CONFLICT (
        interface_id, key_kind, key_a, key_b,
        target_kind, target_id
    ) DO UPDATE SET
        rank = EXCLUDED.rank,
        region_id = EXCLUDED.region_id,
        region_kind = EXCLUDED.region_kind,
        region_start_char = EXCLUDED.region_start_char,
        region_end_char = EXCLUDED.region_end_char,
        run_id = EXCLUDED.run_id,
        document_id = EXCLUDED.document_id,
        run_ref = EXCLUDED.run_ref,
        document_ref = EXCLUDED.document_ref;
    GET DIAGNOSTICS inserted_count = ROW_COUNT;

    INSERT INTO execution.semantic_pnf_frontier_stage_receipt
        (run_id, document_id, stage_name, row_count, elapsed_ms)
    VALUES (
        selected_run_id,
        selected_document_id,
        'root_global_lookup_refresh',
        inserted_count,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (run_id, document_id, stage_name) DO UPDATE SET
        row_count = EXCLUDED.row_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        completed_at = CURRENT_TIMESTAMP;

    RETURN inserted_count + affected_count;
END;
$$;

CREATE OR REPLACE FUNCTION execution.refresh_pnf_visible_lookup(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_run_id BIGINT;
    selected_document_id BIGINT;
    root_interface_id BIGINT;
    inserted_count BIGINT := 0;
    started_at TIMESTAMPTZ := clock_timestamp();
BEGIN
    PERFORM execution.reduce_numeric_pnf_document_frontiers(
        selected_run_ref,
        selected_document_ref
    );

    SELECT run_id INTO selected_run_id
      FROM execution.semantic_pnf_run_identity
     WHERE run_ref = selected_run_ref;
    SELECT document_id INTO selected_document_id
      FROM execution.semantic_pnf_document_identity
     WHERE document_ref = selected_document_ref;

    SELECT interface.interface_id
      INTO root_interface_id
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE region.run_id = selected_run_id
       AND region.document_id = selected_document_id
       AND region.region_kind = 10
       AND interface.closure_state IN (2, 3)
     LIMIT 1;

    DELETE FROM execution.semantic_pnf_visible_lookup AS visible
    USING execution.semantic_pnf_interface AS interface,
          execution.semantic_pnf_region AS region
    WHERE visible.interface_id = interface.interface_id
      AND interface.region_id = region.region_id
      AND region.run_id = selected_run_id
      AND region.document_id = selected_document_id;

    IF root_interface_id IS NOT NULL THEN
        INSERT INTO execution.semantic_pnf_visible_lookup
            (interface_id, key_kind, key_a, key_b,
             target_kind, target_id, source_interface_id,
             ancestor_distance, rank)
        SELECT root_interface_id,
               lookup.key_kind,
               lookup.key_a,
               lookup.key_b,
               lookup.target_kind,
               lookup.target_id,
               root_interface_id,
               0,
               lookup.rank
          FROM execution.semantic_pnf_interface_lookup AS lookup
         WHERE lookup.interface_id = root_interface_id
        ON CONFLICT DO NOTHING;
        GET DIAGNOSTICS inserted_count = ROW_COUNT;
    END IF;

    PERFORM execution.refresh_pnf_global_lookup_ids(
        selected_run_id,
        selected_document_id
    );

    INSERT INTO execution.semantic_pnf_frontier_stage_receipt
        (run_id, document_id, stage_name, row_count, elapsed_ms)
    VALUES (
        selected_run_id,
        selected_document_id,
        'root_visible_projection',
        inserted_count,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (run_id, document_id, stage_name) DO UPDATE SET
        row_count = EXCLUDED.row_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        completed_at = CURRENT_TIMESTAMP;

    RETURN inserted_count;
END;
$$;

-- Compatibility call surface: planning is now the explicit sparse-frontier
-- reduction.  It never scans the complete document object inventory.
CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates_ids(
    selected_run_id BIGINT,
    selected_document_id BIGINT
)
RETURNS BIGINT
LANGUAGE sql
AS $$
    SELECT execution.reduce_numeric_pnf_document_frontiers(
        (SELECT run_ref
           FROM execution.semantic_pnf_run_identity
          WHERE run_id = selected_run_id),
        (SELECT document_ref
           FROM execution.semantic_pnf_document_identity
          WHERE document_id = selected_document_id)
    )
$$;

COMMIT;
