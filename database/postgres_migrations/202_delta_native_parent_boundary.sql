BEGIN;

-- C3b: the transported child boundary becomes a semantically complete parent
-- input carrier.  The earlier C2/C3a projection intentionally carried only
-- export identity/rank information; that was sufficient for parity experiments
-- but not sufficient to become canonical because SparseFibredFrontier also
-- requires explicit scope/provenance/outwardness and actor/action summaries.
ALTER TABLE execution.semantic_pnf_parent_delta_projection
    ADD COLUMN IF NOT EXISTS scope_class SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS origin_interface_id BIGINT,
    ADD COLUMN IF NOT EXISTS outward_required BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE execution.semantic_pnf_parent_delta_projection AS projection
   SET scope_class = source.scope_class,
       origin_interface_id = source.origin_interface_id,
       outward_required = source.outward_required
  FROM execution.semantic_pnf_interface_export AS source
 WHERE source.interface_id = projection.child_interface_id
   AND source.export_kind = projection.export_kind
   AND source.target_kind = projection.target_kind
   AND source.target_id = projection.target_id
   AND source.key_symbol_id IS NOT DISTINCT FROM projection.key_symbol_id
   AND source.role_symbol_id IS NOT DISTINCT FROM projection.role_symbol_id
   AND source.residual_type_symbol_id IS NOT DISTINCT FROM projection.residual_type_symbol_id;

CREATE OR REPLACE VIEW execution.semantic_pnf_parent_delta_fused_export AS
SELECT parent_region_id,
       export_kind,
       target_kind,
       target_id,
       min(key_symbol_id) AS key_symbol_id,
       min(role_symbol_id) AS role_symbol_id,
       min(residual_type_symbol_id) AS residual_type_symbol_id,
       min(rank) AS rank,
       max(promotion_score) AS promotion_score,
       count(*) AS contributing_child_count,
       max(scope_class)::SMALLINT AS scope_class,
       min(COALESCE(origin_interface_id, child_interface_id))
           AS origin_interface_id,
       bool_or(outward_required) AS outward_required
  FROM execution.semantic_pnf_parent_delta_projection
 GROUP BY parent_region_id, export_kind, target_kind, target_id;

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_export_delta_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_delta_projection
        (parent_region_id, child_region_id, child_interface_id,
         export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT child.parent_region_id,
           child.region_id,
           inserted.interface_id,
           inserted.export_kind,
           inserted.target_kind,
           inserted.target_id,
           inserted.key_symbol_id,
           inserted.role_symbol_id,
           inserted.residual_type_symbol_id,
           inserted.rank,
           inserted.promotion_score,
           inserted.scope_class,
           inserted.origin_interface_id,
           inserted.outward_required
      FROM inserted_export AS inserted
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = inserted.interface_id
      JOIN execution.semantic_pnf_region AS child
        ON child.region_id = interface.region_id
     WHERE child.parent_region_id IS NOT NULL
       AND child.region_kind <> 9
    ON CONFLICT (
        parent_region_id, child_interface_id,
        export_kind, target_kind, target_id
    ) DO UPDATE SET
        child_region_id = EXCLUDED.child_region_id,
        key_symbol_id = EXCLUDED.key_symbol_id,
        role_symbol_id = EXCLUDED.role_symbol_id,
        residual_type_symbol_id = EXCLUDED.residual_type_symbol_id,
        rank = EXCLUDED.rank,
        promotion_score = EXCLUDED.promotion_score,
        scope_class = EXCLUDED.scope_class,
        origin_interface_id = EXCLUDED.origin_interface_id,
        outward_required = EXCLUDED.outward_required;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_export_delta_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_parent_delta_projection AS projection
    USING old_export AS old_row
     WHERE projection.child_interface_id = old_row.interface_id
       AND projection.export_kind = old_row.export_kind
       AND projection.target_kind = old_row.target_kind
       AND projection.target_id = old_row.target_id;

    INSERT INTO execution.semantic_pnf_parent_delta_projection
        (parent_region_id, child_region_id, child_interface_id,
         export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT child.parent_region_id,
           child.region_id,
           new_row.interface_id,
           new_row.export_kind,
           new_row.target_kind,
           new_row.target_id,
           new_row.key_symbol_id,
           new_row.role_symbol_id,
           new_row.residual_type_symbol_id,
           new_row.rank,
           new_row.promotion_score,
           new_row.scope_class,
           new_row.origin_interface_id,
           new_row.outward_required
      FROM new_export AS new_row
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = new_row.interface_id
      JOIN execution.semantic_pnf_region AS child
        ON child.region_id = interface.region_id
     WHERE child.parent_region_id IS NOT NULL
       AND child.region_kind <> 9
    ON CONFLICT (
        parent_region_id, child_interface_id,
        export_kind, target_kind, target_id
    ) DO UPDATE SET
        child_region_id = EXCLUDED.child_region_id,
        key_symbol_id = EXCLUDED.key_symbol_id,
        role_symbol_id = EXCLUDED.role_symbol_id,
        residual_type_symbol_id = EXCLUDED.residual_type_symbol_id,
        rank = EXCLUDED.rank,
        promotion_score = EXCLUDED.promotion_score,
        scope_class = EXCLUDED.scope_class,
        origin_interface_id = EXCLUDED.origin_interface_id,
        outward_required = EXCLUDED.outward_required;
    RETURN NULL;
END;
$$;

-- Actor/action summaries are a first-class sparse boundary carrier, separate
-- from promoted exports.  Transport them independently instead of reopening
-- the child proposition graph at every parent reduction.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_parent_actor_delta_projection (
    parent_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    child_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    child_interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    object_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_object(object_id) ON DELETE CASCADE,
    object_kind_symbol_id BIGINT,
    role_symbol_id BIGINT NOT NULL,
    factor_type_symbol_id BIGINT NOT NULL,
    predicate_symbol_id BIGINT NOT NULL,
    occurrence_count BIGINT NOT NULL CHECK (occurrence_count > 0),
    first_start_char BIGINT NOT NULL,
    last_end_char BIGINT NOT NULL,
    promotion_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (
        parent_region_id, child_interface_id, object_id,
        role_symbol_id, factor_type_symbol_id, predicate_symbol_id
    )
);
CREATE INDEX IF NOT EXISTS semantic_pnf_parent_actor_delta_parent_idx
    ON execution.semantic_pnf_parent_actor_delta_projection
       (parent_region_id, object_kind_symbol_id, role_symbol_id,
        factor_type_symbol_id, predicate_symbol_id, object_id);

INSERT INTO execution.semantic_pnf_parent_actor_delta_projection
    (parent_region_id, child_region_id, child_interface_id,
     object_id, object_kind_symbol_id, role_symbol_id,
     factor_type_symbol_id, predicate_symbol_id,
     occurrence_count, first_start_char, last_end_char, promotion_score)
SELECT child.parent_region_id,
       child.region_id,
       profile.interface_id,
       profile.object_id,
       profile.object_kind_symbol_id,
       profile.role_symbol_id,
       profile.factor_type_symbol_id,
       profile.predicate_symbol_id,
       profile.occurrence_count,
       profile.first_start_char,
       profile.last_end_char,
       profile.promotion_score
  FROM execution.semantic_pnf_actor_profile AS profile
  JOIN execution.semantic_pnf_interface AS interface
    ON interface.interface_id = profile.interface_id
  JOIN execution.semantic_pnf_region AS child
    ON child.region_id = interface.region_id
 WHERE child.parent_region_id IS NOT NULL
   AND child.region_kind <> 9
ON CONFLICT (
    parent_region_id, child_interface_id, object_id,
    role_symbol_id, factor_type_symbol_id, predicate_symbol_id
) DO UPDATE SET
    child_region_id = EXCLUDED.child_region_id,
    object_kind_symbol_id = EXCLUDED.object_kind_symbol_id,
    occurrence_count = EXCLUDED.occurrence_count,
    first_start_char = EXCLUDED.first_start_char,
    last_end_char = EXCLUDED.last_end_char,
    promotion_score = EXCLUDED.promotion_score;

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_actor_delta_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_actor_delta_projection
        (parent_region_id, child_region_id, child_interface_id,
         object_id, object_kind_symbol_id, role_symbol_id,
         factor_type_symbol_id, predicate_symbol_id,
         occurrence_count, first_start_char, last_end_char, promotion_score)
    SELECT child.parent_region_id,
           child.region_id,
           inserted.interface_id,
           inserted.object_id,
           inserted.object_kind_symbol_id,
           inserted.role_symbol_id,
           inserted.factor_type_symbol_id,
           inserted.predicate_symbol_id,
           inserted.occurrence_count,
           inserted.first_start_char,
           inserted.last_end_char,
           inserted.promotion_score
      FROM inserted_profile AS inserted
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = inserted.interface_id
      JOIN execution.semantic_pnf_region AS child
        ON child.region_id = interface.region_id
     WHERE child.parent_region_id IS NOT NULL
       AND child.region_kind <> 9
    ON CONFLICT (
        parent_region_id, child_interface_id, object_id,
        role_symbol_id, factor_type_symbol_id, predicate_symbol_id
    ) DO UPDATE SET
        child_region_id = EXCLUDED.child_region_id,
        object_kind_symbol_id = EXCLUDED.object_kind_symbol_id,
        occurrence_count = EXCLUDED.occurrence_count,
        first_start_char = EXCLUDED.first_start_char,
        last_end_char = EXCLUDED.last_end_char,
        promotion_score = EXCLUDED.promotion_score;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_actor_delta_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_parent_actor_delta_projection AS projection
    USING deleted_profile AS deleted
     WHERE projection.child_interface_id = deleted.interface_id
       AND projection.object_id = deleted.object_id
       AND projection.role_symbol_id = deleted.role_symbol_id
       AND projection.factor_type_symbol_id = deleted.factor_type_symbol_id
       AND projection.predicate_symbol_id = deleted.predicate_symbol_id;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_actor_delta_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_parent_actor_delta_projection AS projection
    USING old_profile AS old_row
     WHERE projection.child_interface_id = old_row.interface_id
       AND projection.object_id = old_row.object_id
       AND projection.role_symbol_id = old_row.role_symbol_id
       AND projection.factor_type_symbol_id = old_row.factor_type_symbol_id
       AND projection.predicate_symbol_id = old_row.predicate_symbol_id;

    INSERT INTO execution.semantic_pnf_parent_actor_delta_projection
        (parent_region_id, child_region_id, child_interface_id,
         object_id, object_kind_symbol_id, role_symbol_id,
         factor_type_symbol_id, predicate_symbol_id,
         occurrence_count, first_start_char, last_end_char, promotion_score)
    SELECT child.parent_region_id,
           child.region_id,
           new_row.interface_id,
           new_row.object_id,
           new_row.object_kind_symbol_id,
           new_row.role_symbol_id,
           new_row.factor_type_symbol_id,
           new_row.predicate_symbol_id,
           new_row.occurrence_count,
           new_row.first_start_char,
           new_row.last_end_char,
           new_row.promotion_score
      FROM new_profile AS new_row
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = new_row.interface_id
      JOIN execution.semantic_pnf_region AS child
        ON child.region_id = interface.region_id
     WHERE child.parent_region_id IS NOT NULL
       AND child.region_kind <> 9
    ON CONFLICT (
        parent_region_id, child_interface_id, object_id,
        role_symbol_id, factor_type_symbol_id, predicate_symbol_id
    ) DO UPDATE SET
        child_region_id = EXCLUDED.child_region_id,
        object_kind_symbol_id = EXCLUDED.object_kind_symbol_id,
        occurrence_count = EXCLUDED.occurrence_count,
        first_start_char = EXCLUDED.first_start_char,
        last_end_char = EXCLUDED.last_end_char,
        promotion_score = EXCLUDED.promotion_score;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_actor_delta_insert
    ON execution.semantic_pnf_actor_profile;
CREATE TRIGGER semantic_pnf_parent_actor_delta_insert
AFTER INSERT ON execution.semantic_pnf_actor_profile
REFERENCING NEW TABLE AS inserted_profile
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_actor_delta_insert();

DROP TRIGGER IF EXISTS semantic_pnf_parent_actor_delta_delete
    ON execution.semantic_pnf_actor_profile;
CREATE TRIGGER semantic_pnf_parent_actor_delta_delete
AFTER DELETE ON execution.semantic_pnf_actor_profile
REFERENCING OLD TABLE AS deleted_profile
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_actor_delta_delete();

DROP TRIGGER IF EXISTS semantic_pnf_parent_actor_delta_update
    ON execution.semantic_pnf_actor_profile;
CREATE TRIGGER semantic_pnf_parent_actor_delta_update
AFTER UPDATE ON execution.semantic_pnf_actor_profile
REFERENCING OLD TABLE AS old_profile NEW TABLE AS new_profile
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_actor_delta_update();

-- Reparenting is pure transport for both boundary carrier classes.
CREATE OR REPLACE FUNCTION execution.rehome_numeric_pnf_parent_delta_projection()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.parent_region_id IS NOT DISTINCT FROM NEW.parent_region_id THEN
        RETURN NEW;
    END IF;

    IF NEW.parent_region_id IS NULL OR NEW.region_kind = 9 THEN
        DELETE FROM execution.semantic_pnf_parent_delta_projection
         WHERE child_region_id = NEW.region_id;
        DELETE FROM execution.semantic_pnf_parent_actor_delta_projection
         WHERE child_region_id = NEW.region_id;
    ELSE
        UPDATE execution.semantic_pnf_parent_delta_projection
           SET parent_region_id = NEW.parent_region_id
         WHERE child_region_id = NEW.region_id;
        UPDATE execution.semantic_pnf_parent_actor_delta_projection
           SET parent_region_id = NEW.parent_region_id
         WHERE child_region_id = NEW.region_id;
    END IF;
    RETURN NEW;
END;
$$;

-- Affected parent keys survive deletes as dirty tombstones.  The five families
-- correspond exactly to the Agda AffectedBoundaryKeys split.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_parent_affected_key (
    parent_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    key_family SMALLINT NOT NULL CHECK (key_family BETWEEN 1 AND 5),
    key_a BIGINT NOT NULL,
    key_b BIGINT NOT NULL DEFAULT 0,
    key_c BIGINT NOT NULL DEFAULT 0,
    change_count BIGINT NOT NULL DEFAULT 1,
    dirty_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (parent_region_id, key_family, key_a, key_b, key_c)
);
CREATE INDEX IF NOT EXISTS semantic_pnf_parent_affected_key_dirty_idx
    ON execution.semantic_pnf_parent_affected_key
       (parent_region_id, key_family, dirty_at, key_a, key_b, key_c);

CREATE OR REPLACE FUNCTION execution.mark_numeric_pnf_export_keys_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT row.parent_region_id,
           CASE row.target_kind
               WHEN 1 THEN 1
               WHEN 2 THEN 2
               WHEN 3 THEN 3
               ELSE 5
           END::SMALLINT,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN row.target_id ELSE row.export_kind END,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN 0 ELSE row.target_kind END,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN 0 ELSE row.target_id END
      FROM inserted_projection AS row
    ON CONFLICT (parent_region_id, key_family, key_a, key_b, key_c)
    DO UPDATE SET
        change_count = execution.semantic_pnf_parent_affected_key.change_count + 1,
        dirty_at = CURRENT_TIMESTAMP;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.mark_numeric_pnf_export_keys_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT row.parent_region_id,
           CASE row.target_kind
               WHEN 1 THEN 1
               WHEN 2 THEN 2
               WHEN 3 THEN 3
               ELSE 5
           END::SMALLINT,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN row.target_id ELSE row.export_kind END,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN 0 ELSE row.target_kind END,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN 0 ELSE row.target_id END
      FROM deleted_projection AS row
    ON CONFLICT (parent_region_id, key_family, key_a, key_b, key_c)
    DO UPDATE SET
        change_count = execution.semantic_pnf_parent_affected_key.change_count + 1,
        dirty_at = CURRENT_TIMESTAMP;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.mark_numeric_pnf_export_keys_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT row.parent_region_id,
           CASE row.target_kind
               WHEN 1 THEN 1
               WHEN 2 THEN 2
               WHEN 3 THEN 3
               ELSE 5
           END::SMALLINT,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN row.target_id ELSE row.export_kind END,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN 0 ELSE row.target_kind END,
           CASE WHEN row.target_kind IN (1, 2, 3)
                THEN 0 ELSE row.target_id END
      FROM (
          SELECT * FROM old_projection
          UNION ALL
          SELECT * FROM new_projection
      ) AS row
    ON CONFLICT (parent_region_id, key_family, key_a, key_b, key_c)
    DO UPDATE SET
        change_count = execution.semantic_pnf_parent_affected_key.change_count + 1,
        dirty_at = CURRENT_TIMESTAMP;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_affected_export_insert
    ON execution.semantic_pnf_parent_delta_projection;
CREATE TRIGGER semantic_pnf_parent_affected_export_insert
AFTER INSERT ON execution.semantic_pnf_parent_delta_projection
REFERENCING NEW TABLE AS inserted_projection
FOR EACH STATEMENT
EXECUTE FUNCTION execution.mark_numeric_pnf_export_keys_insert();

DROP TRIGGER IF EXISTS semantic_pnf_parent_affected_export_delete
    ON execution.semantic_pnf_parent_delta_projection;
CREATE TRIGGER semantic_pnf_parent_affected_export_delete
AFTER DELETE ON execution.semantic_pnf_parent_delta_projection
REFERENCING OLD TABLE AS deleted_projection
FOR EACH STATEMENT
EXECUTE FUNCTION execution.mark_numeric_pnf_export_keys_delete();

DROP TRIGGER IF EXISTS semantic_pnf_parent_affected_export_update
    ON execution.semantic_pnf_parent_delta_projection;
CREATE TRIGGER semantic_pnf_parent_affected_export_update
AFTER UPDATE ON execution.semantic_pnf_parent_delta_projection
REFERENCING OLD TABLE AS old_projection NEW TABLE AS new_projection
FOR EACH STATEMENT
EXECUTE FUNCTION execution.mark_numeric_pnf_export_keys_update();

CREATE OR REPLACE FUNCTION execution.mark_numeric_pnf_actor_keys_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT parent_region_id,
           4,
           object_id,
           COALESCE(role_symbol_id, 0),
           COALESCE(factor_type_symbol_id, 0)
      FROM inserted_actor
    ON CONFLICT (parent_region_id, key_family, key_a, key_b, key_c)
    DO UPDATE SET
        change_count = execution.semantic_pnf_parent_affected_key.change_count + 1,
        dirty_at = CURRENT_TIMESTAMP;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.mark_numeric_pnf_actor_keys_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT parent_region_id,
           4,
           object_id,
           COALESCE(role_symbol_id, 0),
           COALESCE(factor_type_symbol_id, 0)
      FROM deleted_actor
    ON CONFLICT (parent_region_id, key_family, key_a, key_b, key_c)
    DO UPDATE SET
        change_count = execution.semantic_pnf_parent_affected_key.change_count + 1,
        dirty_at = CURRENT_TIMESTAMP;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION execution.mark_numeric_pnf_actor_keys_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_affected_key
        (parent_region_id, key_family, key_a, key_b, key_c)
    SELECT parent_region_id,
           4,
           object_id,
           COALESCE(role_symbol_id, 0),
           COALESCE(factor_type_symbol_id, 0)
      FROM (
          SELECT * FROM old_actor
          UNION ALL
          SELECT * FROM new_actor
      ) AS changed
    ON CONFLICT (parent_region_id, key_family, key_a, key_b, key_c)
    DO UPDATE SET
        change_count = execution.semantic_pnf_parent_affected_key.change_count + 1,
        dirty_at = CURRENT_TIMESTAMP;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_affected_actor_insert
    ON execution.semantic_pnf_parent_actor_delta_projection;
CREATE TRIGGER semantic_pnf_parent_affected_actor_insert
AFTER INSERT ON execution.semantic_pnf_parent_actor_delta_projection
REFERENCING NEW TABLE AS inserted_actor
FOR EACH STATEMENT
EXECUTE FUNCTION execution.mark_numeric_pnf_actor_keys_insert();

DROP TRIGGER IF EXISTS semantic_pnf_parent_affected_actor_delete
    ON execution.semantic_pnf_parent_actor_delta_projection;
CREATE TRIGGER semantic_pnf_parent_affected_actor_delete
AFTER DELETE ON execution.semantic_pnf_parent_actor_delta_projection
REFERENCING OLD TABLE AS deleted_actor
FOR EACH STATEMENT
EXECUTE FUNCTION execution.mark_numeric_pnf_actor_keys_delete();

DROP TRIGGER IF EXISTS semantic_pnf_parent_affected_actor_update
    ON execution.semantic_pnf_parent_actor_delta_projection;
CREATE TRIGGER semantic_pnf_parent_affected_actor_update
AFTER UPDATE ON execution.semantic_pnf_parent_actor_delta_projection
REFERENCING OLD TABLE AS old_actor NEW TABLE AS new_actor
FOR EACH STATEMENT
EXECUTE FUNCTION execution.mark_numeric_pnf_actor_keys_update();

-- Existing rows predate the dirty-key triggers.  Seed every current boundary
-- fibre once so the first reduction has an exact cold work set.
INSERT INTO execution.semantic_pnf_parent_affected_key
    (parent_region_id, key_family, key_a, key_b, key_c)
SELECT parent_region_id,
       CASE target_kind WHEN 1 THEN 1 WHEN 2 THEN 2 WHEN 3 THEN 3 ELSE 5 END,
       CASE WHEN target_kind IN (1, 2, 3) THEN target_id ELSE export_kind END,
       CASE WHEN target_kind IN (1, 2, 3) THEN 0 ELSE target_kind END,
       CASE WHEN target_kind IN (1, 2, 3) THEN 0 ELSE target_id END
  FROM execution.semantic_pnf_parent_delta_projection
ON CONFLICT DO NOTHING;

INSERT INTO execution.semantic_pnf_parent_affected_key
    (parent_region_id, key_family, key_a, key_b, key_c)
SELECT parent_region_id,
       4,
       object_id,
       COALESCE(role_symbol_id, 0),
       COALESCE(factor_type_symbol_id, 0)
  FROM execution.semantic_pnf_parent_actor_delta_projection
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_delta_native_parent_work_receipt (
    interface_id BIGINT PRIMARY KEY
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    parent_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    input_delta_atoms BIGINT NOT NULL,
    accumulated_boundary_keys BIGINT NOT NULL,
    touched_boundary_keys BIGINT NOT NULL,
    object_keys_touched BIGINT NOT NULL,
    factor_keys_touched BIGINT NOT NULL,
    demand_keys_touched BIGINT NOT NULL,
    actor_keys_touched BIGINT NOT NULL,
    outward_keys_touched BIGINT NOT NULL,
    emitted_parent_deltas BIGINT NOT NULL,
    hierarchy_depth BIGINT NOT NULL,
    cold_build BOOLEAN NOT NULL,
    output_export_count BIGINT NOT NULL,
    unresolved_demand_count BIGINT NOT NULL,
    resolved_demand_count BIGINT NOT NULL,
    actor_profile_count BIGINT NOT NULL,
    elapsed_ms DOUBLE PRECISION NOT NULL CHECK (elapsed_ms >= 0),
    reduced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Cold/reference reduction over the transported parent-local carrier.  This
-- preserves the established sparse-frontier semantics while removing repeated
-- child region -> interface -> export discovery from the hot hierarchy path.
CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier_delta_input(
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
        RAISE EXCEPTION 'numeric PNF interface % disappeared', selected_interface_id;
    END IF;

    IF selected_region_kind = 1 THEN
        RETURN QUERY
        SELECT count(*)::BIGINT,
               count(*) FILTER (WHERE export.target_kind = 3)::BIGINT,
               0::BIGINT,
               0::BIGINT
          FROM execution.semantic_pnf_interface_export AS export
         WHERE export.interface_id = selected_interface_id;
        RETURN;
    END IF;

    SELECT count(DISTINCT child_interface_id), count(*)
      INTO child_count_value, input_count_value
      FROM execution.semantic_pnf_parent_delta_projection
     WHERE parent_region_id = selected_region_id;

    DELETE FROM execution.semantic_pnf_interface_lookup
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_interface_export
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_actor_profile
     WHERE interface_id = selected_interface_id;
    DELETE FROM execution.semantic_pnf_frontier_resolution
     WHERE interface_id = selected_interface_id;

    WITH profile_source AS (
        SELECT projection.object_id,
               projection.object_kind_symbol_id,
               projection.role_symbol_id,
               projection.factor_type_symbol_id,
               projection.predicate_symbol_id,
               projection.occurrence_count,
               projection.first_start_char,
               projection.last_end_char,
               projection.promotion_score
          FROM execution.semantic_pnf_parent_actor_delta_projection AS projection
         WHERE projection.parent_region_id = selected_region_id
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
          FROM execution.semantic_pnf_parent_delta_projection AS factor_export
          JOIN execution.semantic_pnf_factor AS factor
            ON factor.factor_id = factor_export.target_id
          JOIN execution.semantic_pnf_region AS factor_region
            ON factor_region.region_id = factor.region_id
          JOIN execution.semantic_pnf_hyperedge AS edge
            ON edge.factor_id = factor.factor_id
          JOIN execution.semantic_pnf_object AS object
            ON object.object_id = edge.object_id
         WHERE factor_export.parent_region_id = selected_region_id
           AND factor_export.target_kind = 2
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
        occurrence_count = EXCLUDED.occurrence_count,
        first_start_char = EXCLUDED.first_start_char,
        last_end_char = EXCLUDED.last_end_char,
        promotion_score = EXCLUDED.promotion_score;

    DELETE FROM execution.semantic_pnf_actor_profile AS profile
     WHERE profile.interface_id = selected_interface_id
       AND profile.promotion_score < COALESCE(threshold_value, 0)
       AND profile.occurrence_count < 2
       AND NOT EXISTS (
           SELECT 1
             FROM execution.semantic_pnf_parent_delta_projection AS demand_export
             JOIN execution.semantic_pnf_demand AS demand
               ON demand.demand_id = demand_export.target_id
            WHERE demand_export.parent_region_id = selected_region_id
              AND demand_export.target_kind = 3
              AND demand.state IN (1, 3)
              AND demand.expected_target_kind = 1
              AND (
                  demand.expected_object_kind_symbol_id IS NULL
                  OR demand.expected_object_kind_symbol_id = profile.object_kind_symbol_id
              )
              AND (demand.role_symbol_id IS NULL OR demand.role_symbol_id = profile.role_symbol_id)
              AND (
                  demand.expected_factor_type_symbol_id IS NULL
                  OR demand.expected_factor_type_symbol_id = profile.factor_type_symbol_id
              )
       );

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
           min(boundary.rank),
           0,
           GREATEST(selected_scope_class, max(boundary.scope_class))::SMALLINT,
           min(COALESCE(boundary.origin_interface_id, boundary.child_interface_id)),
           TRUE
      FROM execution.semantic_pnf_parent_delta_projection AS boundary
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = boundary.target_id
     WHERE boundary.parent_region_id = selected_region_id
       AND boundary.target_kind = 3
       AND demand.state IN (1, 3)
     GROUP BY demand.demand_id,
              demand.lexical_symbol_id,
              demand.role_symbol_id,
              demand.residual_type_symbol_id
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT selected_interface_id,
           boundary.export_kind,
           boundary.target_kind,
           boundary.target_id,
           boundary.key_symbol_id,
           boundary.role_symbol_id,
           boundary.residual_type_symbol_id,
           min(boundary.rank),
           max(boundary.promotion_score),
           GREATEST(selected_scope_class, max(boundary.scope_class))::SMALLINT,
           min(COALESCE(boundary.origin_interface_id, boundary.child_interface_id)),
           bool_or(boundary.outward_required)
      FROM execution.semantic_pnf_parent_delta_projection AS boundary
     WHERE boundary.parent_region_id = selected_region_id
       AND (
           boundary.target_kind IN (4, 5)
           OR boundary.export_kind IN (3, 4, 6, 7, 8)
       )
     GROUP BY boundary.export_kind,
              boundary.target_kind,
              boundary.target_id,
              boundary.key_symbol_id,
              boundary.role_symbol_id,
              boundary.residual_type_symbol_id
    ON CONFLICT DO NOTHING;

    WITH child_object AS (
        SELECT boundary.target_id,
               boundary.key_symbol_id,
               min(boundary.rank) AS rank,
               max(boundary.promotion_score) AS promotion_score,
               count(DISTINCT boundary.child_interface_id) AS child_occurrences,
               min(COALESCE(boundary.origin_interface_id, boundary.child_interface_id))
                   AS origin_interface_id
          FROM execution.semantic_pnf_parent_delta_projection AS boundary
         WHERE boundary.parent_region_id = selected_region_id
           AND boundary.target_kind = 1
         GROUP BY boundary.target_id, boundary.key_symbol_id
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

    WITH child_factor AS (
        SELECT boundary.target_id,
               boundary.key_symbol_id,
               min(boundary.rank) AS rank,
               min(COALESCE(boundary.origin_interface_id, boundary.child_interface_id))
                   AS origin_interface_id
          FROM execution.semantic_pnf_parent_delta_projection AS boundary
         WHERE boundary.parent_region_id = selected_region_id
           AND boundary.target_kind = 2
         GROUP BY boundary.target_id, boundary.key_symbol_id
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
                   OR demand.expected_factor_type_symbol_id = factor.factor_type_symbol_id
               )
               AND (
                   demand.lexical_symbol_id IS NULL
                   OR demand.lexical_symbol_id = factor.predicate_symbol_id
               )
        )
    ON CONFLICT DO NOTHING;

    -- Lookup is derived from admitted parent exports, never transported as
    -- independent evidence.  Target metadata supplies the secondary keys.
    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT selected_interface_id, 3, export.key_symbol_id, 0,
           export.target_kind, export.target_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 1
       AND export.key_symbol_id IS NOT NULL
    UNION ALL
    SELECT selected_interface_id, 1, factor.factor_type_symbol_id, 0,
           2, factor.factor_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 2
    UNION ALL
    SELECT selected_interface_id, 3, factor.predicate_symbol_id, 0,
           2, factor.factor_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN execution.semantic_pnf_factor AS factor
        ON factor.factor_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 2
    UNION ALL
    SELECT selected_interface_id, 5, demand.residual_type_symbol_id,
           COALESCE(demand.expected_factor_type_symbol_id, 0),
           3, demand.demand_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 3
       AND demand.residual_type_symbol_id IS NOT NULL
    UNION ALL
    SELECT selected_interface_id, 3, demand.lexical_symbol_id,
           COALESCE(demand.residual_type_symbol_id, 0),
           3, demand.demand_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
      JOIN execution.semantic_pnf_demand AS demand
        ON demand.demand_id = export.target_id
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 3
       AND demand.lexical_symbol_id IS NOT NULL
    UNION ALL
    SELECT selected_interface_id, 6, export.key_symbol_id, 0,
           export.target_kind, export.target_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 4
       AND export.key_symbol_id IS NOT NULL
    UNION ALL
    SELECT selected_interface_id, 7, export.key_symbol_id, 0,
           export.target_kind, export.target_id, export.rank
      FROM execution.semantic_pnf_interface_export AS export
     WHERE export.interface_id = selected_interface_id
       AND export.target_kind = 5
       AND export.key_symbol_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    -- Demand solving is unchanged semantically; only the source frontier is now
    -- built from the transported boundary carrier.
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
               OR demand.expected_object_kind_symbol_id = profile.object_kind_symbol_id
           )
           AND (demand.role_symbol_id IS NULL OR demand.role_symbol_id = profile.role_symbol_id)
           AND (
               demand.expected_factor_type_symbol_id IS NULL
               OR demand.expected_factor_type_symbol_id = profile.factor_type_symbol_id
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
               WHEN 2 THEN profile.last_end_char <= demand.demand_position
               WHEN 3 THEN profile.last_end_char <= demand.demand_position
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
               OR demand.expected_factor_type_symbol_id = factor.factor_type_symbol_id
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
               WHEN demand.candidate_count = 0 AND selected_region_kind = 10 THEN 7
               WHEN demand.candidate_count = 0 THEN 1
               ELSE 3
           END,
           demand.candidate_count,
           demand.resolved_target_kind,
           demand.resolved_target_id,
           CASE WHEN demand.state = 2 THEN selected_interface_id ELSE NULL END
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

    SELECT count(*), count(*) FILTER (WHERE target_kind = 3)
      INTO output_count_value, unresolved_count_value
      FROM execution.semantic_pnf_interface_export
     WHERE interface_id = selected_interface_id;

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
                WHERE interface_id = selected_interface_id AND target_kind = 1
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
                                   ':', export.export_kind::TEXT,
                                   export.target_kind::TEXT,
                                   export.target_id::TEXT,
                                   COALESCE(export.key_symbol_id, 0)::TEXT,
                                   COALESCE(export.role_symbol_id, 0)::TEXT,
                                   COALESCE(export.residual_type_symbol_id, 0)::TEXT
                               ),
                               ',' ORDER BY export.export_kind,
                                            export.target_kind,
                                            export.target_id
                           )
                             FROM execution.semantic_pnf_interface_export AS export
                            WHERE export.interface_id = selected_interface_id
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
        0
    )
    ON CONFLICT (interface_id) DO UPDATE SET
        graph_revision = EXCLUDED.graph_revision,
        child_interface_count = EXCLUDED.child_interface_count,
        input_export_count = EXCLUDED.input_export_count,
        output_export_count = EXCLUDED.output_export_count,
        actor_profile_count = EXCLUDED.actor_profile_count,
        unresolved_demand_count = EXCLUDED.unresolved_demand_count,
        resolved_demand_count = EXCLUDED.resolved_demand_count,
        reduced_at = CURRENT_TIMESTAMP;

    output_export_count := output_count_value;
    unresolved_demand_count := unresolved_count_value;
    resolved_demand_count := resolved_count_value;
    actor_profile_count := actor_count_value;
    RETURN NEXT;
END;
$$;

-- Structural wrapper used by Python.  Cold construction consumes the complete
-- transported boundary directly.  Warm calls with no dirty key are true no-ops;
-- warm calls with dirty keys remain semantically exact by using the delta-input
-- rebuild while the key-local mutation kernel is certified against this oracle.
CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_parent_frontier_delta_native(
    selected_interface_id BIGINT,
    selected_hierarchy_depth BIGINT,
    selected_key_budget BIGINT
)
RETURNS TABLE (
    parent_region_id BIGINT,
    input_delta_atoms BIGINT,
    accumulated_boundary_keys BIGINT,
    touched_boundary_keys BIGINT,
    object_keys_touched BIGINT,
    factor_keys_touched BIGINT,
    demand_keys_touched BIGINT,
    actor_keys_touched BIGINT,
    outward_keys_touched BIGINT,
    emitted_parent_deltas BIGINT,
    hierarchy_depth BIGINT,
    cold_build BOOLEAN,
    output_export_count BIGINT,
    unresolved_demand_count BIGINT,
    resolved_demand_count BIGINT,
    actor_profile_count BIGINT,
    elapsed_ms DOUBLE PRECISION
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_region_id BIGINT;
    started_at TIMESTAMPTZ := clock_timestamp();
    cold_value BOOLEAN;
    input_atoms BIGINT;
    accumulated_keys BIGINT;
    touched BIGINT;
    object_keys BIGINT;
    factor_keys BIGINT;
    demand_keys BIGINT;
    actor_keys BIGINT;
    outward_keys BIGINT;
    output_value BIGINT;
    unresolved_value BIGINT;
    resolved_value BIGINT;
    actor_value BIGINT;
    emitted_value BIGINT;
BEGIN
    IF selected_hierarchy_depth < 0 OR selected_key_budget < 1 THEN
        RAISE EXCEPTION 'invalid delta-native hierarchy depth/key budget';
    END IF;

    SELECT region_id INTO selected_region_id
      FROM execution.semantic_pnf_interface
     WHERE interface_id = selected_interface_id;
    IF selected_region_id IS NULL THEN
        RAISE EXCEPTION 'numeric PNF interface % disappeared', selected_interface_id;
    END IF;

    cold_value := NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_frontier_reduction_receipt
         WHERE interface_id = selected_interface_id
    );

    SELECT
        (SELECT count(*)
           FROM execution.semantic_pnf_parent_delta_projection
          WHERE parent_region_id = selected_region_id)
        +
        (SELECT count(*)
           FROM execution.semantic_pnf_parent_actor_delta_projection
          WHERE parent_region_id = selected_region_id)
      INTO input_atoms;

    SELECT count(*) INTO accumulated_keys
      FROM (
          SELECT 1 AS family, target_id AS a, 0::BIGINT AS b, 0::BIGINT AS c
            FROM execution.semantic_pnf_parent_delta_projection
           WHERE parent_region_id = selected_region_id AND target_kind = 1
          UNION
          SELECT 2, target_id, 0, 0
            FROM execution.semantic_pnf_parent_delta_projection
           WHERE parent_region_id = selected_region_id AND target_kind = 2
          UNION
          SELECT 3, target_id, 0, 0
            FROM execution.semantic_pnf_parent_delta_projection
           WHERE parent_region_id = selected_region_id AND target_kind = 3
          UNION
          SELECT 4, object_id, COALESCE(role_symbol_id, 0),
                 COALESCE(factor_type_symbol_id, 0)
            FROM execution.semantic_pnf_parent_actor_delta_projection
           WHERE parent_region_id = selected_region_id
          UNION
          SELECT 5, export_kind, target_kind, target_id
            FROM execution.semantic_pnf_parent_delta_projection
           WHERE parent_region_id = selected_region_id
             AND target_kind NOT IN (1, 2, 3)
      ) AS keys;

    SELECT count(*),
           count(*) FILTER (WHERE key_family = 1),
           count(*) FILTER (WHERE key_family = 2),
           count(*) FILTER (WHERE key_family = 3),
           count(*) FILTER (WHERE key_family = 4),
           count(*) FILTER (WHERE key_family = 5)
      INTO touched, object_keys, factor_keys, demand_keys, actor_keys, outward_keys
      FROM execution.semantic_pnf_parent_affected_key
     WHERE parent_region_id = selected_region_id;

    IF GREATEST(object_keys, factor_keys, demand_keys, actor_keys, outward_keys)
       > selected_key_budget THEN
        RAISE EXCEPTION
            'delta-native parent % exceeds exact per-family key budget %',
            selected_region_id, selected_key_budget;
    END IF;

    IF NOT cold_value AND touched = 0 THEN
        SELECT interface_cardinality, unresolved_count
          INTO output_value, unresolved_value
          FROM execution.semantic_pnf_interface
         WHERE interface_id = selected_interface_id;
        SELECT count(*) INTO resolved_value
          FROM execution.semantic_pnf_frontier_resolution
         WHERE interface_id = selected_interface_id AND outcome_state = 2;
        SELECT count(*) INTO actor_value
          FROM execution.semantic_pnf_actor_profile
         WHERE interface_id = selected_interface_id;
        emitted_value := 0;
    ELSE
        SELECT result.output_export_count,
               result.unresolved_demand_count,
               result.resolved_demand_count,
               result.actor_profile_count
          INTO output_value, unresolved_value, resolved_value, actor_value
          FROM execution.rebuild_numeric_pnf_parent_frontier_delta_input(
              selected_interface_id
          ) AS result;
        emitted_value := CASE WHEN cold_value THEN output_value ELSE touched END;
        DELETE FROM execution.semantic_pnf_parent_affected_key
         WHERE parent_region_id = selected_region_id;
    END IF;

    INSERT INTO execution.semantic_pnf_delta_native_parent_work_receipt
        (interface_id, parent_region_id, input_delta_atoms,
         accumulated_boundary_keys, touched_boundary_keys,
         object_keys_touched, factor_keys_touched, demand_keys_touched,
         actor_keys_touched, outward_keys_touched,
         emitted_parent_deltas, hierarchy_depth, cold_build,
         output_export_count, unresolved_demand_count,
         resolved_demand_count, actor_profile_count, elapsed_ms)
    VALUES (
        selected_interface_id, selected_region_id, input_atoms,
        accumulated_keys, touched,
        object_keys, factor_keys, demand_keys, actor_keys, outward_keys,
        emitted_value, selected_hierarchy_depth, cold_value,
        output_value, unresolved_value, resolved_value, actor_value,
        EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000
    )
    ON CONFLICT (interface_id) DO UPDATE SET
        parent_region_id = EXCLUDED.parent_region_id,
        input_delta_atoms = EXCLUDED.input_delta_atoms,
        accumulated_boundary_keys = EXCLUDED.accumulated_boundary_keys,
        touched_boundary_keys = EXCLUDED.touched_boundary_keys,
        object_keys_touched = EXCLUDED.object_keys_touched,
        factor_keys_touched = EXCLUDED.factor_keys_touched,
        demand_keys_touched = EXCLUDED.demand_keys_touched,
        actor_keys_touched = EXCLUDED.actor_keys_touched,
        outward_keys_touched = EXCLUDED.outward_keys_touched,
        emitted_parent_deltas = EXCLUDED.emitted_parent_deltas,
        hierarchy_depth = EXCLUDED.hierarchy_depth,
        cold_build = EXCLUDED.cold_build,
        output_export_count = EXCLUDED.output_export_count,
        unresolved_demand_count = EXCLUDED.unresolved_demand_count,
        resolved_demand_count = EXCLUDED.resolved_demand_count,
        actor_profile_count = EXCLUDED.actor_profile_count,
        elapsed_ms = EXCLUDED.elapsed_ms,
        reduced_at = CURRENT_TIMESTAMP;

    RETURN QUERY
    SELECT selected_region_id,
           input_atoms,
           accumulated_keys,
           touched,
           object_keys,
           factor_keys,
           demand_keys,
           actor_keys,
           outward_keys,
           emitted_value,
           selected_hierarchy_depth,
           cold_value,
           output_value,
           unresolved_value,
           resolved_value,
           actor_value,
           EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000;
END;
$$;

COMMENT ON FUNCTION execution.reduce_numeric_pnf_parent_frontier_delta_native(
    BIGINT, BIGINT, BIGINT
) IS
    'C3b parent reducer bridge: consume complete transported child boundaries, classify affected key families, no-op when no key changed, retain full delta-input rebuild as the exact cold/recovery oracle while key-local mutation is certified.';

COMMIT;
