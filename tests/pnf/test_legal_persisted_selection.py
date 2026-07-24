from src.pnf.legal_adjunct import (
    PersistedLegalSource,
    plan_legal_sources,
    project_acquisition_requirements,
    project_normative_interaction_demands,
)


def test_legal_plan_selects_persisted_authority_or_remains_blocked() -> None:
    demands = project_normative_interaction_demands(
        (
            {
                "demand_ref": "demand:drive",
                "factor_revision_ref": "revision:1",
                "structural_signature_ref": "signature:1",
                "requested_facets": (
                    "legal.relevance_unresolved",
                    "legal.jurisdiction:AU",
                    "legal.source_role:primary_legislation",
                    "legal.authority_level:official",
                ),
            },
        )
    )
    blocked = plan_legal_sources(demands)
    assert blocked[0].state == "blocked_acquisition_required"
    assert project_acquisition_requirements(blocked)[0].demand_ref == "demand:drive"
    ready = plan_legal_sources(
        demands,
        (
            PersistedLegalSource(
                "revision:act", "AU", "primary_legislation", "official"
            ),
        ),
    )
    assert ready[0].state == "ready_persisted"
    assert ready[0].selected_source_revision_refs == ("revision:act",)
