BEGIN;

-- 177: parent-region recurrence derivation must scale with the represented
-- descendant fibre, not with (candidate groups × descendant fibre).  Migration
-- 045 found recurrence heads once, but then re-ran the recursive descendant
-- traversal once for every repeated head symbol while materialising members.
-- Large adaptive blocks therefore amplified one semantic parent close into
-- hundreds of seconds of PL/pgSQL/SPI work and temp spill.
--
-- Preserve the same authority objects and identities while performing a bounded
-- number of set-wise passes:
--   descendants -> grouped recurrence authority
--   recurrence authority -> missing recurrence objects
--   descendants × groups -> recurrence members (one partitioned pass)
--   recurrence authority -> support/export/lookup publication
-- Sentence mention derivation and generic parent close semantics are untouched.

CREATE OR REPLACE FUNCTION execution.derive_numeric_region_recurrence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    selected_interface_id BIGINT;
    selected_object_kind BIGINT;
BEGIN
    IF NEW.region_kind = 1
       OR NEW.closure_state NOT IN (2, 3)
       OR OLD.closure_state IS NOT DISTINCT FROM NEW.closure_state THEN
        RETURN NEW;
    END IF;

    SELECT interface_id
      INTO selected_interface_id
      FROM execution.semantic_pnf_interface
     WHERE region_id = NEW.region_id;
    IF selected_interface_id IS NULL THEN
        RETURN NEW;
    END IF;

    selected_object_kind := execution.ensure_semantic_symbol(
        14::smallint, 'mention.recurrence_group'
    );

    -- One descendant traversal discovers every repeated active head symbol.
    WITH RECURSIVE descendants(region_id) AS MATERIALIZED (
        SELECT child.region_id
          FROM execution.semantic_pnf_region AS child
         WHERE child.parent_region_id = NEW.region_id
        UNION ALL
        SELECT child.region_id
          FROM descendants
          JOIN execution.semantic_pnf_region AS child
            ON child.parent_region_id = descendants.region_id
    ),
    grouped AS (
        SELECT mention.head_symbol_id,
               count(*)::BIGINT AS member_count
          FROM descendants
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id = descendants.region_id
         WHERE mention.active
         GROUP BY mention.head_symbol_id
        HAVING count(*) >= 2
    )
    INSERT INTO execution.semantic_pnf_recurrence_group
        (recurrence_digest, region_id, head_symbol_id, member_count)
    SELECT digest(
               int8send(NEW.region_id)
               || int8send(grouped.head_symbol_id)
               || int8send(grouped.member_count),
               'sha256'
           ),
           NEW.region_id,
           grouped.head_symbol_id,
           grouped.member_count
      FROM grouped
    ON CONFLICT (region_id, head_symbol_id)
    DO UPDATE SET member_count = EXCLUDED.member_count;

    -- Admit only recurrence objects that were absent before this close.  This
    -- matches migration 045's selected_object_id IS NULL branch: an already
    -- authoritative recurrence object is neither replaced nor spuriously
    -- reactivated merely because its parent is observed again.
    INSERT INTO execution.semantic_pnf_object
        (object_digest, region_id, object_kind_symbol_id,
         head_symbol_id, scope_region_id, promotion_level,
         information_gain, representation_cost, ambiguity_cost,
         promotion_score, active)
    SELECT digest(
               int8send(recurrence.recurrence_id)
               || int8send(NEW.region_id)
               || int8send(selected_object_kind),
               'sha256'
           ),
           NEW.region_id,
           selected_object_kind,
           recurrence.head_symbol_id,
           NEW.region_id,
           NEW.region_kind,
           recurrence.member_count,
           1.0,
           0.5,
           recurrence.member_count - 1.5,
           TRUE
      FROM execution.semantic_pnf_recurrence_group AS recurrence
     WHERE recurrence.region_id = NEW.region_id
       AND recurrence.object_id IS NULL
    ON CONFLICT (object_digest) DO UPDATE SET active = TRUE;

    UPDATE execution.semantic_pnf_recurrence_group AS recurrence
       SET object_id = object.object_id
      FROM execution.semantic_pnf_object AS object
     WHERE recurrence.region_id = NEW.region_id
       AND recurrence.object_id IS NULL
       AND object.object_digest = digest(
           int8send(recurrence.recurrence_id)
           || int8send(NEW.region_id)
           || int8send(selected_object_kind),
           'sha256'
       );

    -- The old function repeated this recursive traversal once per candidate.
    -- Here every member is produced in one pass and the historical per-group
    -- ordering is retained exactly by PARTITION BY recurrence_id.
    WITH RECURSIVE descendants(region_id) AS MATERIALIZED (
        SELECT child.region_id
          FROM execution.semantic_pnf_region AS child
         WHERE child.parent_region_id = NEW.region_id
        UNION ALL
        SELECT child.region_id
          FROM descendants
          JOIN execution.semantic_pnf_region AS child
            ON child.parent_region_id = descendants.region_id
    ),
    members AS (
        SELECT recurrence.recurrence_id,
               mention.mention_id,
               row_number() OVER (
                   PARTITION BY recurrence.recurrence_id
                   ORDER BY mention.start_char, mention.mention_id
               ) - 1 AS ordinal
          FROM execution.semantic_pnf_recurrence_group AS recurrence
          JOIN descendants ON TRUE
          JOIN execution.semantic_pnf_mention AS mention
            ON mention.region_id = descendants.region_id
           AND mention.head_symbol_id = recurrence.head_symbol_id
         WHERE recurrence.region_id = NEW.region_id
           AND mention.active
    )
    INSERT INTO execution.semantic_pnf_recurrence_member
        (recurrence_id, mention_id, ordinal)
    SELECT recurrence_id, mention_id, ordinal
      FROM members
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_object_mention_support
        (object_id, mention_id)
    SELECT recurrence.object_id,
           member.mention_id
      FROM execution.semantic_pnf_recurrence_group AS recurrence
      JOIN execution.semantic_pnf_recurrence_member AS member
        ON member.recurrence_id = recurrence.recurrence_id
     WHERE recurrence.region_id = NEW.region_id
       AND recurrence.object_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_export
        (interface_id, export_kind, target_kind, target_id,
         key_symbol_id, rank, promotion_score)
    SELECT selected_interface_id,
           1,
           1,
           recurrence.object_id,
           recurrence.head_symbol_id,
           0,
           recurrence.member_count - 1.5
      FROM execution.semantic_pnf_recurrence_group AS recurrence
     WHERE recurrence.region_id = NEW.region_id
       AND recurrence.object_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO execution.semantic_pnf_interface_lookup
        (interface_id, key_kind, key_a, key_b,
         target_kind, target_id, rank)
    SELECT selected_interface_id,
           3,
           recurrence.head_symbol_id,
           0,
           1,
           recurrence.object_id,
           0
      FROM execution.semantic_pnf_recurrence_group AS recurrence
     WHERE recurrence.region_id = NEW.region_id
       AND recurrence.object_id IS NOT NULL
    ON CONFLICT DO NOTHING;

    UPDATE execution.semantic_pnf_interface AS interface
       SET interface_cardinality = counts.total_count,
           promoted_object_count = counts.object_count,
           unresolved_count = counts.demand_count
      FROM (
          SELECT count(*) AS total_count,
                 count(*) FILTER (WHERE target_kind = 1) AS object_count,
                 count(*) FILTER (WHERE target_kind = 3) AS demand_count
            FROM execution.semantic_pnf_interface_export
           WHERE interface_id = selected_interface_id
      ) AS counts
     WHERE interface.interface_id = selected_interface_id;

    RETURN NEW;
END;
$$;

-- Keep the existing trigger identity/ordering. Replacing the function is enough
-- for upgraded databases and avoids creating a second closure authority.

COMMIT;
