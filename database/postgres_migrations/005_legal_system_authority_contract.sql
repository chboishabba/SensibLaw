-- Layer 1 legal-system authority-boundary enrichment (PostgreSQL)
BEGIN;

ALTER TABLE legal_system
    ADD COLUMN IF NOT EXISTS sovereignty_type TEXT,
    ADD COLUMN IF NOT EXISTS parent_system_id BIGINT REFERENCES legal_system(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS commencement_date DATE,
    ADD COLUMN IF NOT EXISTS constitutional_source_id BIGINT REFERENCES legal_source(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS recognises_common_law BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS recognises_equity BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_legal_system_parent_system
    ON legal_system(parent_system_id);

CREATE INDEX IF NOT EXISTS idx_legal_system_sovereignty_type
    ON legal_system(sovereignty_type);

INSERT INTO norm_source_category (code, label, description) VALUES
    ('CONSTITUTION', 'Constitution', 'Foundational constitutional source of legislative and judicial authority.')
ON CONFLICT (code) DO NOTHING;

UPDATE legal_system
SET recognises_common_law = CASE WHEN UPPER(COALESCE(tradition, '')) = 'COMMON' THEN TRUE ELSE FALSE END,
    recognises_equity = CASE WHEN UPPER(COALESCE(tradition, '')) = 'COMMON' THEN TRUE ELSE FALSE END;

UPDATE legal_system
SET sovereignty_type = CASE
    WHEN code = 'AU.COMMON' THEN 'sovereign'
    WHEN code LIKE 'AU.STATE.%' THEN 'sub_sovereign'
    WHEN code = 'US.STATE' THEN 'sub_sovereign'
    WHEN code = 'EU' THEN 'supranational'
    WHEN code IN ('NZ.TIKANGA', 'PK.ISLAM.HANAFI') THEN 'community'
    ELSE 'sovereign'
END
WHERE COALESCE(sovereignty_type, '') = '';

INSERT INTO legal_system (
    code, name, tradition, region, description, priority,
    sovereignty_type, commencement_date, recognises_common_law, recognises_equity
) VALUES
    ('AU.STATE.NSW', 'Australia — New South Wales', 'COMMON', 'AU', 'New South Wales state legal system under Australian constitutional hierarchy.', 1, 'sub_sovereign', '1901-01-01', TRUE, TRUE),
    ('AU.STATE.VIC', 'Australia — Victoria', 'COMMON', 'AU', 'Victoria state legal system under Australian constitutional hierarchy.', 1, 'sub_sovereign', '1901-01-01', TRUE, TRUE),
    ('AU.STATE.WA', 'Australia — Western Australia', 'COMMON', 'AU', 'Western Australia state legal system under Australian constitutional hierarchy.', 1, 'sub_sovereign', '1901-01-01', TRUE, TRUE),
    ('AU.STATE.SA', 'Australia — South Australia', 'COMMON', 'AU', 'South Australia state legal system under Australian constitutional hierarchy.', 1, 'sub_sovereign', '1901-01-01', TRUE, TRUE),
    ('AU.STATE.TAS', 'Australia — Tasmania', 'COMMON', 'AU', 'Tasmania state legal system under Australian constitutional hierarchy.', 1, 'sub_sovereign', '1901-01-01', TRUE, TRUE),
    ('AU.STATE.ACT', 'Australia — Australian Capital Territory', 'COMMON', 'AU', 'ACT legal system under Australian constitutional hierarchy.', 1, 'sub_sovereign', '1901-01-01', TRUE, TRUE),
    ('AU.STATE.NT', 'Australia — Northern Territory', 'COMMON', 'AU', 'NT legal system under Australian constitutional hierarchy.', 1, 'sub_sovereign', '1901-01-01', TRUE, TRUE)
ON CONFLICT (code) DO NOTHING;

UPDATE legal_system
SET parent_system_id = (SELECT id FROM legal_system WHERE code = 'AU.COMMON')
WHERE code LIKE 'AU.STATE.%'
  AND code <> 'AU.COMMON';

UPDATE legal_system
SET commencement_date = CASE
    WHEN code = 'AU.COMMON' THEN '1901-01-01'
    WHEN code LIKE 'AU.STATE.%' THEN '1901-01-01'
    WHEN code = 'EU' THEN '1993-11-01'
    ELSE commencement_date
END
WHERE commencement_date IS NULL;

INSERT INTO legal_source (
    legal_system_id,
    norm_source_category_id,
    citation,
    title,
    source_url,
    summary
)
VALUES (
    (SELECT id FROM legal_system WHERE code = 'AU.COMMON'),
    (SELECT id FROM norm_source_category WHERE code = 'CONSTITUTION'),
    'Commonwealth of Australia Constitution Act 1900 (UK)',
    'Commonwealth of Australia Constitution Act 1900',
    'https://www.legislation.gov.au/C2004A00469/latest/text',
    'Foundational constitutional instrument for the Commonwealth of Australia.'
)
ON CONFLICT (legal_system_id, citation) DO NOTHING;

INSERT INTO legal_source (
    legal_system_id,
    norm_source_category_id,
    citation,
    title,
    source_url,
    summary
)
VALUES (
    (SELECT id FROM legal_system WHERE code = 'AU.STATE.NSW'),
    (SELECT id FROM norm_source_category WHERE code = 'CONSTITUTION'),
    'Constitution Act 1902 (NSW)',
    'Constitution Act 1902 (NSW)',
    'https://legislation.nsw.gov.au/view/html/inforce/current/act-1902-032',
    'Constitutional framework statute for New South Wales.'
)
ON CONFLICT (legal_system_id, citation) DO NOTHING;

INSERT INTO legal_source (
    legal_system_id,
    norm_source_category_id,
    citation,
    title,
    source_url,
    summary
)
VALUES (
    (SELECT id FROM legal_system WHERE code = 'AU.STATE.QLD'),
    (SELECT id FROM norm_source_category WHERE code = 'CONSTITUTION'),
    'Constitution of Queensland 2001 (Qld)',
    'Constitution of Queensland 2001 (Qld)',
    'https://www.legislation.qld.gov.au/view/html/inforce/current/act-2001-080',
    'Constitutional framework statute for Queensland.'
)
ON CONFLICT (legal_system_id, citation) DO NOTHING;

UPDATE legal_system lsys
SET constitutional_source_id = src.id
FROM legal_source src
JOIN norm_source_category cat ON cat.id = src.norm_source_category_id
WHERE src.legal_system_id = lsys.id
  AND cat.code = 'CONSTITUTION'
  AND lsys.code IN ('AU.COMMON', 'AU.STATE.NSW', 'AU.STATE.QLD');

COMMIT;
