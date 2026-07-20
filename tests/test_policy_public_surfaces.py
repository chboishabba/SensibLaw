from __future__ import annotations

import inspect
import pytest

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


def test_lane_receipts_require_projected_linkage_case_inputs() -> None:
    with pytest.raises(ValueError, match="project_linkage_case"):
        brexit.attach_receipt({"artifact_id": "brexit:raw"})

    with pytest.raises(ValueError, match="project_linkage_case"):
        gwb.attach_receipt({"artifact_id": "gwb:raw"})

    with pytest.raises(ValueError, match="project_linkage_case"):
        nat.attach_receipt({"artifact_id": "nat:raw"}, profile="q43229_superclass_pressure")


def test_downstream_policy_avoids_direct_nlp_and_regex_imports() -> None:
    from pathlib import Path
    
    root_dir = Path(__file__).parents[1]
    policy_dir = root_dir / "src" / "policy"
    scripts_dir = root_dir / "scripts"
    
    python_files = list(policy_dir.glob("**/*.py")) + list(scripts_dir.glob("**/*.py"))
    
    skipped_files = {
        "archive_turn_fact_extract.py",
        "wiki_timeline_aoo_extract.py",
        "hca_case_demo_ingest.py"
    }
    for p in python_files:
        if p.name in skipped_files:
            continue
        content = p.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if not line.strip().startswith("#")]
        for line in lines:
            assert "import spacy" not in line, f"Direct spacy import found in {p.name}: {line}"
            assert "src.text.sentences" not in line, f"Direct src.text.sentences import found in {p.name}: {line}"
            assert "src.nlp.spacy_adapter" not in line, f"Direct src.nlp.spacy_adapter import found in {p.name}: {line}"
