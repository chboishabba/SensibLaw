BEGIN;

-- 095: preserve ambiguity and revision.  A contextual fit is not a scalar
-- identity decision, and a once-valid query/policy certificate may later be
-- superseded or withdrawn without deleting its provenance row.

-- One typed context coordinate has one explicit polarity per witness.  Missing
-- rows remain unknown; opposite evidence must be represented explicitly rather
-- than by absence.
CREATE UNIQUE INDEX IF NOT EXISTS semantic_pnf_world_context_axis_single_polarity_idx
    ON execution.semantic_pnf_world_context_axis_symbol
       (context_witness_id,axis_kind,symbol_id);
CREATE UNIQUE INDEX IF NOT EXISTS semantic_pnf_world_requirement_single_polarity_idx
    ON execution.semantic_pnf_world_candidate_requirement
       (world_entity_id,axis_kind,required_symbol_id);

-- Rank only within the mention-local label fibre.  A unique contextual choice
-- exists only when exactly one candidate has the maximum signed margin and that
-- candidate's full requirement set is positively witnessed.  Ties remain open.
CREATE OR REPLACE VIEW execution.semantic_pnf_world_context_choice_v1 AS
WITH ranked AS (
    SELECT fit.*,
           max(fit.signed_margin) OVER (
               PARTITION BY fit.context_witness_id,fit.token_id,fit.label_symbol_id
           ) AS maximum_margin
      FROM execution.semantic_pnf_world_context_fit_v1 AS fit
), top AS (
    SELECT ranked.*,
           count(*) FILTER (
               WHERE ranked.requirements_satisfied
                 AND ranked.signed_margin=ranked.maximum_margin
           ) OVER (
               PARTITION BY ranked.context_witness_id,ranked.token_id,ranked.label_symbol_id
           ) AS top_satisfied_count
      FROM ranked
)
SELECT top.*,
       (top.requirements_satisfied
        AND top.signed_margin=top.maximum_margin
        AND top.top_satisfied_count=1) AS unique_preference
  FROM top;

-- Automatic contextual attachment refuses unresolved ties.  This remains a
-- mention-local attachment only: the function does not call an identity-admission
-- function and carries no permission to promote a Wikidata/world identity.
CREATE OR REPLACE FUNCTION execution.attach_numeric_pnf_world_candidate(
    selected_token_id BIGINT,
    selected_label_symbol_id BIGINT,
    selected_world_entity_id BIGINT,
    selected_context_witness_id BIGINT
) RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE witness_region BIGINT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_label_world_candidate AS candidate
         WHERE candidate.label_symbol_id=selected_label_symbol_id
           AND candidate.world_entity_id=selected_world_entity_id
    ) THEN
        RAISE EXCEPTION 'world candidate is not cached for this label';
    END IF;

    SELECT witness.region_id INTO witness_region
      FROM execution.semantic_pnf_world_context_witness AS witness
     WHERE witness.context_witness_id=selected_context_witness_id
       AND witness.token_id=selected_token_id;
    IF witness_region IS NULL THEN
        RAISE EXCEPTION 'context witness does not belong to mention token';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM execution.semantic_parser_token AS token
          JOIN execution.semantic_pnf_region AS region ON region.region_id=witness_region
          JOIN execution.semantic_pnf_run_identity AS run_identity
            ON run_identity.run_id=region.run_id AND run_identity.run_ref=token.run_ref
          JOIN execution.semantic_pnf_document_identity AS document_identity
            ON document_identity.document_id=region.document_id
           AND document_identity.document_ref=token.document_ref
         WHERE token.token_id=selected_token_id
           AND token.representation_version=2
           AND selected_label_symbol_id IN (token.orth_symbol_id,token.lemma_symbol_id)
           AND token.start_char>=region.start_char
           AND token.end_char<=region.end_char
    ) THEN
        RAISE EXCEPTION 'mention label/region is not justified by the numeric parser observation';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM execution.semantic_pnf_world_context_choice_v1 AS choice
         WHERE choice.context_witness_id=selected_context_witness_id
           AND choice.token_id=selected_token_id
           AND choice.label_symbol_id=selected_label_symbol_id
           AND choice.world_entity_id=selected_world_entity_id
           AND choice.unique_preference
    ) THEN
        RAISE EXCEPTION 'context does not provide a unique positively witnessed preference';
    END IF;

    INSERT INTO execution.semantic_pnf_mention_world_attachment
        (token_id,label_symbol_id,world_entity_id,context_witness_id,attachment_state)
    VALUES (selected_token_id,selected_label_symbol_id,selected_world_entity_id,
            selected_context_witness_id,1)
    ON CONFLICT DO NOTHING;
    RETURN TRUE;
END;
$$;

ALTER TABLE execution.semantic_pnf_consumer_sufficiency_certificate
    ADD COLUMN IF NOT EXISTS certificate_state SMALLINT NOT NULL DEFAULT 1
        CHECK (certificate_state IN (1,2));
-- 1 active, 2 withdrawn/superseded. Rows remain append-only evidence receipts.

CREATE OR REPLACE VIEW execution.semantic_pnf_consumer_sufficiency_current_v1 AS
SELECT DISTINCT ON (
           certificate.demand_id,certificate.consumer_ref,certificate.query_ref,
           certificate.policy_ref,certificate.certificate_kind
       )
       certificate.*
  FROM execution.semantic_pnf_consumer_sufficiency_certificate AS certificate
 ORDER BY certificate.demand_id,certificate.consumer_ref,certificate.query_ref,
          certificate.policy_ref,certificate.certificate_kind,
          certificate.revision DESC,certificate.certificate_id DESC;

CREATE OR REPLACE FUNCTION execution.numeric_pnf_consumer_stop_at_horizon(
    selected_demand_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT,
    selected_horizon SMALLINT
) RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT EXISTS (
    SELECT 1
      FROM execution.semantic_pnf_consumer_sufficiency_current_v1 AS certificate
     WHERE certificate.demand_id=selected_demand_id
       AND certificate.consumer_ref=selected_consumer_ref
       AND certificate.query_ref=selected_query_ref
       AND certificate.policy_ref=selected_policy_ref
       AND certificate.certificate_state=1
       AND certificate.horizon<=selected_horizon
       AND (
           -- A query-only consumer can stop on exact query factorisation or on
           -- a stronger future-safety certificate.
           (selected_policy_ref='' AND certificate.certificate_kind IN (1,3))
           OR
           -- Once a policy may act, query factorisation alone is insufficient;
           -- use restricted-policy safety or the stronger future certificate.
           (selected_policy_ref<>'' AND certificate.certificate_kind IN (2,3))
       )
);
$$;

CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_consumer_sufficiency(
    selected_demand_id BIGINT,
    selected_consumer_ref TEXT,
    selected_query_ref TEXT,
    selected_policy_ref TEXT,
    selected_horizon SMALLINT,
    selected_certificate_kind SMALLINT,
    selected_residual_required BOOLEAN,
    selected_certificate_ref TEXT,
    selected_revision BIGINT,
    selected_certificate_state SMALLINT DEFAULT 1
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE new_id BIGINT;
BEGIN
    IF selected_horizon NOT IN (3,6,9) THEN
        RAISE EXCEPTION 'horizon must be 3, 6, or 9';
    END IF;
    IF selected_certificate_kind NOT IN (1,2,3) THEN
        RAISE EXCEPTION 'certificate_kind must be query, policy, or future safety';
    END IF;
    IF selected_certificate_state NOT IN (1,2) THEN
        RAISE EXCEPTION 'certificate_state must be active or withdrawn';
    END IF;
    INSERT INTO execution.semantic_pnf_consumer_sufficiency_certificate
        (demand_id,consumer_ref,query_ref,policy_ref,horizon,certificate_kind,
         residual_required,certificate_ref,revision,certificate_state)
    VALUES (selected_demand_id,selected_consumer_ref,selected_query_ref,
            selected_policy_ref,selected_horizon,selected_certificate_kind,
            selected_residual_required,selected_certificate_ref,selected_revision,
            selected_certificate_state)
    RETURNING certificate_id INTO new_id;
    RETURN new_id;
END;
$$;

-- Current hot rows are demand-scoped.  NOT VALID preserves upgrade tolerance for
-- any legacy orphan while enforcing the foreign key for new/changed rows.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname='semantic_pnf_current_execution_demand_fkey'
    ) THEN
        ALTER TABLE execution.semantic_pnf_candidate_current_execution
            ADD CONSTRAINT semantic_pnf_current_execution_demand_fkey
            FOREIGN KEY(demand_id) REFERENCES execution.semantic_pnf_demand(demand_id)
            ON DELETE CASCADE NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname='semantic_pnf_current_admissibility_demand_fkey'
    ) THEN
        ALTER TABLE execution.semantic_pnf_candidate_current_admissibility
            ADD CONSTRAINT semantic_pnf_current_admissibility_demand_fkey
            FOREIGN KEY(demand_id) REFERENCES execution.semantic_pnf_demand(demand_id)
            ON DELETE CASCADE NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname='semantic_pnf_current_preference_demand_fkey'
    ) THEN
        ALTER TABLE execution.semantic_pnf_candidate_current_preference
            ADD CONSTRAINT semantic_pnf_current_preference_demand_fkey
            FOREIGN KEY(demand_id) REFERENCES execution.semantic_pnf_demand(demand_id)
            ON DELETE CASCADE NOT VALID;
    END IF;
END;
$$;

COMMIT;
