-- Enforce deriving remedy legal-system provenance from the linked harm/event
BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'remedy' AND column_name = 'legal_system_id'
    ) THEN
        -- Align any existing remedy records with their event legal system
        UPDATE remedy r
        SET legal_system_id = e.legal_system_id
        FROM harm_instance h
        JOIN event e ON e.id = h.event_id
        WHERE r.harm_instance_id = h.id
          AND r.legal_system_id IS DISTINCT FROM e.legal_system_id;

        -- Block upgrades if any mismatches remain
        IF EXISTS (
            SELECT 1
            FROM remedy r
            JOIN harm_instance h ON h.id = r.harm_instance_id
            JOIN event e ON e.id = h.event_id
            WHERE r.legal_system_id IS DISTINCT FROM e.legal_system_id
        ) THEN
            RAISE EXCEPTION 'Remedy legal_system_id must match event legal system';
        END IF;

        -- Drop the redundant legal system column
        ALTER TABLE remedy DROP COLUMN legal_system_id;
    END IF;
END$$;

-- Allow template remedies that are not yet bound to a harm
ALTER TABLE remedy ALTER COLUMN harm_instance_id DROP NOT NULL;

-- Refresh dependent views to source the legal system from events
DROP VIEW IF EXISTS remedy_library_by_value_frame;
CREATE VIEW remedy_library_by_value_frame AS
SELECT
    vf.id AS value_frame_id,
    vf.frame_code,
    vf.label AS value_frame_label,
    r.id AS remedy_id,
    r.remedy_modality,
    r.remedy_code,
    r.terms,
    r.note,
    e.legal_system_id,
    r.cultural_register_id
FROM value_frame vf
JOIN value_frame_remedies vfr ON vfr.value_frame_id = vf.id
JOIN remedy r ON r.id = vfr.remedy_id
LEFT JOIN harm_instance h ON h.id = r.harm_instance_id
LEFT JOIN event e ON e.id = h.event_id;

COMMIT;
