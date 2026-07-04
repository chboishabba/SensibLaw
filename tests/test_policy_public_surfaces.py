from __future__ import annotations

import inspect

from src.ontology import nat
from src.policy import au, brexit, gwb


def test_lane_wrappers_export_generic_verbs_only() -> None:
    assert set(au.__all__) == {"attach_receipt", "build_report", "build_world_model"}
    assert set(brexit.__all__) == {"attach_receipt", "build_report", "build_world_model", "load_records"}
    assert set(gwb.__all__) == {"attach_receipt", "build_report", "build_world_model"}
    assert set(nat.__all__) == {"attach_receipt", "build_report", "build_world_model", "load_fixture"}

    forbidden_tokens = ("gwb", "brexit", "au", "nat", "wikidata")
    for module in (au, brexit, gwb, nat):
        for name in module.__all__:
            lowered = name.casefold()
            assert lowered.startswith(("attach_", "build_", "load_"))
            assert not any(token in lowered for token in forbidden_tokens)


def test_gwb_and_nat_use_profile_selectors_not_kind() -> None:
    gwb_attach = inspect.signature(gwb.attach_receipt)
    gwb_build = inspect.signature(gwb.build_report)
    nat_attach = inspect.signature(nat.attach_receipt)
    nat_build = inspect.signature(nat.build_report)
    nat_world_model = inspect.signature(nat.build_world_model)

    assert "profile" in gwb_attach.parameters
    assert "kind" not in gwb_attach.parameters
    assert "profile" in gwb_build.parameters
    assert "profile" in nat_attach.parameters
    assert "profile" in nat_build.parameters
    assert "profile" in nat_world_model.parameters
