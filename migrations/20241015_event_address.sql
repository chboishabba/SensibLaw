-- Add address reference to event and migrate legacy location values
BEGIN;

-- Ensure address dimension exists for events to reference
CREATE TABLE IF NOT EXISTS address (
    id BIGSERIAL PRIMARY KEY,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city TEXT,
    state_province TEXT,
    postal_code TEXT,
    country_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add the new foreign key while retaining the legacy location column for backfill
ALTER TABLE event
    ADD COLUMN IF NOT EXISTS address_id BIGINT REFERENCES address(id) ON DELETE SET NULL;

COMMENT ON COLUMN event.location IS 'Deprecated: prefer structured address fields and address_id.';

-- Map historic free-text locations to structured address rows to preserve links
CREATE TABLE IF NOT EXISTS event_location_address (
    location TEXT PRIMARY KEY,
    address_id BIGINT NOT NULL REFERENCES address(id) ON DELETE CASCADE
);

WITH distinct_locations AS (
    SELECT DISTINCT TRIM(location) AS location
    FROM event
    WHERE location IS NOT NULL AND TRIM(location) <> ''
),
existing_matches AS (
    SELECT dl.location, a.id AS address_id
    FROM distinct_locations dl
    JOIN address a ON a.address_line1 = dl.location
),
inserted AS (
    INSERT INTO address (address_line1)
    SELECT dl.location
    FROM distinct_locations dl
    WHERE NOT EXISTS (
        SELECT 1 FROM address a WHERE a.address_line1 = dl.location
    )
    RETURNING id, address_line1
),
consolidated AS (
    SELECT address_line1 AS location, id AS address_id FROM inserted
    UNION
    SELECT location, address_id FROM existing_matches
)
INSERT INTO event_location_address (location, address_id)
SELECT location, address_id FROM consolidated
ON CONFLICT (location) DO UPDATE SET address_id = EXCLUDED.address_id;

UPDATE event e
SET address_id = ela.address_id
FROM event_location_address ela
WHERE TRIM(e.location) = ela.location
  AND (e.address_id IS NULL OR e.address_id <> ela.address_id);

-- Recreate views to surface address metadata alongside events
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
    e.legal_system_id,
    e.event_kind,
    e.address_id,
    addr.address_line1,
    addr.address_line2,
    addr.city,
    addr.state_province,
    addr.postal_code,
    addr.country_code,
    h.severity,
    h.extent,
    h.note
FROM harm_instance h
JOIN protected_interest_type pit ON pit.id = h.protected_interest_type_id
JOIN event e ON e.id = h.event_id
LEFT JOIN address addr ON addr.id = e.address_id;

DROP VIEW IF EXISTS harm_counts_by_interest;
CREATE VIEW harm_counts_by_interest AS
SELECT
    pit.id AS protected_interest_type_id,
    pit.description AS protected_interest_description,
    e.legal_system_id,
    e.address_id,
    COUNT(h.id) AS harm_count,
    COUNT(DISTINCT e.id) AS event_count
FROM harm_instance h
JOIN event e ON e.id = h.event_id
JOIN protected_interest_type pit ON pit.id = h.protected_interest_type_id
GROUP BY pit.id, pit.description, e.legal_system_id, e.address_id;

COMMIT;
