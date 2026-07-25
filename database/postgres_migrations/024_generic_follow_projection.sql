BEGIN;

CREATE TABLE IF NOT EXISTS pnf_follow_projection (
    projection_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL,
    profile_ref TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    projection_kind TEXT NOT NULL,
    source_graph_ref TEXT,
    source_resolution_ref TEXT REFERENCES pnf_resolution_receipt(resolution_ref),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    derived_only BOOLEAN NOT NULL DEFAULT TRUE CHECK (derived_only = TRUE),
    challengeable BOOLEAN NOT NULL DEFAULT TRUE CHECK (challengeable = TRUE),
    promotes_truth BOOLEAN NOT NULL DEFAULT FALSE CHECK (promotes_truth = FALSE),
    execution_authority BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_authority = FALSE),
    UNIQUE (document_ref, profile_ref, scope_ref, projection_kind)
);

CREATE TABLE IF NOT EXISTS pnf_follow_node (
    node_ref TEXT PRIMARY KEY,
    projection_ref TEXT NOT NULL REFERENCES pnf_follow_projection(projection_ref) ON DELETE CASCADE,
    node_kind TEXT NOT NULL,
    label TEXT NOT NULL,
    factor_ref TEXT,
    factor_revision_ref TEXT,
    assessment_ref TEXT REFERENCES pnf_candidate_assessment(assessment_ref),
    admissibility_receipt_ref TEXT REFERENCES pnf_admissibility_receipt(receipt_ref),
    resolution_ref TEXT REFERENCES pnf_resolution_receipt(resolution_ref),
    domain_ir_ref TEXT REFERENCES pnf_domain_ir(domain_ir_ref),
    source_revision_ref TEXT,
    ordinal INTEGER NOT NULL,
    derived_only BOOLEAN NOT NULL DEFAULT TRUE CHECK (derived_only = TRUE),
    UNIQUE (projection_ref, ordinal)
);

CREATE TABLE IF NOT EXISTS pnf_follow_edge (
    edge_ref TEXT PRIMARY KEY,
    projection_ref TEXT NOT NULL REFERENCES pnf_follow_projection(projection_ref) ON DELETE CASCADE,
    source_node_ref TEXT NOT NULL REFERENCES pnf_follow_node(node_ref),
    target_node_ref TEXT NOT NULL REFERENCES pnf_follow_node(node_ref),
    relation_kind TEXT NOT NULL,
    admissibility_state TEXT NOT NULL CHECK (
        admissibility_state IN ('admitted', 'rejected', 'blocked', 'undetermined', 'inapplicable')
    ),
    ordinal INTEGER NOT NULL,
    derived_only BOOLEAN NOT NULL DEFAULT TRUE CHECK (derived_only = TRUE),
    challengeable BOOLEAN NOT NULL DEFAULT TRUE CHECK (challengeable = TRUE),
    promotes_truth BOOLEAN NOT NULL DEFAULT FALSE CHECK (promotes_truth = FALSE),
    execution_authority BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_authority = FALSE),
    UNIQUE (projection_ref, ordinal),
    CHECK (source_node_ref <> target_node_ref OR relation_kind = 'self_reference')
);

CREATE TABLE IF NOT EXISTS pnf_follow_edge_evidence (
    edge_ref TEXT NOT NULL REFERENCES pnf_follow_edge(edge_ref) ON DELETE CASCADE,
    evidence_ref TEXT NOT NULL,
    evidence_role TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (edge_ref, evidence_ref, evidence_role)
);

CREATE TABLE IF NOT EXISTS pnf_follow_edge_provenance (
    edge_ref TEXT NOT NULL REFERENCES pnf_follow_edge(edge_ref) ON DELETE CASCADE,
    provenance_ref TEXT NOT NULL,
    provenance_role TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (edge_ref, provenance_ref, provenance_role)
);

CREATE TABLE IF NOT EXISTS pnf_follow_edge_admissibility_ground (
    edge_ref TEXT NOT NULL REFERENCES pnf_follow_edge(edge_ref) ON DELETE CASCADE,
    ground_ref TEXT NOT NULL,
    ground_kind TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (edge_ref, ground_ref, ground_kind)
);

CREATE INDEX IF NOT EXISTS pnf_follow_projection_document_idx
    ON pnf_follow_projection(document_ref, profile_ref, projection_kind);
CREATE INDEX IF NOT EXISTS pnf_follow_node_projection_kind_idx
    ON pnf_follow_node(projection_ref, node_kind, ordinal);
CREATE INDEX IF NOT EXISTS pnf_follow_edge_projection_relation_idx
    ON pnf_follow_edge(projection_ref, relation_kind, admissibility_state, ordinal);

CREATE OR REPLACE VIEW pnf_follow_projection_rows AS
SELECT
    p.projection_ref,
    p.document_ref,
    p.profile_ref,
    p.scope_ref,
    p.projection_kind,
    p.source_graph_ref,
    p.source_resolution_ref,
    n.node_ref,
    n.node_kind,
    n.label,
    n.factor_ref,
    n.factor_revision_ref,
    n.assessment_ref,
    n.admissibility_receipt_ref,
    n.resolution_ref,
    n.domain_ir_ref,
    n.source_revision_ref,
    n.ordinal AS node_ordinal,
    p.derived_only,
    p.challengeable,
    p.promotes_truth,
    p.execution_authority
FROM pnf_follow_projection p
JOIN pnf_follow_node n USING (projection_ref);

CREATE OR REPLACE VIEW pnf_follow_edge_rows AS
SELECT
    p.projection_ref,
    p.document_ref,
    p.profile_ref,
    p.scope_ref,
    p.projection_kind,
    e.edge_ref,
    e.source_node_ref,
    s.node_kind AS source_node_kind,
    s.label AS source_label,
    e.target_node_ref,
    t.node_kind AS target_node_kind,
    t.label AS target_label,
    e.relation_kind,
    e.admissibility_state,
    e.ordinal AS edge_ordinal,
    e.derived_only,
    e.challengeable,
    e.promotes_truth,
    e.execution_authority
FROM pnf_follow_projection p
JOIN pnf_follow_edge e USING (projection_ref)
JOIN pnf_follow_node s ON s.node_ref = e.source_node_ref
JOIN pnf_follow_node t ON t.node_ref = e.target_node_ref;

CREATE OR REPLACE VIEW pnf_legal_follow_projection AS
SELECT * FROM pnf_follow_edge_rows
WHERE projection_kind = 'legal';

CREATE OR REPLACE VIEW pnf_nonlegal_follow_projection AS
SELECT * FROM pnf_follow_edge_rows
WHERE projection_kind <> 'legal';

COMMIT;
