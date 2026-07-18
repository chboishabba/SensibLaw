-- Document-level build receipts make an unchanged v0.7 rerun reusable even
-- when a document has zero binding candidate sets.

INSERT INTO execution.operation (operation_ref, operation_version)
VALUES ('compiler.document.local-binding', 'v0_7')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS execution.document_compilation_build (
    build_ref TEXT PRIMARY KEY REFERENCES execution.build(build_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref) ON DELETE CASCADE,
    compiler_contract_ref TEXT NOT NULL,
    graph_ref TEXT NOT NULL REFERENCES pnf.graph(graph_ref),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, compiler_contract_ref)
);

CREATE TABLE IF NOT EXISTS execution.document_compilation_build_demand (
    build_ref TEXT NOT NULL
        REFERENCES execution.document_compilation_build(build_ref) ON DELETE CASCADE,
    demand_ref TEXT NOT NULL REFERENCES resolution.demand(demand_ref) ON DELETE CASCADE,
    PRIMARY KEY (build_ref, demand_ref)
);

CREATE INDEX IF NOT EXISTS document_compilation_build_document_idx
    ON execution.document_compilation_build
        (document_ref, compiler_contract_ref, completed_at);
