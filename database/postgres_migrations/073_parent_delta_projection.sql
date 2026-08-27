BEGIN;

-- C2 shadow path: transport compact child-interface boundary deltas into a
-- parent-local projection without rebuilding child interiors or mutating the
-- canonical sparse frontier.  The canonical reducer remains the authority
-- until parity is certified.
CREATE TABLE IF NOT EXISTS execution.semantic_pnf_parent_delta_projection (
    parent_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    child_region_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_region(region_id) ON DELETE CASCADE,
    child_interface_id BIGINT NOT NULL
        REFERENCES execution.semantic_pnf_interface(interface_id) ON DELETE CASCADE,
    export_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_export_kind(kind_id) ON DELETE RESTRICT,
    target_kind SMALLINT NOT NULL
        REFERENCES execution.semantic_pnf_target_kind(kind_id) ON DELETE RESTRICT,
    target_id BIGINT NOT NULL,
    key_symbol_id BIGINT,
    role_symbol_id BIGINT,
    residual_type_symbol_id BIGINT,
    rank BIGINT NOT NULL DEFAULT 0,
    promotion_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (
        parent_region_id, child_interface_id,
        export_kind, target_kind, target_id
    )
);

CREATE INDEX IF NOT EXISTS semantic_pnf_parent_delta_projection_parent_idx
    ON execution.semantic_pnf_parent_delta_projection
       (parent_region_id, target_kind, key_symbol_id, residual_type_symbol_id,
        child_interface_id, target_id);

-- Associative/idempotent parent fusion.  Child provenance remains in the base
-- projection while this view exposes the canonical set-like union shape.
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
         rank, promotion_score)
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
           inserted.promotion_score
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
        promotion_score = EXCLUDED.promotion_score;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_delta_export_insert
    ON execution.semantic_pnf_interface_export;
CREATE TRIGGER semantic_pnf_parent_delta_export_insert
AFTER INSERT ON execution.semantic_pnf_interface_export
REFERENCING NEW TABLE AS inserted_export
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_export_delta_insert();

CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_export_delta_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM execution.semantic_pnf_parent_delta_projection AS projection
    USING deleted_export AS deleted
     WHERE projection.child_interface_id = deleted.interface_id
       AND projection.export_kind = deleted.export_kind
       AND projection.target_kind = deleted.target_kind
       AND projection.target_id = deleted.target_id;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_delta_export_delete
    ON execution.semantic_pnf_interface_export;
CREATE TRIGGER semantic_pnf_parent_delta_export_delete
AFTER DELETE ON execution.semantic_pnf_interface_export
REFERENCING OLD TABLE AS deleted_export
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_export_delta_delete();

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
         rank, promotion_score)
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
           new_row.promotion_score
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
        promotion_score = EXCLUDED.promotion_score;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_delta_export_update
    ON execution.semantic_pnf_interface_export;
CREATE TRIGGER semantic_pnf_parent_delta_export_update
AFTER UPDATE ON execution.semantic_pnf_interface_export
REFERENCING OLD TABLE AS old_export NEW TABLE AS new_export
FOR EACH STATEMENT
EXECUTE FUNCTION execution.transport_numeric_pnf_export_delta_update();

-- Reparenting is itself transport: move existing child-boundary atoms to the
-- new fibre address without reopening or re-reading the child semantic graph.
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
    ELSE
        UPDATE execution.semantic_pnf_parent_delta_projection
           SET parent_region_id = NEW.parent_region_id
         WHERE child_region_id = NEW.region_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_delta_rehome
    ON execution.semantic_pnf_region;
CREATE TRIGGER semantic_pnf_parent_delta_rehome
AFTER UPDATE OF parent_region_id ON execution.semantic_pnf_region
FOR EACH ROW
EXECUTE FUNCTION execution.rehome_numeric_pnf_parent_delta_projection();

-- Explicit certification/bootstrap only.  Normal execution is trigger-fed;
-- this function seeds a pre-existing isolated fixture once from already
-- materialized child boundaries, never from token/object/factor interiors.
CREATE OR REPLACE FUNCTION execution.seed_numeric_pnf_parent_delta_projection(
    selected_run_ref TEXT,
    selected_document_ref TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected BIGINT := 0;
BEGIN
    INSERT INTO execution.semantic_pnf_parent_delta_projection
        (parent_region_id, child_region_id, child_interface_id,
         export_kind, target_kind, target_id,
         key_symbol_id, role_symbol_id, residual_type_symbol_id,
         rank, promotion_score)
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
           export.promotion_score
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
        promotion_score = EXCLUDED.promotion_score;
    GET DIAGNOSTICS affected = ROW_COUNT;
    RETURN affected;
END;
$$;

COMMIT;
