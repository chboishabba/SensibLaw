CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    data TEXT NOT NULL,
    valid_from TEXT NOT NULL DEFAULT '1970-01-01',
    valid_to TEXT,
    recorded_from TEXT NOT NULL DEFAULT '1970-01-01',
    recorded_to TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source INTEGER NOT NULL REFERENCES nodes(id),
    target INTEGER NOT NULL REFERENCES nodes(id),
    type TEXT NOT NULL,
    data TEXT,
    valid_from TEXT NOT NULL DEFAULT '1970-01-01',
    valid_to TEXT,
    recorded_from TEXT NOT NULL DEFAULT '1970-01-01',
    recorded_to TEXT
);

CREATE INDEX IF NOT EXISTS idx_nodes_valid ON nodes(valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_edges_valid ON edges(valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_nodes_recorded ON nodes(recorded_from, recorded_to);
CREATE INDEX IF NOT EXISTS idx_edges_recorded ON edges(recorded_from, recorded_to);

CREATE TABLE IF NOT EXISTS frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id),
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    template TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id),
    suggestion TEXT NOT NULL,
    data TEXT
);

CREATE TRIGGER IF NOT EXISTS prevent_corrections_delete
BEFORE DELETE ON corrections
BEGIN
    SELECT RAISE(ABORT, 'corrections table is append-only');
END;

CREATE TABLE IF NOT EXISTS glossary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT UNIQUE NOT NULL,
    definition TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    simhash TEXT,
    minhash TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT
);

CREATE TABLE IF NOT EXISTS revisions (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    effective_date TEXT NOT NULL,
    metadata TEXT NOT NULL,
    body TEXT NOT NULL,
    source_url TEXT,
    retrieved_at TEXT,
    checksum TEXT,
    licence TEXT,
    document_json TEXT,
    PRIMARY KEY (doc_id, rev_id),
    FOREIGN KEY (doc_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS provisions (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    parent_id INTEGER,
    identifier TEXT,
    heading TEXT,
    node_type TEXT,
    text TEXT,
    rule_tokens TEXT,
    references_json TEXT,
    principles TEXT,
    customs TEXT,
    cultural_flags TEXT,
    PRIMARY KEY (doc_id, rev_id, provision_id),
    FOREIGN KEY (doc_id, rev_id) REFERENCES revisions(doc_id, rev_id)
);

CREATE INDEX IF NOT EXISTS idx_provisions_doc_rev
ON provisions(doc_id, rev_id, provision_id);

CREATE TABLE IF NOT EXISTS atoms (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    atom_id INTEGER NOT NULL,
    type TEXT,
    role TEXT,
    party TEXT,
    who TEXT,
    who_text TEXT,
    text TEXT,
    conditions TEXT,
    refs TEXT,
    gloss TEXT,
    gloss_metadata TEXT,
    PRIMARY KEY (doc_id, rev_id, provision_id, atom_id),
    FOREIGN KEY (doc_id, rev_id, provision_id)
        REFERENCES provisions(doc_id, rev_id, provision_id)
);

CREATE INDEX IF NOT EXISTS idx_atoms_doc_rev
ON atoms(doc_id, rev_id, provision_id);

CREATE VIRTUAL TABLE IF NOT EXISTS revisions_fts USING fts5(
    body, metadata, content='revisions', content_rowid='rowid'
);
