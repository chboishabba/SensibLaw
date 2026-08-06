BEGIN;

CREATE TABLE IF NOT EXISTS execution.semantic_parser_graph_work (
    work_ref TEXT PRIMARY KEY
        REFERENCES execution.semantic_work_item(work_ref) ON DELETE CASCADE,
    run_ref TEXT NOT NULL
        REFERENCES execution.semantic_run(run_ref) ON DELETE CASCADE,
    document_ref TEXT NOT NULL,
    sentence_ref TEXT
        REFERENCES execution.semantic_parser_sentence(sentence_ref) ON DELETE CASCADE,
    scope_kind TEXT NOT NULL CHECK (scope_kind IN ('sentence', 'document')),
    operation_kind TEXT NOT NULL CHECK (
        operation_kind IN (
            'mention_licensing',
            'operator_composition',
            'dependency_projection',
            'document_closure'
        )
    ),
    parser_coverage_required BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (scope_kind = 'sentence' AND sentence_ref IS NOT NULL
         AND parser_coverage_required = FALSE)
        OR
        (scope_kind = 'document' AND sentence_ref IS NULL
         AND parser_coverage_required = TRUE)
    ),
    UNIQUE (run_ref, document_ref, sentence_ref, operation_kind)
);

CREATE INDEX IF NOT EXISTS semantic_parser_graph_work_sentence_idx
    ON execution.semantic_parser_graph_work
       (run_ref, document_ref, sentence_ref, operation_kind);

COMMIT;
