-- Candidate-set references are query-critical demand structure, not JSON
-- payload. Persist them relationally after both the demand and set exist.

CREATE TABLE IF NOT EXISTS resolution.demand_candidate_set (
    demand_ref TEXT NOT NULL REFERENCES resolution.demand(demand_ref) ON DELETE CASCADE,
    candidate_set_ref TEXT NOT NULL
        REFERENCES resolution.binding_candidate_set(candidate_set_ref) ON DELETE CASCADE,
    PRIMARY KEY (demand_ref, candidate_set_ref)
);

CREATE INDEX IF NOT EXISTS demand_candidate_set_reverse_idx
    ON resolution.demand_candidate_set (candidate_set_ref, demand_ref);

CREATE OR REPLACE VIEW resolution.v_binding_demand AS
SELECT
    demand.demand_ref,
    demand.factor_ref,
    demand.factor_revision_ref,
    demand.subject_kind_ref,
    demand.formal_role_ref,
    demand.scope_ref,
    demand.budget_class_ref,
    candidate_set.candidate_set_ref,
    candidate_set.referential_type_ref,
    candidate_set.member_count,
    demand.demand_state_ref
FROM resolution.demand AS demand
JOIN resolution.demand_candidate_set AS link
  ON link.demand_ref = demand.demand_ref
JOIN resolution.binding_candidate_set AS candidate_set
  ON candidate_set.candidate_set_ref = link.candidate_set_ref;
