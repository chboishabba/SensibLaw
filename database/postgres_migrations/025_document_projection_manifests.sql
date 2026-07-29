BEGIN;

-- Immutable physical projection partitions.  They are execution and reuse
-- units only; a document manifest is required before semantic publication.
CREATE TABLE IF NOT EXISTS compiler_projection_partition (
    partition_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    source_sha256 BYTEA NOT NULL,
    carrier_ref TEXT NOT NULL,
    build_key_sha256 BYTEA NOT NULL,
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    owner_start INTEGER NOT NULL CHECK (owner_start >= 0),
    owner_end INTEGER NOT NULL CHECK (owner_end > owner_start),
    context_start INTEGER NOT NULL CHECK (context_start <= owner_start),
    context_end INTEGER NOT NULL CHECK (context_end >= owner_end),
    parser_contract_ref TEXT NOT NULL,
    reducer_contract_ref TEXT NOT NULL,
    payload JSONB NOT NULL,
    payload_sha256 BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, build_key_sha256, sequence_no)
);

CREATE TABLE IF NOT EXISTS compiler_document_projection_manifest (
    manifest_ref TEXT PRIMARY KEY,
    document_ref TEXT NOT NULL REFERENCES corpus.document(document_ref),
    source_sha256 BYTEA NOT NULL,
    carrier_ref TEXT NOT NULL,
    build_key_sha256 BYTEA NOT NULL,
    graph_ref TEXT NOT NULL,
    payload JSONB NOT NULL,
    manifest_sha256 BYTEA NOT NULL UNIQUE,
    published_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_ref, build_key_sha256)
);

CREATE TABLE IF NOT EXISTS compiler_document_projection_member (
    manifest_ref TEXT NOT NULL REFERENCES compiler_document_projection_manifest(manifest_ref) ON DELETE CASCADE,
    partition_ref TEXT NOT NULL REFERENCES compiler_projection_partition(partition_ref),
    sequence_no INTEGER NOT NULL,
    PRIMARY KEY (manifest_ref, partition_ref),
    UNIQUE (manifest_ref, sequence_no)
);

COMMIT;
