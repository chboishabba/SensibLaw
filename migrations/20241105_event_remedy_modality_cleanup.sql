-- Align event_remedy modality to the catalog and drop the duplicate column
BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'event_remedy'
          AND column_name = 'remedy_modality_id'
    ) THEN
        -- Backfill any divergent modality_ids to match the linked catalog entry
        UPDATE event_remedy er
        SET remedy_modality_id = rc.remedy_modality_id
        FROM remedy_catalog rc
        WHERE er.remedy_catalog_id = rc.id
          AND er.remedy_modality_id IS DISTINCT FROM rc.remedy_modality_id;

        -- Create a transient FK to guarantee remaining values match the catalog modality
        CREATE UNIQUE INDEX IF NOT EXISTS idx_remedy_catalog_id_modality
            ON remedy_catalog (id, remedy_modality_id);

        ALTER TABLE event_remedy
            ADD CONSTRAINT event_remedy_catalog_modality_fk
            FOREIGN KEY (remedy_catalog_id, remedy_modality_id)
            REFERENCES remedy_catalog(id, remedy_modality_id)
            ON DELETE SET NULL
            NOT VALID;

        ALTER TABLE event_remedy
            VALIDATE CONSTRAINT event_remedy_catalog_modality_fk;

        ALTER TABLE event_remedy
            DROP CONSTRAINT IF EXISTS event_remedy_catalog_modality_fk;

        -- Drop the redundant modality column now that modality is catalog-owned
        ALTER TABLE event_remedy
            DROP COLUMN IF EXISTS remedy_modality_id;

        DROP INDEX IF EXISTS idx_remedy_catalog_id_modality;
    END IF;
END $$;

-- Refresh modality-aware views to route through remedy_catalog
DROP VIEW IF EXISTS event_remedy_with_modality;
CREATE VIEW event_remedy_with_modality AS
SELECT
    er.id,
    er.event_id,
    er.harm_instance_id,
    er.remedy_catalog_id,
    er.value_frame_id,
    er.terms,
    er.note,
    er.created_at,
    er.updated_at,
    rc.remedy_modality_id,
    rm.modality_code,
    rm.label AS remedy_modality_label,
    rm.description AS remedy_modality_description
FROM event_remedy er
LEFT JOIN remedy_catalog rc ON rc.id = er.remedy_catalog_id
LEFT JOIN remedy_modality rm ON rm.id = rc.remedy_modality_id;

DROP VIEW IF EXISTS remedy_library_by_value_frame;
CREATE VIEW remedy_library_by_value_frame AS
SELECT
    vf.id AS value_frame_id,
    vf.frame_code,
    vf.label AS value_frame_label,
    rc.id AS remedy_catalog_id,
    rc.remedy_code,
    rc.terms,
    rc.note,
    rc.legal_system_id,
    rc.cultural_register_id,
    rm.modality_code,
    rm.label AS remedy_modality_label,
    rm.description AS remedy_modality_description
FROM value_frame vf
JOIN value_frame_remedies vfr ON vfr.value_frame_id = vf.id
JOIN remedy_catalog rc ON rc.id = vfr.remedy_catalog_id
JOIN remedy_modality rm ON rm.id = rc.remedy_modality_id;

COMMIT;
