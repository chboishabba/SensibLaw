-- Ensure event legal systems match the referenced wrong type.
-- Backfills any mismatches and installs a composite foreign key
-- so downstream services can derive the legal system from wrong_type.

BEGIN;

-- Align existing rows to the wrong type's legal system when linked.
UPDATE event e
SET legal_system_id = wt.legal_system_id
FROM wrong_type wt
WHERE e.wrong_type_id = wt.id
  AND e.legal_system_id IS DISTINCT FROM wt.legal_system_id;

-- Allow composite foreign key enforcement.
ALTER TABLE wrong_type
    ADD CONSTRAINT IF NOT EXISTS wrong_type_id_legal_system_unique
        UNIQUE (id, legal_system_id);

-- Enforce that an event tied to a wrong type shares its legal system.
ALTER TABLE event
    ADD CONSTRAINT IF NOT EXISTS event_wrong_type_legal_system_fk
        FOREIGN KEY (wrong_type_id, legal_system_id)
        REFERENCES wrong_type(id, legal_system_id)
        ON UPDATE CASCADE;

-- Refresh views to rely on the wrong_type legal system where available.
DROP VIEW IF EXISTS harm_interest_links;
CREATE VIEW harm_interest_links AS
SELECT
    h.id AS harm_instance_id,
    h.event_id,
    h.protected_interest_type_id,
    pit.label AS protected_interest_label,
    pit.description AS protected_interest_description,
    pit.value_dimension_id,
    pit.cultural_register_id,
    COALESCE(wt.legal_system_id, e.legal_system_id) AS legal_system_id,
    e.event_kind,
    h.severity,
    h.extent,
    h.note
FROM harm_instance h
JOIN protected_interest_type pit ON pit.id = h.protected_interest_type_id
JOIN event e ON e.id = h.event_id
LEFT JOIN wrong_type wt ON wt.id = e.wrong_type_id;

DROP VIEW IF EXISTS harm_counts_by_interest;
CREATE VIEW harm_counts_by_interest AS
SELECT
    pit.id AS protected_interest_type_id,
    pit.description AS protected_interest_description,
    COALESCE(wt.legal_system_id, e.legal_system_id) AS legal_system_id,
    COUNT(h.id) AS harm_count,
    COUNT(DISTINCT e.id) AS event_count
FROM harm_instance h
JOIN event e ON e.id = h.event_id
JOIN protected_interest_type pit ON pit.id = h.protected_interest_type_id
LEFT JOIN wrong_type wt ON wt.id = e.wrong_type_id
GROUP BY pit.id, pit.description, COALESCE(wt.legal_system_id, e.legal_system_id);

COMMIT;
