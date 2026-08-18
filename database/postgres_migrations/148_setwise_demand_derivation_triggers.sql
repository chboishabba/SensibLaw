BEGIN;

-- 148: preserve demand-derived constraints and initial H3 scheduling while
-- avoiding one PL/pgSQL trigger invocation per demand row.
--
-- Both derivations are pure functions of the affected demand rows. PostgreSQL
-- transition tables therefore provide the exact active carrier for one
-- statement-level projection. This follows the established transition-table
-- pattern used by migration 066 for actor-profile capture.

DROP TRIGGER IF EXISTS semantic_pnf_demand_constraints
    ON execution.semantic_pnf_demand;
DROP TRIGGER IF EXISTS semantic_pnf_demand_seed_h3_work
    ON execution.semantic_pnf_demand;

CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_inserted_demand_derivations()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_demand_constraint
        (demand_id, ordinal, key_kind, key_a, key_b, required, polarity)
    SELECT demand.demand_id,
           row_number() OVER (
               PARTITION BY demand.demand_id
               ORDER BY coordinate.key_kind, coordinate.key_a, coordinate.key_b
           )::SMALLINT - 1,
           coordinate.key_kind,
           coordinate.key_a,
           coordinate.key_b,
           TRUE,
           1
      FROM inserted_demand AS demand
      CROSS JOIN LATERAL (
          VALUES
              (1::SMALLINT, demand.expected_factor_type_symbol_id, 0::BIGINT),
              (2::SMALLINT, demand.expected_object_kind_symbol_id, 0::BIGINT),
              (3::SMALLINT, demand.lexical_symbol_id, 0::BIGINT),
              (4::SMALLINT, demand.role_symbol_id, 0::BIGINT),
              (5::SMALLINT, demand.residual_type_symbol_id, 0::BIGINT)
      ) AS coordinate(key_kind, key_a, key_b)
     WHERE coordinate.key_a IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_horizon_work_queue(demand_id, horizon)
    SELECT demand_id, 3
      FROM inserted_demand
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_insert_derivations
AFTER INSERT ON execution.semantic_pnf_demand
REFERENCING NEW TABLE AS inserted_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_inserted_demand_derivations();

-- UPDATE transition tables cannot be combined with an UPDATE OF column list.
-- Filter the transition relation explicitly so state-only updates do not
-- rebuild constraint rows. This preserves the old trigger's field-sensitive
-- behavior while keeping the work set-wise.
CREATE OR REPLACE FUNCTION execution.project_numeric_pnf_updated_demand_constraints()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    WITH changed AS (
        SELECT current.*
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING (demand_id)
         WHERE current.expected_factor_type_symbol_id
                   IS DISTINCT FROM prior.expected_factor_type_symbol_id
            OR current.expected_object_kind_symbol_id
                   IS DISTINCT FROM prior.expected_object_kind_symbol_id
            OR current.lexical_symbol_id
                   IS DISTINCT FROM prior.lexical_symbol_id
            OR current.role_symbol_id
                   IS DISTINCT FROM prior.role_symbol_id
            OR current.residual_type_symbol_id
                   IS DISTINCT FROM prior.residual_type_symbol_id
    )
    DELETE FROM execution.semantic_pnf_demand_constraint AS constraint_row
     USING changed
     WHERE constraint_row.demand_id = changed.demand_id;

    WITH changed AS (
        SELECT current.*
          FROM updated_demand AS current
          JOIN prior_demand AS prior USING (demand_id)
         WHERE current.expected_factor_type_symbol_id
                   IS DISTINCT FROM prior.expected_factor_type_symbol_id
            OR current.expected_object_kind_symbol_id
                   IS DISTINCT FROM prior.expected_object_kind_symbol_id
            OR current.lexical_symbol_id
                   IS DISTINCT FROM prior.lexical_symbol_id
            OR current.role_symbol_id
                   IS DISTINCT FROM prior.role_symbol_id
            OR current.residual_type_symbol_id
                   IS DISTINCT FROM prior.residual_type_symbol_id
    )
    INSERT INTO execution.semantic_pnf_demand_constraint
        (demand_id, ordinal, key_kind, key_a, key_b, required, polarity)
    SELECT demand.demand_id,
           row_number() OVER (
               PARTITION BY demand.demand_id
               ORDER BY coordinate.key_kind, coordinate.key_a, coordinate.key_b
           )::SMALLINT - 1,
           coordinate.key_kind,
           coordinate.key_a,
           coordinate.key_b,
           TRUE,
           1
      FROM changed AS demand
      CROSS JOIN LATERAL (
          VALUES
              (1::SMALLINT, demand.expected_factor_type_symbol_id, 0::BIGINT),
              (2::SMALLINT, demand.expected_object_kind_symbol_id, 0::BIGINT),
              (3::SMALLINT, demand.lexical_symbol_id, 0::BIGINT),
              (4::SMALLINT, demand.role_symbol_id, 0::BIGINT),
              (5::SMALLINT, demand.residual_type_symbol_id, 0::BIGINT)
      ) AS coordinate(key_kind, key_a, key_b)
     WHERE coordinate.key_a IS NOT NULL
    ON CONFLICT DO NOTHING;

    RETURN NULL;
END;
$$;

CREATE TRIGGER semantic_pnf_demand_update_constraints
AFTER UPDATE ON execution.semantic_pnf_demand
REFERENCING OLD TABLE AS prior_demand NEW TABLE AS updated_demand
FOR EACH STATEMENT
EXECUTE FUNCTION execution.project_numeric_pnf_updated_demand_constraints();

COMMIT;
