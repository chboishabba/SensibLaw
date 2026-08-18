BEGIN;

-- Portable semantic receipts for the strict numeric compiler.
--
-- Dense BIGINT ids remain the execution representation, but they are explicitly
-- database-local.  A publication receipt therefore stores only roots derived
-- from source coordinates, stable symbol BYTEA digests, typed semantic state,
-- and proof-bearing content.  Timing, worker ids, lease epochs, cache state and
-- local surrogate allocation never enter these roots.
CREATE TABLE IF NOT EXISTS execution.numeric_semantic_publication_receipt (
    build_ref TEXT PRIMARY KEY
        REFERENCES execution.build(build_ref) ON DELETE CASCADE,
    receipt_version SMALLINT NOT NULL DEFAULT 1 CHECK (receipt_version = 1),
    receipt_sha256 BYTEA NOT NULL CHECK (octet_length(receipt_sha256) = 32),
    parser_root_sha256 BYTEA NOT NULL CHECK (octet_length(parser_root_sha256) = 32),
    object_root_sha256 BYTEA NOT NULL CHECK (octet_length(object_root_sha256) = 32),
    factor_root_sha256 BYTEA NOT NULL CHECK (octet_length(factor_root_sha256) = 32),
    residual_root_sha256 BYTEA NOT NULL CHECK (octet_length(residual_root_sha256) = 32),
    export_root_sha256 BYTEA NOT NULL CHECK (octet_length(export_root_sha256) = 32),
    proof_root_sha256 BYTEA NOT NULL CHECK (octet_length(proof_root_sha256) = 32),
    object_leaf_count BIGINT NOT NULL CHECK (object_leaf_count >= 0),
    factor_leaf_count BIGINT NOT NULL CHECK (factor_leaf_count >= 0),
    residual_leaf_count BIGINT NOT NULL CHECK (residual_leaf_count >= 0),
    export_leaf_count BIGINT NOT NULL CHECK (export_leaf_count >= 0),
    proof_leaf_count BIGINT NOT NULL CHECK (proof_leaf_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS numeric_semantic_publication_receipt_digest_idx
    ON execution.numeric_semantic_publication_receipt(receipt_sha256);

COMMIT;
