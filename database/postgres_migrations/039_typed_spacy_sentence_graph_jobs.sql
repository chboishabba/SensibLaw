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

CREATE OR REPLACE FUNCTION execution.enqueue_parser_sentence_graph_work()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    operation_value TEXT;
    stage_ref_value TEXT;
    work_ref_value TEXT;
    source_digest BYTEA;
    sentence_digest BYTEA;
BEGIN
    SELECT source.content_sha256
      INTO source_digest
      FROM execution.semantic_parser_partition AS partition
      JOIN execution.semantic_parser_source AS source
        ON source.source_ref = partition.source_ref
     WHERE partition.partition_ref = NEW.partition_ref;

    sentence_digest := decode(right(NEW.sentence_ref, 64), 'hex');

    FOREACH operation_value IN ARRAY ARRAY[
        'mention_licensing',
        'operator_composition',
        'dependency_projection'
    ]
    LOOP
        stage_ref_value :=
            'parser-stage:' || operation_value || ':' || NEW.run_ref || ':' || NEW.document_ref;
        work_ref_value :=
            'parser-work:' || operation_value || ':' || NEW.sentence_ref;

        INSERT INTO execution.semantic_stage_instance
            (stage_instance_ref, run_ref, document_ref,
             stage_contract_ref, operation_ref, state,
             input_manifest_sha256)
        VALUES (
            stage_ref_value,
            NEW.run_ref,
            NEW.document_ref,
            'parser-sentence-graph:v1',
            operation_value,
            'running',
            source_digest
        )
        ON CONFLICT (stage_instance_ref) DO NOTHING;

        INSERT INTO execution.semantic_work_item
            (work_ref, stage_instance_ref, run_ref, document_ref,
             stage_contract_ref, operation_ref, partition_ref,
             ordinal, input_manifest, input_sha256, state)
        VALUES (
            work_ref_value,
            stage_ref_value,
            NEW.run_ref,
            NEW.document_ref,
            'parser-sentence-graph:v1',
            operation_value,
            NEW.sentence_ref,
            NEW.start_char,
            NULL,
            sentence_digest,
            'ready'
        )
        ON CONFLICT (work_ref) DO NOTHING;

        INSERT INTO execution.semantic_parser_graph_work
            (work_ref, run_ref, document_ref, sentence_ref,
             scope_kind, operation_kind, parser_coverage_required)
        VALUES (
            work_ref_value,
            NEW.run_ref,
            NEW.document_ref,
            NEW.sentence_ref,
            'sentence',
            operation_value,
            FALSE
        )
        ON CONFLICT (work_ref) DO NOTHING;
    END LOOP;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_sentence_graph_work
    ON execution.semantic_parser_sentence;
CREATE TRIGGER semantic_parser_sentence_graph_work
AFTER INSERT ON execution.semantic_parser_sentence
FOR EACH ROW
EXECUTE FUNCTION execution.enqueue_parser_sentence_graph_work();

CREATE OR REPLACE FUNCTION execution.enqueue_parser_document_graph_work()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    stage_ref_value TEXT;
    work_ref_value TEXT;
    source_digest BYTEA;
BEGIN
    IF NEW.state <> 'complete' OR OLD.state = 'complete' THEN
        RETURN NEW;
    END IF;

    SELECT content_sha256
      INTO source_digest
      FROM execution.semantic_parser_source
     WHERE run_ref = NEW.run_ref
       AND document_ref = NEW.document_ref
     ORDER BY created_at DESC
     LIMIT 1;

    stage_ref_value :=
        'parser-stage:document_closure:' || NEW.run_ref || ':' || NEW.document_ref;
    work_ref_value :=
        'parser-work:document_closure:' || NEW.run_ref || ':' || NEW.document_ref;

    INSERT INTO execution.semantic_stage_instance
        (stage_instance_ref, run_ref, document_ref,
         stage_contract_ref, operation_ref, state,
         input_manifest_sha256)
    VALUES (
        stage_ref_value,
        NEW.run_ref,
        NEW.document_ref,
        'parser-document-graph:v1',
        'document_closure',
        'running',
        source_digest
    )
    ON CONFLICT (stage_instance_ref) DO NOTHING;

    INSERT INTO execution.semantic_work_item
        (work_ref, stage_instance_ref, run_ref, document_ref,
         stage_contract_ref, operation_ref, partition_ref,
         ordinal, input_manifest, input_sha256, state)
    VALUES (
        work_ref_value,
        stage_ref_value,
        NEW.run_ref,
        NEW.document_ref,
        'parser-document-graph:v1',
        'document_closure',
        NEW.document_ref,
        0,
        NULL,
        source_digest,
        'ready'
    )
    ON CONFLICT (work_ref) DO NOTHING;

    INSERT INTO execution.semantic_parser_graph_work
        (work_ref, run_ref, document_ref, sentence_ref,
         scope_kind, operation_kind, parser_coverage_required)
    VALUES (
        work_ref_value,
        NEW.run_ref,
        NEW.document_ref,
        NULL,
        'document',
        'document_closure',
        TRUE
    )
    ON CONFLICT (work_ref) DO NOTHING;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_parser_document_graph_work
    ON execution.semantic_parser_document_coverage;
CREATE TRIGGER semantic_parser_document_graph_work
AFTER UPDATE OF state ON execution.semantic_parser_document_coverage
FOR EACH ROW
EXECUTE FUNCTION execution.enqueue_parser_document_graph_work();

COMMIT;
