PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS legal_systems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    tradition TEXT,
    region TEXT,
    description TEXT,
    valid_from DATE,
    valid_to DATE,
    priority INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS norm_source_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS legal_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legal_system_id INTEGER NOT NULL REFERENCES legal_systems(id) ON DELETE CASCADE,
    norm_source_category_id INTEGER NOT NULL REFERENCES norm_source_categories(id) ON DELETE RESTRICT,
    citation TEXT NOT NULL,
    title TEXT,
    source_url TEXT,
    promulgation_date DATE,
    summary TEXT,
    notes TEXT,
    UNIQUE (legal_system_id, citation)
);

CREATE TABLE IF NOT EXISTS source_text_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legal_source_id INTEGER NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE,
    segment_ref TEXT NOT NULL,
    heading TEXT,
    text TEXT,
    start_position INTEGER,
    end_position INTEGER
);

CREATE TABLE IF NOT EXISTS actor_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT
);

-- Layer 1 actor scaffolding and fixtures for downstream tooling
CREATE TABLE IF NOT EXISTS actors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    actor_class_id INTEGER REFERENCES actor_classes(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city TEXT,
    state_province TEXT,
    postal_code TEXT,
    country_code TEXT
);

CREATE TABLE IF NOT EXISTS actor_person_details (
    actor_id INTEGER PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
    given_name TEXT NOT NULL,
    family_name TEXT NOT NULL,
    birthdate DATE,
    pronouns TEXT,
    gender TEXT,
    ethnicity TEXT,
    address_id INTEGER REFERENCES addresses(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS actor_org_details (
    actor_id INTEGER PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
    legal_name TEXT NOT NULL,
    registration_no TEXT,
    org_type TEXT,
    address_id INTEGER REFERENCES addresses(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS actor_contact_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    label TEXT,
    UNIQUE (actor_id, kind, value)
);

CREATE TABLE IF NOT EXISTS role_markers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marker TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    actor_class_id INTEGER REFERENCES actor_classes(id) ON DELETE SET NULL,
    legal_system_id INTEGER REFERENCES legal_systems(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relationship_kinds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    legal_system_id INTEGER REFERENCES legal_systems(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cultural_registers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    region TEXT,
    description TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_role_markers_unique
    ON role_markers(marker, COALESCE(legal_system_id, -1), COALESCE(actor_class_id, -1));

CREATE UNIQUE INDEX IF NOT EXISTS idx_relationship_kinds_unique
    ON relationship_kinds(code, COALESCE(legal_system_id, -1));

-- Seed priority legal systems
INSERT OR IGNORE INTO legal_systems (code, name, tradition, region, description, priority) VALUES
    ('AU.COMMON', 'Australia (Common Law)', 'COMMON', 'AU', 'Federated common law system across Australian jurisdictions.', 1),
    ('AU.STATE.QLD', 'Australia — Queensland', 'COMMON', 'AU', 'Queensland state system drawing on AU common law.', 1),
    ('PK.ISLAM.HANAFI', 'Pakistan — Hanafi Interpretation', 'ISLAMIC', 'PK', 'Hanafi jurisprudence applied within Pakistan.', 1),
    ('NZ.TIKANGA', 'Aotearoa New Zealand — Tikanga', 'CUSTOM', 'NZ', 'Tikanga Māori custom sources and community rules.', 1),
    ('US.STATE', 'United States — State Systems', 'COMMON', 'US', 'Representative US state jurisdictions.', 1),
    ('EU', 'European Union', 'CIVIL/INTEGRATION', 'EU', 'European Union regulations, directives, and case law.', 1);

-- Seed norm source categories
INSERT OR IGNORE INTO norm_source_categories (code, label, description) VALUES
    ('STATUTE', 'Statute or Act', 'Primary legislation enacted by a parliament or legislature.'),
    ('REGULATION', 'Regulation', 'Delegated legislation or rules issued under statutory authority.'),
    ('CASE', 'Case Law', 'Judicial decisions with precedential weight.'),
    ('TREATY', 'Treaty', 'International treaties or conventions.'),
    ('CUSTOM', 'Customary or Community Rule', 'Non-codified custom or tikanga sources.'),
    ('RELIGIOUS_TEXT', 'Religious Text', 'Faith-based sources with normative content.'),
    ('COMMUNITY_RULE', 'Community Rule', 'Community-authored protocols or bylaws.');

-- Seed actor classes
INSERT OR IGNORE INTO actor_classes (code, label, description) VALUES
    ('individual', 'Individual', 'Natural person or individual actor.'),
    ('corporate', 'Corporate', 'Corporations, companies, or incorporated associations.'),
    ('state_actor', 'State Actor', 'Government agencies, regulators, or the Crown.'),
    ('tribunal', 'Tribunal or Court', 'Judicial or quasi-judicial bodies.'),
    ('customary_authority', 'Customary Authority', 'Iwi, hapū, village councils, or elders with authority under custom.'),
    ('ngo', 'Non-governmental Organisation', 'Civil society or advocacy organisation.');

-- Seed role markers with optional system scoping
INSERT OR IGNORE INTO role_markers (marker, label, description, actor_class_id, legal_system_id) VALUES
    ('plaintiff', 'Plaintiff', 'Civil claimant bringing a proceeding.', (SELECT id FROM actor_classes WHERE code = 'individual'), NULL),
    ('defendant', 'Defendant', 'Person or entity responding to allegations.', (SELECT id FROM actor_classes WHERE code = 'individual'), NULL),
    ('appellant', 'Appellant', 'Party appealing a prior decision.', (SELECT id FROM actor_classes WHERE code = 'individual'), NULL),
    ('respondent', 'Respondent', 'Party responding to an appeal or application.', (SELECT id FROM actor_classes WHERE code = 'individual'), NULL),
    ('prosecutor', 'Prosecutor', 'State actor bringing criminal proceedings.', (SELECT id FROM actor_classes WHERE code = 'state_actor'), (SELECT id FROM legal_systems WHERE code = 'AU.COMMON')),
    ('crown', 'Crown', 'The Crown as a prosecuting or representing authority.', (SELECT id FROM actor_classes WHERE code = 'state_actor'), (SELECT id FROM legal_systems WHERE code = 'NZ.TIKANGA')),
    ('regulator', 'Regulator', 'Agency enforcing statutory standards.', (SELECT id FROM actor_classes WHERE code = 'state_actor'), (SELECT id FROM legal_systems WHERE code = 'US.STATE')),
    ('iwi', 'Iwi', 'Tribal authority under tikanga Māori.', (SELECT id FROM actor_classes WHERE code = 'customary_authority'), (SELECT id FROM legal_systems WHERE code = 'NZ.TIKANGA')),
    ('hapū', 'Hapū', 'Sub-tribal authority under tikanga Māori.', (SELECT id FROM actor_classes WHERE code = 'customary_authority'), (SELECT id FROM legal_systems WHERE code = 'NZ.TIKANGA')),
    ('mufti', 'Mufti', 'Islamic jurist issuing guidance.', (SELECT id FROM actor_classes WHERE code = 'customary_authority'), (SELECT id FROM legal_systems WHERE code = 'PK.ISLAM.HANAFI')),
    ('judge', 'Judge', 'Judicial decision maker.', (SELECT id FROM actor_classes WHERE code = 'tribunal'), NULL);

-- Seed relationship kinds with optional system scoping
INSERT OR IGNORE INTO relationship_kinds (code, label, description, legal_system_id) VALUES
    ('family', 'Family or Whānau', 'Kinship, guardianship, and whānau ties.', NULL),
    ('contract', 'Contractual', 'Contractual or commercial obligations between parties.', NULL),
    ('fiduciary', 'Fiduciary', 'Trust, fiduciary, or agency relationships.', NULL),
    ('governmental', 'Governmental', 'State-to-person relationships including regulation.', NULL),
    ('communal', 'Communal or Customary', 'Community-centric obligations grounded in tikanga or custom.', (SELECT id FROM legal_systems WHERE code = 'NZ.TIKANGA')),
    ('religious', 'Religious Authority', 'Obligations grounded in religious hierarchy.', (SELECT id FROM legal_systems WHERE code = 'PK.ISLAM.HANAFI'));

-- Seed cultural registers (optional Layer 5 scaffolding)
INSERT OR IGNORE INTO cultural_registers (code, label, region, description) VALUES
    ('tikanga', 'Tikanga Māori', 'Aotearoa New Zealand', 'Cultural register for tikanga Māori reasoning.'),
    ('sharia', 'Sharia', 'Pakistan', 'Islamic jurisprudential register.'),
    ('common_law', 'Common Law', 'Commonwealth', 'Shared common law interpretive context.');
