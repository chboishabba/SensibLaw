-- Milestone 2: Layer 2 Actors, Roles, and Social Context
-- Depends on: 001_layer1_normative.sql
BEGIN;

CREATE TABLE IF NOT EXISTS actor_class (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_marker (
    id BIGSERIAL PRIMARY KEY,
    marker TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    actor_class_id BIGINT REFERENCES actor_class(id) ON DELETE SET NULL,
    legal_system_id BIGINT REFERENCES legal_system(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relationship_kind (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    legal_system_id BIGINT REFERENCES legal_system(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cultural_register (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    region TEXT,
    description TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_role_marker_unique
    ON role_marker (marker, COALESCE(legal_system_id, -1), COALESCE(actor_class_id, -1));

CREATE UNIQUE INDEX IF NOT EXISTS idx_relationship_kind_unique
    ON relationship_kind (code, COALESCE(legal_system_id, -1));

-- Seed actor classes
INSERT INTO actor_class (code, label, description) VALUES
    ('individual', 'Individual', 'Natural person or individual actor.'),
    ('corporate', 'Corporate', 'Corporations, companies, or incorporated associations.'),
    ('state_actor', 'State Actor', 'Government agencies, regulators, or the Crown.'),
    ('tribunal', 'Tribunal or Court', 'Judicial or quasi-judicial bodies.'),
    ('customary_authority', 'Customary Authority', 'Iwi, hapū, village councils, or elders with authority under custom.'),
    ('ngo', 'Non-governmental Organisation', 'Civil society or advocacy organisation.')
ON CONFLICT (code) DO NOTHING;

-- Seed role markers with optional system scoping
INSERT INTO role_marker (marker, label, description, actor_class_id, legal_system_id) VALUES
    ('plaintiff', 'Plaintiff', 'Civil claimant bringing a proceeding.', (SELECT id FROM actor_class WHERE code = 'individual'), NULL),
    ('defendant', 'Defendant', 'Person or entity responding to allegations.', (SELECT id FROM actor_class WHERE code = 'individual'), NULL),
    ('appellant', 'Appellant', 'Party appealing a prior decision.', (SELECT id FROM actor_class WHERE code = 'individual'), NULL),
    ('respondent', 'Respondent', 'Party responding to an appeal or application.', (SELECT id FROM actor_class WHERE code = 'individual'), NULL),
    ('prosecutor', 'Prosecutor', 'State actor bringing criminal proceedings.', (SELECT id FROM actor_class WHERE code = 'state_actor'), (SELECT id FROM legal_system WHERE code = 'AU.COMMON')),
    ('crown', 'Crown', 'The Crown as a prosecuting or representing authority.', (SELECT id FROM actor_class WHERE code = 'state_actor'), (SELECT id FROM legal_system WHERE code = 'NZ.TIKANGA')),
    ('regulator', 'Regulator', 'Agency enforcing statutory standards.', (SELECT id FROM actor_class WHERE code = 'state_actor'), (SELECT id FROM legal_system WHERE code = 'US.STATE')),
    ('iwi', 'Iwi', 'Tribal authority under tikanga Māori.', (SELECT id FROM actor_class WHERE code = 'customary_authority'), (SELECT id FROM legal_system WHERE code = 'NZ.TIKANGA')),
    ('hapū', 'Hapū', 'Sub-tribal authority under tikanga Māori.', (SELECT id FROM actor_class WHERE code = 'customary_authority'), (SELECT id FROM legal_system WHERE code = 'NZ.TIKANGA')),
    ('mufti', 'Mufti', 'Islamic jurist issuing guidance.', (SELECT id FROM actor_class WHERE code = 'customary_authority'), (SELECT id FROM legal_system WHERE code = 'PK.ISLAM.HANAFI')),
    ('judge', 'Judge', 'Judicial decision maker.', (SELECT id FROM actor_class WHERE code = 'tribunal'), NULL)
ON CONFLICT DO NOTHING;

-- Seed relationship kinds with optional system scoping
INSERT INTO relationship_kind (code, label, description, legal_system_id) VALUES
    ('family', 'Family or Whānau', 'Kinship, guardianship, and whānau ties.', NULL),
    ('contract', 'Contractual', 'Contractual or commercial obligations between parties.', NULL),
    ('fiduciary', 'Fiduciary', 'Trust, fiduciary, or agency relationships.', NULL),
    ('governmental', 'Governmental', 'State-to-person relationships including regulation.', NULL),
    ('communal', 'Communal or Customary', 'Community-centric obligations grounded in tikanga or custom.', (SELECT id FROM legal_system WHERE code = 'NZ.TIKANGA')),
    ('religious', 'Religious Authority', 'Obligations grounded in religious hierarchy.', (SELECT id FROM legal_system WHERE code = 'PK.ISLAM.HANAFI'))
ON CONFLICT DO NOTHING;

-- Seed cultural registers (optional Layer 5 scaffolding)
INSERT INTO cultural_register (code, label, region, description) VALUES
    ('tikanga', 'Tikanga Māori', 'Aotearoa New Zealand', 'Cultural register for tikanga Māori reasoning.'),
    ('sharia', 'Sharia', 'Pakistan', 'Islamic jurisprudential register.'),
    ('common_law', 'Common Law', 'Commonwealth', 'Shared common law interpretive context.')
ON CONFLICT (code) DO NOTHING;

COMMIT;
