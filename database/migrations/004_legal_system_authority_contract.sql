PRAGMA foreign_keys = OFF;

-- Layer 3 authority-boundary upgrade for legal systems.
ALTER TABLE legal_systems ADD COLUMN sovereignty_type TEXT;
ALTER TABLE legal_systems ADD COLUMN parent_system_id INTEGER REFERENCES legal_systems(id) ON DELETE SET NULL;
ALTER TABLE legal_systems ADD COLUMN commencement_date DATE;
ALTER TABLE legal_systems ADD COLUMN constitutional_source_id INTEGER REFERENCES legal_sources(id) ON DELETE SET NULL;
ALTER TABLE legal_systems ADD COLUMN recognises_common_law INTEGER NOT NULL DEFAULT 0 CHECK (recognises_common_law IN (0, 1));
ALTER TABLE legal_systems ADD COLUMN recognises_equity INTEGER NOT NULL DEFAULT 0 CHECK (recognises_equity IN (0, 1));

CREATE INDEX IF NOT EXISTS idx_legal_systems_parent_system
    ON legal_systems(parent_system_id);

CREATE INDEX IF NOT EXISTS idx_legal_systems_sovereignty_type
    ON legal_systems(sovereignty_type);

INSERT OR IGNORE INTO norm_source_categories (code, label, description) VALUES
    ('CONSTITUTION', 'Constitution', 'Foundational constitutional source of legislative and judicial authority.');

-- Baseline sovereignty and doctrinal-recognition defaults.
UPDATE legal_systems
SET recognises_common_law = CASE WHEN UPPER(COALESCE(tradition, '')) = 'COMMON' THEN 1 ELSE 0 END,
    recognises_equity = CASE WHEN UPPER(COALESCE(tradition, '')) = 'COMMON' THEN 1 ELSE 0 END;

UPDATE legal_systems
SET sovereignty_type = CASE
    WHEN code = 'AU.COMMON' THEN 'sovereign'
    WHEN code LIKE 'AU.STATE.%' THEN 'sub_sovereign'
    WHEN code = 'US.STATE' THEN 'sub_sovereign'
    WHEN code = 'EU' THEN 'supranational'
    WHEN code IN ('NZ.TIKANGA', 'PK.ISLAM.HANAFI') THEN 'community'
    ELSE 'sovereign'
END
WHERE COALESCE(sovereignty_type, '') = '';

-- Add AU state systems as explicit sub-sovereign authority spaces.
INSERT OR IGNORE INTO legal_systems (
    code, name, tradition, description, valid_from, valid_to, priority,
    country_id, subdivision_id, sovereignty_type, commencement_date,
    recognises_common_law, recognises_equity
)
SELECT
    'AU.STATE.NSW',
    'Australia — New South Wales',
    'COMMON',
    'New South Wales state legal system under Australian constitutional hierarchy.',
    NULL,
    NULL,
    1,
    c.id,
    sub.id,
    'sub_sovereign',
    '1901-01-01',
    1,
    1
FROM countries c
JOIN subdivisions sub ON sub.country_id = c.id AND sub.code = 'NSW'
WHERE c.code = 'AU';

INSERT OR IGNORE INTO legal_systems (
    code, name, tradition, description, valid_from, valid_to, priority,
    country_id, subdivision_id, sovereignty_type, commencement_date,
    recognises_common_law, recognises_equity
)
SELECT
    'AU.STATE.VIC',
    'Australia — Victoria',
    'COMMON',
    'Victoria state legal system under Australian constitutional hierarchy.',
    NULL,
    NULL,
    1,
    c.id,
    sub.id,
    'sub_sovereign',
    '1901-01-01',
    1,
    1
FROM countries c
JOIN subdivisions sub ON sub.country_id = c.id AND sub.code = 'VIC'
WHERE c.code = 'AU';

INSERT OR IGNORE INTO legal_systems (
    code, name, tradition, description, valid_from, valid_to, priority,
    country_id, subdivision_id, sovereignty_type, commencement_date,
    recognises_common_law, recognises_equity
)
SELECT
    'AU.STATE.WA',
    'Australia — Western Australia',
    'COMMON',
    'Western Australia state legal system under Australian constitutional hierarchy.',
    NULL,
    NULL,
    1,
    c.id,
    sub.id,
    'sub_sovereign',
    '1901-01-01',
    1,
    1
FROM countries c
JOIN subdivisions sub ON sub.country_id = c.id AND sub.code = 'WA'
WHERE c.code = 'AU';

INSERT OR IGNORE INTO legal_systems (
    code, name, tradition, description, valid_from, valid_to, priority,
    country_id, subdivision_id, sovereignty_type, commencement_date,
    recognises_common_law, recognises_equity
)
SELECT
    'AU.STATE.SA',
    'Australia — South Australia',
    'COMMON',
    'South Australia state legal system under Australian constitutional hierarchy.',
    NULL,
    NULL,
    1,
    c.id,
    sub.id,
    'sub_sovereign',
    '1901-01-01',
    1,
    1
FROM countries c
JOIN subdivisions sub ON sub.country_id = c.id AND sub.code = 'SA'
WHERE c.code = 'AU';

INSERT OR IGNORE INTO legal_systems (
    code, name, tradition, description, valid_from, valid_to, priority,
    country_id, subdivision_id, sovereignty_type, commencement_date,
    recognises_common_law, recognises_equity
)
SELECT
    'AU.STATE.TAS',
    'Australia — Tasmania',
    'COMMON',
    'Tasmania state legal system under Australian constitutional hierarchy.',
    NULL,
    NULL,
    1,
    c.id,
    sub.id,
    'sub_sovereign',
    '1901-01-01',
    1,
    1
FROM countries c
JOIN subdivisions sub ON sub.country_id = c.id AND sub.code = 'TAS'
WHERE c.code = 'AU';

INSERT OR IGNORE INTO legal_systems (
    code, name, tradition, description, valid_from, valid_to, priority,
    country_id, subdivision_id, sovereignty_type, commencement_date,
    recognises_common_law, recognises_equity
)
SELECT
    'AU.STATE.ACT',
    'Australia — Australian Capital Territory',
    'COMMON',
    'ACT legal system under Australian constitutional hierarchy.',
    NULL,
    NULL,
    1,
    c.id,
    sub.id,
    'sub_sovereign',
    '1901-01-01',
    1,
    1
FROM countries c
JOIN subdivisions sub ON sub.country_id = c.id AND sub.code = 'ACT'
WHERE c.code = 'AU';

INSERT OR IGNORE INTO legal_systems (
    code, name, tradition, description, valid_from, valid_to, priority,
    country_id, subdivision_id, sovereignty_type, commencement_date,
    recognises_common_law, recognises_equity
)
SELECT
    'AU.STATE.NT',
    'Australia — Northern Territory',
    'COMMON',
    'NT legal system under Australian constitutional hierarchy.',
    NULL,
    NULL,
    1,
    c.id,
    sub.id,
    'sub_sovereign',
    '1901-01-01',
    1,
    1
FROM countries c
JOIN subdivisions sub ON sub.country_id = c.id AND sub.code = 'NT'
WHERE c.code = 'AU';

UPDATE legal_systems
SET sovereignty_type = 'sub_sovereign'
WHERE code LIKE 'AU.STATE.%';

UPDATE legal_systems
SET parent_system_id = (SELECT id FROM legal_systems WHERE code = 'AU.COMMON')
WHERE code LIKE 'AU.STATE.%'
  AND code != 'AU.COMMON';

UPDATE legal_systems
SET commencement_date = CASE
    WHEN code = 'AU.COMMON' THEN '1901-01-01'
    WHEN code LIKE 'AU.STATE.%' THEN '1901-01-01'
    WHEN code = 'EU' THEN '1993-11-01'
    ELSE commencement_date
END
WHERE commencement_date IS NULL;

-- Seed constitutional sources for canonical AU systems and link them.
INSERT OR IGNORE INTO legal_sources (
    legal_system_id,
    norm_source_category_id,
    citation,
    title,
    source_url,
    summary
)
VALUES (
    (SELECT id FROM legal_systems WHERE code = 'AU.COMMON'),
    (SELECT id FROM norm_source_categories WHERE code = 'CONSTITUTION'),
    'Commonwealth of Australia Constitution Act 1900 (UK)',
    'Commonwealth of Australia Constitution Act 1900',
    'https://www.legislation.gov.au/C2004A00469/latest/text',
    'Foundational constitutional instrument for the Commonwealth of Australia.'
);

INSERT OR IGNORE INTO legal_sources (
    legal_system_id,
    norm_source_category_id,
    citation,
    title,
    source_url,
    summary
)
VALUES (
    (SELECT id FROM legal_systems WHERE code = 'AU.STATE.NSW'),
    (SELECT id FROM norm_source_categories WHERE code = 'CONSTITUTION'),
    'Constitution Act 1902 (NSW)',
    'Constitution Act 1902 (NSW)',
    'https://legislation.nsw.gov.au/view/html/inforce/current/act-1902-032',
    'Constitutional framework statute for New South Wales.'
);

INSERT OR IGNORE INTO legal_sources (
    legal_system_id,
    norm_source_category_id,
    citation,
    title,
    source_url,
    summary
)
VALUES (
    (SELECT id FROM legal_systems WHERE code = 'AU.STATE.QLD'),
    (SELECT id FROM norm_source_categories WHERE code = 'CONSTITUTION'),
    'Constitution of Queensland 2001 (Qld)',
    'Constitution of Queensland 2001 (Qld)',
    'https://www.legislation.qld.gov.au/view/html/inforce/current/act-2001-080',
    'Constitutional framework statute for Queensland.'
);

UPDATE legal_systems
SET constitutional_source_id = (
    SELECT ls.id
    FROM legal_sources ls
    JOIN norm_source_categories cat ON cat.id = ls.norm_source_category_id
    WHERE ls.legal_system_id = legal_systems.id
      AND cat.code = 'CONSTITUTION'
    ORDER BY ls.id
    LIMIT 1
)
WHERE code IN ('AU.COMMON', 'AU.STATE.NSW', 'AU.STATE.QLD');

PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;
