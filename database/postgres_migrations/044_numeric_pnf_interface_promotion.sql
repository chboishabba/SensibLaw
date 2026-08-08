BEGIN;

CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_interface_export()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    region_kind_value SMALLINT;
    promotion_threshold_value DOUBLE PRECISION;
    repeated_child_count BIGINT;
    factor_participant BOOLEAN;
    outward_demand BOOLEAN;
BEGIN
    SELECT region.region_kind
      INTO region_kind_value
      FROM execution.semantic_pnf_interface AS interface
      JOIN execution.semantic_pnf_region AS region
        ON region.region_id = interface.region_id
     WHERE interface.interface_id = NEW.interface_id;

    IF region_kind_value IS NULL OR region_kind_value = 1 THEN
        RETURN NEW;
    END IF;
    IF NEW.target_kind <> 1 THEN
        RETURN NEW;
    END IF;

    SELECT promotion_threshold + (0.25 * GREATEST(region_kind_value - 1, 0))
      INTO promotion_threshold_value
      FROM execution.semantic_pnf_mdl_profile
     WHERE profile_id = 1;

    SELECT count(DISTINCT child_interface.interface_id)
      INTO repeated_child_count
      FROM execution.semantic_pnf_interface AS parent_interface
      JOIN execution.semantic_pnf_region AS child_region
        ON child_region.parent_region_id = parent_interface.region_id
      JOIN execution.semantic_pnf_interface AS child_interface
        ON child_interface.region_id = child_region.region_id
      JOIN execution.semantic_pnf_interface_export AS child_export
        ON child_export.interface_id = child_interface.interface_id
     WHERE parent_interface.interface_id = NEW.interface_id
       AND child_export.target_kind = 1
       AND child_export.key_symbol_id IS NOT DISTINCT FROM NEW.key_symbol_id;

    SELECT EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_interface AS parent_interface
          JOIN execution.semantic_pnf_region AS child_region
            ON child_region.parent_region_id = parent_interface.region_id
          JOIN execution.semantic_pnf_interface AS child_interface
            ON child_interface.region_id = child_region.region_id
          JOIN execution.semantic_pnf_interface_export AS factor_export
            ON factor_export.interface_id = child_interface.interface_id
           AND factor_export.target_kind = 2
          JOIN execution.semantic_pnf_hyperedge AS hyperedge
            ON hyperedge.factor_id = factor_export.target_id
         WHERE parent_interface.interface_id = NEW.interface_id
           AND hyperedge.object_id = NEW.target_id
    ) INTO factor_participant;

    SELECT EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_demand AS demand
         WHERE demand.source_region_id = (
             SELECT object.region_id
               FROM execution.semantic_pnf_object AS object
              WHERE object.object_id = NEW.target_id
         )
           AND demand.state = 1
    ) INTO outward_demand;

    IF NEW.promotion_score >= COALESCE(promotion_threshold_value, 0)
       OR repeated_child_count >= 2
       OR factor_participant
       OR outward_demand THEN
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_export_promotion
    ON execution.semantic_pnf_interface_export;
CREATE TRIGGER semantic_pnf_parent_export_promotion
BEFORE INSERT ON execution.semantic_pnf_interface_export
FOR EACH ROW
EXECUTE FUNCTION execution.admit_numeric_pnf_interface_export();

CREATE OR REPLACE FUNCTION execution.admit_numeric_pnf_interface_lookup()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.target_kind <> 1 THEN
        RETURN NEW;
    END IF;
    IF EXISTS (
        SELECT 1
          FROM execution.semantic_pnf_interface_export AS export
         WHERE export.interface_id = NEW.interface_id
           AND export.target_kind = NEW.target_kind
           AND export.target_id = NEW.target_id
    ) THEN
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_parent_lookup_promotion
    ON execution.semantic_pnf_interface_lookup;
CREATE TRIGGER semantic_pnf_parent_lookup_promotion
BEFORE INSERT ON execution.semantic_pnf_interface_lookup
FOR EACH ROW
EXECUTE FUNCTION execution.admit_numeric_pnf_interface_lookup();

CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_interface_measure()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.closure_state NOT IN (2, 3)
       OR OLD.closure_state IS NOT DISTINCT FROM NEW.closure_state THEN
        RETURN NEW;
    END IF;
    UPDATE execution.semantic_pnf_interface AS interface
       SET interface_cardinality = counts.total_count,
           promoted_object_count = counts.object_count,
           unresolved_count = counts.demand_count
      FROM (
          SELECT count(*) AS total_count,
                 count(*) FILTER (WHERE target_kind = 1) AS object_count,
                 count(*) FILTER (WHERE target_kind = 3) AS demand_count
            FROM execution.semantic_pnf_interface_export
           WHERE interface_id = (
               SELECT candidate.interface_id
                 FROM execution.semantic_pnf_interface AS candidate
                WHERE candidate.region_id = NEW.region_id
           )
      ) AS counts
     WHERE interface.region_id = NEW.region_id;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS semantic_pnf_interface_measure_refresh
    ON execution.semantic_pnf_region;
CREATE TRIGGER semantic_pnf_interface_measure_refresh
AFTER UPDATE OF closure_state
ON execution.semantic_pnf_region
FOR EACH ROW
EXECUTE FUNCTION execution.refresh_numeric_pnf_interface_measure();

COMMIT;
