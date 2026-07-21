-- Migration 008 was authored against the superseded compiler_document carrier.
-- The active PostgreSQL runtime persists canonical documents in corpus.document.
-- Nonempty candidate-set proofs exercise these foreign keys, so move them onto
-- the authoritative operational document table before any binding rows are
-- admitted.

ALTER TABLE pnf.factor_anchor
    DROP CONSTRAINT IF EXISTS factor_anchor_document_ref_fkey;
ALTER TABLE pnf.factor_anchor
    ADD CONSTRAINT factor_anchor_document_ref_fkey
    FOREIGN KEY (document_ref)
    REFERENCES corpus.document(document_ref)
    ON DELETE CASCADE;

ALTER TABLE resolution.binding_candidate_set
    DROP CONSTRAINT IF EXISTS binding_candidate_set_document_ref_fkey;
ALTER TABLE resolution.binding_candidate_set
    ADD CONSTRAINT binding_candidate_set_document_ref_fkey
    FOREIGN KEY (document_ref)
    REFERENCES corpus.document(document_ref)
    ON DELETE CASCADE;
