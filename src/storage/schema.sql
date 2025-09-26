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

CREATE TABLE IF NOT EXISTS toc (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    toc_id INTEGER NOT NULL,
    parent_id INTEGER,
    node_type TEXT,
    identifier TEXT,
    title TEXT,
    stable_id TEXT,
    position INTEGER NOT NULL,
    page_number INTEGER,
    PRIMARY KEY (doc_id, rev_id, toc_id),
    FOREIGN KEY (doc_id, rev_id) REFERENCES revisions(doc_id, rev_id),
    FOREIGN KEY (doc_id, rev_id, parent_id)
        REFERENCES toc(doc_id, rev_id, toc_id)
);

CREATE INDEX IF NOT EXISTS idx_toc_doc_rev
ON toc(doc_id, rev_id, toc_id);

CREATE INDEX IF NOT EXISTS idx_toc_parent
ON toc(doc_id, rev_id, parent_id);


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
    toc_id INTEGER,
    PRIMARY KEY (doc_id, rev_id, provision_id),
    FOREIGN KEY (doc_id, rev_id) REFERENCES revisions(doc_id, rev_id),
    FOREIGN KEY (doc_id, rev_id, toc_id)
        REFERENCES toc(doc_id, rev_id, toc_id)
);

CREATE INDEX IF NOT EXISTS idx_provisions_doc_rev
ON provisions(doc_id, rev_id, provision_id);


CREATE INDEX IF NOT EXISTS idx_provisions_toc
ON provisions(doc_id, rev_id, toc_id);

CREATE VIEW IF NOT EXISTS atoms AS
WITH subject_rows AS (
    SELECT
        ra.doc_id AS doc_id,
        ra.rev_id AS rev_id,
        ra.provision_id AS provision_id,
        ra.rule_id AS rule_id,
        0 AS group_order,
        0 AS sequence_order,
        COALESCE(rs.type, ra.atom_type, 'rule') AS type,
        COALESCE(rs.role, ra.role) AS role,
        COALESCE(rs.party, ra.party) AS party,
        COALESCE(rs.who, ra.who) AS who,
        COALESCE(rs.who_text, ra.who_text) AS who_text,
        COALESCE(rs.text, ra.text) AS text,
        COALESCE(rs.conditions, ra.conditions) AS conditions,
        rs.refs AS refs,
        COALESCE(rs.gloss, ra.subject_gloss) AS gloss,
        COALESCE(rs.gloss_metadata, ra.subject_gloss_metadata) AS gloss_metadata,
        COALESCE(rs.glossary_id, ra.glossary_id) AS glossary_id
    FROM rule_atoms AS ra
    LEFT JOIN rule_atom_subjects AS rs
        ON ra.doc_id = rs.doc_id
        AND ra.rev_id = rs.rev_id
        AND ra.provision_id = rs.provision_id
        AND ra.rule_id = rs.rule_id
), element_reference_json AS (
    SELECT
        doc_id,
        rev_id,
        provision_id,
        rule_id,
        element_id,
        json_group_array(
            COALESCE(
                citation_text,
                TRIM(
                    (CASE WHEN work IS NOT NULL AND work <> '' THEN work || ' ' ELSE '' END) ||
                    (CASE WHEN section IS NOT NULL AND section <> '' THEN section || ' ' ELSE '' END) ||
                    COALESCE(pinpoint, '')
                )
            )
        ) AS refs
    FROM rule_element_references
    GROUP BY doc_id, rev_id, provision_id, rule_id, element_id
), element_rows AS (
    SELECT
        ra.doc_id AS doc_id,
        ra.rev_id AS rev_id,
        ra.provision_id AS provision_id,
        re.rule_id AS rule_id,
        1 AS group_order,
        re.element_id AS sequence_order,
        COALESCE(re.atom_type, 'element') AS type,
        re.role AS role,
        ra.party AS party,
        ra.who AS who,
        ra.who_text AS who_text,
        re.text AS text,
        re.conditions AS conditions,
        er.refs AS refs,
        re.gloss AS gloss,
        re.gloss_metadata AS gloss_metadata,
        COALESCE(re.glossary_id, ra.glossary_id) AS glossary_id
    FROM rule_elements AS re
    JOIN rule_atoms AS ra
        ON ra.doc_id = re.doc_id
        AND ra.rev_id = re.rev_id
        AND ra.provision_id = re.provision_id
        AND ra.rule_id = re.rule_id
    LEFT JOIN element_reference_json AS er
        ON re.doc_id = er.doc_id
        AND re.rev_id = er.rev_id
        AND re.provision_id = er.provision_id
        AND re.rule_id = er.rule_id
        AND re.element_id = er.element_id
), lint_rows AS (
    SELECT
        ra.doc_id AS doc_id,
        ra.rev_id AS rev_id,
        ra.provision_id AS provision_id,
        rl.rule_id AS rule_id,
        2 AS group_order,
        rl.lint_id AS sequence_order,
        COALESCE(rl.atom_type, 'lint') AS type,
        rl.code AS role,
        ra.party AS party,
        ra.who AS who,
        ra.who_text AS who_text,
        rl.message AS text,
        NULL AS conditions,
        NULL AS refs,
        ra.subject_gloss AS gloss,
        rl.metadata AS gloss_metadata,
        ra.glossary_id AS glossary_id
    FROM rule_lints AS rl
    JOIN rule_atoms AS ra
        ON rl.doc_id = ra.doc_id
        AND rl.rev_id = ra.rev_id
        AND rl.provision_id = ra.provision_id
        AND rl.rule_id = ra.rule_id
)
SELECT
    doc_id,
    rev_id,
    provision_id,
    ROW_NUMBER() OVER (
        PARTITION BY doc_id, rev_id, provision_id
        ORDER BY rule_id, group_order, sequence_order
    ) AS atom_id,
    type,
    role,
    party,
    who,
    who_text,
    text,
    conditions,
    refs,
    gloss,
    gloss_metadata,
    glossary_id
FROM (
    SELECT * FROM subject_rows
    UNION ALL
    SELECT * FROM element_rows
    UNION ALL
    SELECT * FROM lint_rows
)
ORDER BY doc_id, rev_id, provision_id, atom_id;

CREATE TABLE IF NOT EXISTS rule_atoms (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
    text_hash TEXT NOT NULL,
    toc_id INTEGER,
    atom_type TEXT,
    role TEXT,
    party TEXT,
    who TEXT,
    who_text TEXT,
    actor TEXT,
    modality TEXT,
    action TEXT,
    conditions TEXT,
    scope TEXT,
    text TEXT,
    subject_gloss TEXT,
    subject_gloss_metadata TEXT,
    glossary_id INTEGER,
    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id),
    FOREIGN KEY (doc_id, rev_id, provision_id)
        REFERENCES provisions(doc_id, rev_id, provision_id),
    FOREIGN KEY (doc_id, rev_id, toc_id)
        REFERENCES toc(doc_id, rev_id, toc_id)
);

CREATE INDEX IF NOT EXISTS idx_rule_atoms_doc_rev
ON rule_atoms(doc_id, rev_id, provision_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rule_atoms_unique_text
ON rule_atoms(doc_id, rev_id, provision_id, party, role, text_hash);
CREATE INDEX IF NOT EXISTS idx_rule_atoms_toc
ON rule_atoms(doc_id, rev_id, toc_id);

CREATE TABLE IF NOT EXISTS rule_atom_subjects (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
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
    glossary_id INTEGER,
    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id),
    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id)
        REFERENCES rule_atoms(doc_id, rev_id, provision_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_rule_atom_subjects_doc_rev
ON rule_atom_subjects(doc_id, rev_id, provision_id);

CREATE TABLE IF NOT EXISTS rule_atom_references (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
    ref_index INTEGER NOT NULL,
    work TEXT,
    section TEXT,
    pinpoint TEXT,
    citation_text TEXT,
    glossary_id INTEGER,
    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, ref_index),
    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id)
        REFERENCES rule_atoms(doc_id, rev_id, provision_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_rule_atom_refs_doc_rev
ON rule_atom_references(doc_id, rev_id, provision_id, rule_id);

CREATE TABLE IF NOT EXISTS rule_elements (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
    element_id INTEGER NOT NULL,
    text_hash TEXT,
    atom_type TEXT,
    role TEXT,
    text TEXT,
    conditions TEXT,
    gloss TEXT,
    gloss_metadata TEXT,
    glossary_id INTEGER,
    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, element_id),
    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id)
        REFERENCES rule_atoms(doc_id, rev_id, provision_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_rule_elements_doc_rev
ON rule_elements(doc_id, rev_id, provision_id, rule_id);

CREATE TABLE IF NOT EXISTS rule_element_references (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
    element_id INTEGER NOT NULL,
    ref_index INTEGER NOT NULL,
    work TEXT,
    section TEXT,
    pinpoint TEXT,
    citation_text TEXT,
    glossary_id INTEGER,
    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, element_id, ref_index),
    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id, element_id)
        REFERENCES rule_elements(doc_id, rev_id, provision_id, rule_id, element_id)
);

CREATE INDEX IF NOT EXISTS idx_rule_element_refs_doc_rev
ON rule_element_references(doc_id, rev_id, provision_id, rule_id, element_id);

CREATE TABLE IF NOT EXISTS rule_lints (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
    lint_id INTEGER NOT NULL,
    atom_type TEXT,
    code TEXT,
    message TEXT,
    metadata TEXT,
    PRIMARY KEY (doc_id, rev_id, provision_id, rule_id, lint_id),
    FOREIGN KEY (doc_id, rev_id, provision_id, rule_id)
        REFERENCES rule_atoms(doc_id, rev_id, provision_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_rule_lints_doc_rev
ON rule_lints(doc_id, rev_id, provision_id, rule_id);

CREATE TABLE IF NOT EXISTS atom_references (
    doc_id INTEGER NOT NULL,
    rev_id INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    atom_id INTEGER NOT NULL,
    ref_index INTEGER NOT NULL,
    work TEXT,
    section TEXT,
    pinpoint TEXT,
    citation_text TEXT,
    PRIMARY KEY (doc_id, rev_id, provision_id, atom_id, ref_index)
);

CREATE INDEX IF NOT EXISTS idx_atom_references_doc_rev
ON atom_references(doc_id, rev_id, provision_id, atom_id);

CREATE VIRTUAL TABLE IF NOT EXISTS revisions_fts USING fts5(
    body, metadata, content='revisions', content_rowid='rowid'
);
