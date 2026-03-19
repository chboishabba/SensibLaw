CREATE TABLE IF NOT EXISTS entity_relations (
    relation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    relation_key TEXT NOT NULL REFERENCES semantic_relation_vocab(relation_key),
    object_kind TEXT NOT NULL,
    object_id TEXT NOT NULL,
    assertion_origin TEXT NOT NULL,
    relation_status TEXT NOT NULL DEFAULT 'active',
    rule_key TEXT REFERENCES semantic_rule_vocab(rule_key),
    confidence REAL,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_relations_unique
    ON entity_relations(run_id, subject_kind, subject_id, relation_key, object_kind, object_id, assertion_origin, COALESCE(rule_key, ''));

CREATE INDEX IF NOT EXISTS idx_entity_relations_subject
    ON entity_relations(run_id, subject_kind, subject_id);

CREATE INDEX IF NOT EXISTS idx_entity_relations_object
    ON entity_relations(run_id, object_kind, object_id);

CREATE TABLE IF NOT EXISTS policy_outcomes (
    outcome_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    policy_key TEXT NOT NULL REFERENCES policy_vocab(policy_key),
    outcome_status TEXT NOT NULL DEFAULT 'active',
    trigger_assertion_id TEXT REFERENCES entity_class_assertions(assertion_id) ON DELETE SET NULL,
    trigger_relation_id TEXT REFERENCES entity_relations(relation_id) ON DELETE SET NULL,
    rule_key TEXT REFERENCES semantic_rule_vocab(rule_key),
    provenance_json TEXT NOT NULL DEFAULT '{}',
    reviewer TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_outcomes_unique
    ON policy_outcomes(run_id, target_kind, target_id, policy_key, COALESCE(rule_key, ''));

CREATE INDEX IF NOT EXISTS idx_policy_outcomes_target
    ON policy_outcomes(run_id, target_kind, target_id);

CREATE TABLE IF NOT EXISTS semantic_refresh_runs (
    refresh_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES fact_intake_runs(run_id) ON DELETE CASCADE,
    bridge_version TEXT NOT NULL,
    ruleset_version TEXT NOT NULL,
    refresh_kind TEXT NOT NULL,
    refresh_status TEXT NOT NULL,
    facts_serialized_count INTEGER NOT NULL DEFAULT 0,
    assertion_count INTEGER NOT NULL DEFAULT 0,
    relation_count INTEGER NOT NULL DEFAULT 0,
    policy_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_semantic_refresh_runs_run_id
    ON semantic_refresh_runs(run_id, created_at);
