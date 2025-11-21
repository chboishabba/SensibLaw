-- Add country and subdivision references to addresses and migrate legacy country codes.
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS addresses_new;

CREATE TABLE addresses_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city TEXT,
    state_province TEXT,
    postal_code TEXT,
    country_id INTEGER REFERENCES countries(id) ON DELETE SET NULL,
    subdivision_id INTEGER REFERENCES subdivisions(id) ON DELETE SET NULL
);

INSERT INTO addresses_new (
    id,
    address_line1,
    address_line2,
    city,
    state_province,
    postal_code,
    country_id,
    subdivision_id
)
SELECT
    id,
    address_line1,
    address_line2,
    city,
    state_province,
    postal_code,
    (
        SELECT id
        FROM countries
        WHERE code = UPPER(TRIM(country_code))
    ) AS country_id,
    (
        SELECT sub.id
        FROM subdivisions sub
        JOIN countries c ON c.id = sub.country_id
        WHERE c.code = UPPER(TRIM(country_code))
          AND sub.code = UPPER(TRIM(state_province))
    ) AS subdivision_id
FROM addresses;

DROP TABLE addresses;
ALTER TABLE addresses_new RENAME TO addresses;

PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;
