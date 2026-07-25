BEGIN;

-- A derived projection, not a second graph authority. JSON payloads may carry
-- display annotations, but every semantic relation has a queryable row below.
CREATE TABLE IF NOT EXISTS pnf_follow_projection (
    projection_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    projection_kind TEXT NOT NULL,
    authority_ceiling TEXT NOT NULL DEFAULT 'derived_only_challengeable'
        CHECK (authority_ceiling = 'derived_only_challengeable'),
    promotion_allowed BOOLEAN NOT NULL DEFAULT FALSE CHECK (promotion_allowed = FALSE),
    execution_allowed BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_allowed = FALSE),
    payload JSONB NOT NULL,
    projection_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pnf_follow_node (
    projection_ref TEXT NOT NULL REFERENCES pnf_follow_projection(projection_ref) ON DELETE CASCADE,
    node_ref TEXT NOT NULL,
    node_kind TEXT NOT NULL,
    label TEXT NOT NULL,
    document_ref TEXT REFERENCES corpus.document(document_ref),
    factor_revision_ref TEXT REFERENCES algebra.factor_revision(factor_revision_ref),
    domain_ir_ref TEXT REFERENCES pnf_domain_ir(domain_ir_ref),
    source_record_ref TEXT,
    PRIMARY KEY (projection_ref, node_ref)
);

CREATE TABLE IF NOT EXISTS pnf_follow_edge (
    projection_ref TEXT NOT NULL REFERENCES pnf_follow_projection(projection_ref) ON DELETE CASCADE,
    edge_ref TEXT PRIMARY KEY,
    from_node_ref TEXT NOT NULL,
    to_node_ref TEXT NOT NULL,
    relation_kind TEXT NOT NULL,
    admissibility_state TEXT NOT NULL CHECK (admissibility_state IN ('admissible', 'challengeable', 'blocked', 'rejected')),
    CHECK (from_node_ref <> to_node_ref),
    FOREIGN KEY (projection_ref, from_node_ref) REFERENCES pnf_follow_node(projection_ref, node_ref),
    FOREIGN KEY (projection_ref, to_node_ref) REFERENCES pnf_follow_node(projection_ref, node_ref)
);

CREATE TABLE IF NOT EXISTS pnf_follow_edge_provenance (
    edge_ref TEXT NOT NULL REFERENCES pnf_follow_edge(edge_ref) ON DELETE CASCADE,
    provenance_ref TEXT NOT NULL,
    evidence_ref TEXT,
    PRIMARY KEY (edge_ref, provenance_ref, evidence_ref)
);

CREATE TABLE IF NOT EXISTS pnf_follow_edge_admissibility_ground (
    edge_ref TEXT NOT NULL REFERENCES pnf_follow_edge(edge_ref) ON DELETE CASCADE,
    ground_ref TEXT NOT NULL,
    assessment_ref TEXT REFERENCES pnf_candidate_assessment(assessment_ref),
    admissibility_receipt_ref TEXT REFERENCES pnf_admissibility_receipt(receipt_ref),
    resolution_ref TEXT REFERENCES pnf_resolution_receipt(resolution_ref),
    PRIMARY KEY (edge_ref, ground_ref)
);

CREATE OR REPLACE VIEW pnf_v_legal_follow_projection AS
SELECT p.projection_ref, p.document_ref, n.node_ref, n.node_kind, n.label,
       e.edge_ref, e.relation_kind, e.admissibility_state
FROM pnf_follow_projection p
JOIN pnf_follow_node n ON n.projection_ref = p.projection_ref
LEFT JOIN pnf_follow_edge e ON e.projection_ref = p.projection_ref
    AND (e.from_node_ref = n.node_ref OR e.to_node_ref = n.node_ref)
WHERE p.projection_kind = 'legal_follow';

CREATE OR REPLACE VIEW pnf_v_nonlegal_follow_projection AS
SELECT p.projection_ref, p.document_ref, n.node_ref, n.node_kind, n.label,
       e.edge_ref, e.relation_kind, e.admissibility_state
FROM pnf_follow_projection p
JOIN pnf_follow_node n ON n.projection_ref = p.projection_ref
LEFT JOIN pnf_follow_edge e ON e.projection_ref = p.projection_ref
    AND (e.from_node_ref = n.node_ref OR e.to_node_ref = n.node_ref)
WHERE p.projection_kind <> 'legal_follow';

COMMIT;
