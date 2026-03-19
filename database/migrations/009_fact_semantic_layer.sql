CREATE TABLE IF NOT EXISTS semantic_class_vocab (
    class_key TEXT PRIMARY KEY,
    dimension TEXT NOT NULL,
    applies_to TEXT NOT NULL,
    class_status TEXT NOT NULL DEFAULT 'active',
    description TEXT,
    introduced_in_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_relation_vocab (
    relation_key TEXT PRIMARY KEY,
    subject_kind TEXT NOT NULL,
    object_kind TEXT NOT NULL,
    relation_status TEXT NOT NULL DEFAULT 'active',
    description TEXT,
    introduced_in_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_rule_vocab (
    rule_key TEXT PRIMARY KEY,
    engine_kind TEXT NOT NULL,
    ruleset_version TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_vocab (
    policy_key TEXT PRIMARY KEY,
    applies_to TEXT NOT NULL,
    policy_status TEXT NOT NULL DEFAULT 'active',
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entity_class_assertions (
    assertion_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    class_key TEXT NOT NULL REFERENCES semantic_class_vocab(class_key),
    assertion_origin TEXT NOT NULL,
    assertion_status TEXT NOT NULL DEFAULT 'active',
    rule_key TEXT REFERENCES semantic_rule_vocab(rule_key),
    confidence REAL,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_class_assertions_unique
    ON entity_class_assertions(run_id, target_kind, target_id, class_key, assertion_origin, COALESCE(rule_key, ''));

CREATE INDEX IF NOT EXISTS idx_entity_class_assertions_target
    ON entity_class_assertions(run_id, target_kind, target_id);

CREATE INDEX IF NOT EXISTS idx_entity_class_assertions_class
    ON entity_class_assertions(class_key);
