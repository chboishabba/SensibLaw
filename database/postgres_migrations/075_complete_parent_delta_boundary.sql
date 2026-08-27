BEGIN;

-- C3b prerequisite: the canonical reducer consumes more than the C2 core
-- export tuple.  Complete the transported boundary so it carries every child
-- export attribute used by parent-local reconciliation, plus the child lookup
-- boundary used to build the admitted parent lookup.  Normal transport remains
-- statement-level and delta-fed; no parser/object/factor graph is reopened.

ALTER TABLE execution.semantic_pnf_parent_delta_projection
    ADD COLUMN IF NOT EXISTS scope_class SMALLINT NOT NULL DEFAULT 1
        REFERENCES execution.semantic_pnf_scope_class(scope_class)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS origin_interface_id BIGINT
        REFERENCES execution.semantic_pnf_interface(interface_id)
        ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS outward_required BOOLEAN NOT NULL DEFAULT FALSE;

-- Backfill the retained/shadow projection from the exact child boundary rows.
UPDATE execution.semantic_pnf_parent_delta_projection AS projection
   SET scope_class = export.scope_class,
       origin_interface_id = export.origin_interface_id,
       outward_required = export.outward_required
  FROM execution.semantic_pnf_interface_export AS export
 WHERE export.interface_id = projection.child_interface_id
   AND export.export_kind = projection.export_kind
   AND export.target_kind = projection.target_kind
   AND export.target_id = projection.target_id;

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
       max(scope_class) AS scope_class,
       min(COALESCE(origin_interface_id, child_interface_id)) AS origin_interface_id,
       bool_or(outward_required) AS outward_required,
       count(*) AS contributing_child_count
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

CREATE TABLE IF NOT EXISTS execution.semantic_pnf_parent_delta_lookup_projection (
    parent_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    child_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    child_interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    key_kind SMALLINT NOT NULL CHECK (key_kind BETWEEN 1 AND 7),
    key_a BIGINT NOT NULL DEFAULT 0,
    key_b BIGINT NOT NULL DEFAULT 0,
    target_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_target_kind(kind_id) ON DELETE RESTRICT,
    target_id BIGINT NOT NULL,
    rank BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (
        parent_region_id, child_interface_id,
        key_kind, key_a, key_b, target_kind, target_id
    )
);

CREATE INDEX IF NOT EXISTS semantic_pnf_parent_delta_lookup_parent_idx
    ON execution.semantic_pnf_parent_delta_lookup_projection
       (parent_region_id, key_kind, key_a, key_b,
        target_kind, target_id, rank, child_interface_id);

CREATE OR REPLACE VIEW execution.semantic_pnf_parent_delta_fused_lookup AS
SELECT parent_region_id,
       key_kind,
       key_a,
       key_b,
       target_kind,
       target_id,
       min(rank) AS rank,
       count(*) AS contributing_child_count
  FROM execution.semantic_pnf_parent_delta_lookup_projection
 GROUP BY parent_region_id, key_kind, key_a, key_b, target_kind, target_id;

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_lookup_delta_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO execution.semantic_pnf_parent_delta_lookup_projection
        (parent_region_id, child_region_id, child_interface_id,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT child.parent_region_id,
           child.region_id,
           inserted.interface_id,
           inserted.key_kind,
           inserted.key_a,
           inserted.key_b,
           inserted.target_kind,
           inserted.target_id,
           inserted.rank
      FROM inserted_lookup AS inserted
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = inserted.interface_id
      JOIN execution.semantic_pnf_region AS child
        ON child.region_id = interface.region_id
     WHERE child.parent_region_id IS NOT NULL
       AND child.region_kind <> 9
    ON CONFLICT (
        parent_region_id, child_interface_id,
        key_kind, key_a, key_b, target_kind, target_id
    ) DO UPDATE SET
        child_region_id = EXCLUDED.child_region_id,
        rank = EXCLUDED.rank;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_delta_lookup_insert
    ON execution.semantic_pnf_interface_lookup;
CREATE TRIGGER semantic_pnf_parent_delta_lookup_insert
AFTER INSERT ON execution.semantic_pnf_interface_lookup
REFERENCING NEW TABLE AS inserted_lookup
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_lookup_delta_insert();

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_lookup_delta_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_parent_delta_lookup_projection AS projection
    USING deleted_lookup AS deleted
     WHERE projection.child_interface_id = deleted.interface_id
       AND projection.key_kind = deleted.key_kind
       AND projection.key_a = deleted.key_a
       AND projection.key_b = deleted.key_b
       AND projection.target_kind = deleted.target_kind
       AND projection.target_id = deleted.target_id;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_delta_lookup_delete
    ON execution.semantic_pnf_interface_lookup;
CREATE TRIGGER semantic_pnf_parent_delta_lookup_delete
AFTER DELETE ON execution.semantic_pnf_interface_lookup
REFERENCING OLD TABLE AS deleted_lookup
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_lookup_delta_delete();

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_lookup_delta_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_parent_delta_lookup_projection AS projection
    USING old_lookup AS old_row
     WHERE projection.child_interface_id = old_row.interface_id
       AND projection.key_kind = old_row.key_kind
       AND projection.key_a = old_row.key_a
       AND projection.key_b = old_row.key_b
       AND projection.target_kind = old_row.target_kind
       AND projection.target_id = old_row.target_id;

    INSERT INTO execution.semantic_pnf_parent_delta_lookup_projection
        (parent_region_id, child_region_id, child_interface_id,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT child.parent_region_id,
           child.region_id,
           new_row.interface_id,
           new_row.key_kind,
           new_row.key_a,
           new_row.key_b,
           new_row.target_kind,
           new_row.target_id,
           new_row.rank
      FROM new_lookup AS new_row
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.interface_id = new_row.interface_id
      JOIN execution.semantic_pnf_region AS child
        ON child.region_id = interface.region_id
     WHERE child.parent_region_id IS NOT NULL
       AND child.region_kind <> 9
    ON CONFLICT (
        parent_region_id, child_interface_id,
        key_kind, key_a, key_b, target_kind, target_id
    ) DO UPDATE SET
        child_region_id = EXCLUDED.child_region_id,
        rank = EXCLUDED.rank;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_delta_lookup_update
    ON execution.semantic_pnf_interface_lookup;
CREATE TRIGGER semantic_pnf_parent_delta_lookup_update
AFTER UPDATE ON execution.semantic_pnf_interface_lookup
REFERENCING OLD TABLE AS old_lookup NEW TABLE AS new_lookup
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_lookup_delta_update();

-- Reparent both transported boundary families together.
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
        DELETE FROM execution.semantic_pnf_parent_delta_lookup_projection
         WHERE child_region_id = NEW.region_id;
    ELSE
        UPDATE execution.semantic_pnf_parent_delta_projection
           SET parent_region_id = NEW.parent_region_id
         WHERE child_region_id = NEW.region_id;
        UPDATE execution.semantic_pnf_parent_delta_lookup_projection
           SET parent_region_id = NEW.parent_region_id
         WHERE child_region_id = NEW.region_id;
    END IF;
    RETURN NEW;
END;
$$;

-- Extend fixture/bootstrap to the complete export and lookup boundary.  This is
-- certification-only; normal execution remains statement-trigger-fed.
CREATE OR REPLACE FUNCTION execution.seed_numeric_pnf_parent_delta_projection(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected BIGINT := 0;
    lookup_affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_parent_delta_projection
        (parent_region_id, child_region_id, child_interface_id,
         export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score, scope_class, origin_interface_id,
         outward_required)
    SELECT child.parent_region_id,
           child.region_id,
           interface.interface_id,
           export.export_kind,
           export.target_kind,
           export.target_id,
           export.key_symbol_id,
           export.role_symbol_id,
           export.residual_type_symbol_id,
           export.rank,
           export.promotion_score,
           export.scope_class,
           export.origin_interface_id,
           export.outward_required
      FROM execution.semantic_pnf_region AS child
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id = child.region_id
      JOIN execution.semantic_pnf_interface_export AS export
        ON export.interface_id = interface.interface_id
     WHERE child.run_ref = selected_run_ref
       AND child.document_ref = selected_document_ref
       AND child.parent_region_id IS NOT NULL
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
    GET DIAGNOSTICS affected = ROW_COUNT;

    INSERT INTO execution.semantic_pnf_parent_delta_lookup_projection
        (parent_region_id, child_region_id, child_interface_id,
         key_kind, key_a, key_b, target_kind, target_id, rank)
    SELECT child.parent_region_id,
           child.region_id,
           interface.interface_id,
           lookup.key_kind,
           lookup.key_a,
           lookup.key_b,
           lookup.target_kind,
           lookup.target_id,
           lookup.rank
      FROM execution.semantic_pnf_region AS child
      JOIN execution.semantic_pnf_interface AS interface
        ON interface.region_id = child.region_id
      JOIN execution.semantic_pnf_interface_lookup AS lookup
        ON lookup.interface_id = interface.interface_id
     WHERE child.run_ref = selected_run_ref
       AND child.document_ref = selected_document_ref
       AND child.parent_region_id IS NOT NULL
       AND child.region_kind <> 9
    ON CONFLICT (
        parent_region_id, child_interface_id,
        key_kind, key_a, key_b, target_kind, target_id
    ) DO UPDATE SET
        child_region_id = EXCLUDED.child_region_id,
        rank = EXCLUDED.rank;
    GET DIAGNOSTICS lookup_affected = ROW_COUNT;

    RETURN affected + lookup_affected;
END;
$$;

COMMIT;
