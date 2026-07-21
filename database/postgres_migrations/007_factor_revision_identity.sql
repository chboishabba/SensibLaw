BEGIN;

-- A factor keeps stable semantic identity while every state is immutable and
-- content-addressed. This is required for genuine factor-local refinement.
DROP VIEW IF EXISTS pnf.v_document_pnf;
DROP VIEW IF EXISTS corpus.v_document_summary;
DROP VIEW IF EXISTS resolution.v_unresolved_demand;

DROP TABLE IF EXISTS resolution.refinement_residual_transition;
DROP TABLE IF EXISTS resolution.refinement_alternative_transition;
DROP TABLE IF EXISTS resolution.refinement;
DROP TABLE IF EXISTS pnf.graph_factor;
DROP TABLE IF EXISTS algebra.factor_alternative;

ALTER TABLE algebra.factor
    ALTER COLUMN closure_state_ref DROP NOT NULL,
    ALTER COLUMN factor_sha256 DROP NOT NULL;
ALTER TABLE algebra.factor
    DROP CONSTRAINT IF EXISTS factor_factor_sha256_key;

CREATE TABLE IF NOT EXISTS algebra.factor_revision (
    factor_revision_ref text PRIMARY KEY,
    factor_ref text NOT NULL REFERENCES algebra.factor(factor_ref) ON DELETE CASCADE,
    closure_state_ref text NOT NULL,
    factor_sha256 bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS algebra.factor_revision_alternative (
    factor_revision_ref text NOT NULL
        REFERENCES algebra.factor_revision(factor_revision_ref) ON DELETE CASCADE,
    alternative_ref text NOT NULL REFERENCES algebra.alternative(alternative_ref),
    alternative_state_ref text NOT NULL,
    PRIMARY KEY (factor_revision_ref, alternative_ref)
);

CREATE TABLE IF NOT EXISTS pnf.graph_factor_revision (
    graph_ref text NOT NULL REFERENCES pnf.graph(graph_ref) ON DELETE CASCADE,
    factor_revision_ref text NOT NULL
        REFERENCES algebra.factor_revision(factor_revision_ref),
    graph_role_ref text NOT NULL,
    PRIMARY KEY (graph_ref, factor_revision_ref, graph_role_ref)
);

ALTER TABLE resolution.demand
    ADD COLUMN IF NOT EXISTS factor_revision_ref text
        REFERENCES algebra.factor_revision(factor_revision_ref);

CREATE TABLE resolution.refinement (
    refinement_ref text PRIMARY KEY,
    factor_ref text NOT NULL REFERENCES algebra.factor(factor_ref),
    prior_factor_revision_ref text NOT NULL
        REFERENCES algebra.factor_revision(factor_revision_ref),
    resulting_factor_revision_ref text NOT NULL
        REFERENCES algebra.factor_revision(factor_revision_ref),
    assessment_ref text REFERENCES resolution.assessment(assessment_ref),
    refinement_sha256 bytea NOT NULL UNIQUE
);

CREATE TABLE resolution.refinement_alternative_transition (
    refinement_ref text NOT NULL REFERENCES resolution.refinement(refinement_ref) ON DELETE CASCADE,
    alternative_ref text NOT NULL REFERENCES algebra.alternative(alternative_ref),
    transition_type_ref text NOT NULL CHECK (transition_type_ref IN ('added', 'retained', 'rejected')),
    PRIMARY KEY (refinement_ref, alternative_ref, transition_type_ref)
);

CREATE TABLE resolution.refinement_residual_transition (
    refinement_ref text NOT NULL REFERENCES resolution.refinement(refinement_ref) ON DELETE CASCADE,
    residual_ref text NOT NULL,
    prior_state_ref text,
    resulting_state_ref text,
    PRIMARY KEY (refinement_ref, residual_ref)
);

CREATE OR REPLACE VIEW pnf.v_document_pnf AS
SELECT
    g.document_ref,
    g.graph_ref,
    g.closure_state_ref AS graph_closure_state,
    f.factor_ref,
    fr.factor_revision_ref,
    f.factor_type_ref,
    fr.closure_state_ref AS factor_closure_state,
    fra.alternative_ref,
    a.type_ref,
    a.value_ref,
    a.value_literal,
    fra.alternative_state_ref
FROM pnf.graph AS g
JOIN pnf.graph_factor_revision AS gfr ON gfr.graph_ref = g.graph_ref
JOIN algebra.factor_revision AS fr
  ON fr.factor_revision_ref = gfr.factor_revision_ref
JOIN algebra.factor AS f ON f.factor_ref = fr.factor_ref
LEFT JOIN algebra.factor_revision_alternative AS fra
  ON fra.factor_revision_ref = fr.factor_revision_ref
LEFT JOIN algebra.alternative AS a ON a.alternative_ref = fra.alternative_ref;

CREATE OR REPLACE VIEW resolution.v_unresolved_demand AS
SELECT
    o.corpus_ref,
    d.document_ref,
    rd.demand_ref,
    rd.factor_ref,
    rd.factor_revision_ref,
    rd.subject_kind_ref,
    rd.formal_role_ref,
    rd.scope_ref,
    rd.semantic_key_sha256,
    rd.budget_class_ref,
    rd.demand_state_ref
FROM resolution.demand AS rd
JOIN algebra.factor AS f ON f.factor_ref = rd.factor_ref
JOIN corpus.document AS d ON d.document_ref = f.document_ref
JOIN corpus.document_occurrence AS o ON o.document_ref = d.document_ref
WHERE rd.demand_state_ref IN ('open', 'not_evaluated', 'budget_exhausted');

CREATE OR REPLACE VIEW corpus.v_document_summary AS
SELECT
    d.document_ref,
    count(DISTINCT f.factor_ref) AS factor_count,
    count(DISTINCT fr.factor_revision_ref) FILTER (
        WHERE fr.closure_state_ref IN ('closed', 'locally_closed', 'not_required')
    ) AS closed_factor_count,
    count(DISTINCT r.residual_ref) FILTER (
        WHERE r.residual_state_ref NOT IN ('closed', 'discharged')
    ) AS open_residual_count,
    count(DISTINCT rd.demand_ref) FILTER (
        WHERE rd.demand_state_ref IN ('open', 'not_evaluated', 'budget_exhausted')
    ) AS unresolved_demand_count
FROM corpus.document AS d
LEFT JOIN algebra.factor AS f ON f.document_ref = d.document_ref
LEFT JOIN algebra.factor_revision AS fr ON fr.factor_ref = f.factor_ref
LEFT JOIN algebra.residual AS r ON r.target_ref = fr.factor_revision_ref
LEFT JOIN resolution.demand AS rd ON rd.factor_ref = f.factor_ref
GROUP BY d.document_ref;

COMMIT;
