PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS countries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subdivisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_id INTEGER NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    UNIQUE (country_id, code)
);

INSERT OR IGNORE INTO countries (code, name) VALUES
    ('AU', 'Australia'),
    ('NZ', 'New Zealand'),
    ('PK', 'Pakistan'),
    ('US', 'United States'),
    ('EU', 'European Union'),
    ('GB', 'United Kingdom'),
    ('CA', 'Canada'),
    ('IN', 'India');

INSERT OR IGNORE INTO countries (code, name)
SELECT DISTINCT region, region
FROM legal_systems
WHERE region IS NOT NULL
  AND region NOT IN (SELECT code FROM countries);

INSERT OR IGNORE INTO subdivisions (country_id, code, name)
SELECT id, 'FEDERAL', 'Federal' FROM countries WHERE code IN ('AU', 'US', 'PK')
UNION ALL
SELECT id, 'QLD', 'Queensland' FROM countries WHERE code = 'AU'
UNION ALL
SELECT id, 'NSW', 'New South Wales' FROM countries WHERE code = 'AU'
UNION ALL
SELECT id, 'VIC', 'Victoria' FROM countries WHERE code = 'AU'
UNION ALL
SELECT id, 'WA', 'Western Australia' FROM countries WHERE code = 'AU'
UNION ALL
SELECT id, 'SA', 'South Australia' FROM countries WHERE code = 'AU'
UNION ALL
SELECT id, 'TAS', 'Tasmania' FROM countries WHERE code = 'AU'
UNION ALL
SELECT id, 'ACT', 'Australian Capital Territory' FROM countries WHERE code = 'AU'
UNION ALL
SELECT id, 'NT', 'Northern Territory' FROM countries WHERE code = 'AU'
UNION ALL
SELECT id, 'PUNJAB', 'Punjab' FROM countries WHERE code = 'PK'
UNION ALL
SELECT id, 'SINDH', 'Sindh' FROM countries WHERE code = 'PK'
UNION ALL
SELECT id, 'KPK', 'Khyber Pakhtunkhwa' FROM countries WHERE code = 'PK'
UNION ALL
SELECT id, 'BALOCHISTAN', 'Balochistan' FROM countries WHERE code = 'PK'
UNION ALL
SELECT id, 'ICT', 'Islamabad Capital Territory' FROM countries WHERE code = 'PK';

CREATE TABLE IF NOT EXISTS legal_systems_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    tradition TEXT,
    description TEXT,
    valid_from DATE,
    valid_to DATE,
    priority INTEGER DEFAULT 0,
    country_id INTEGER NOT NULL REFERENCES countries(id) ON DELETE RESTRICT,
    subdivision_id INTEGER REFERENCES subdivisions(id) ON DELETE SET NULL
);

INSERT INTO legal_systems_new (
    id, code, name, tradition, description, valid_from, valid_to, priority, country_id, subdivision_id
)
SELECT
    ls.id,
    ls.code,
    ls.name,
    ls.tradition,
    ls.description,
    ls.valid_from,
    ls.valid_to,
    ls.priority,
    (SELECT id FROM countries WHERE code = ls.region),
    CASE
        WHEN ls.code = 'AU.STATE.QLD' THEN (
            SELECT sub.id
            FROM subdivisions sub
            JOIN countries c ON c.id = sub.country_id
            WHERE c.code = 'AU' AND sub.code = 'QLD'
        )
        ELSE NULL
    END
FROM legal_systems ls;

DROP TABLE legal_systems;
ALTER TABLE legal_systems_new RENAME TO legal_systems;

PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;
