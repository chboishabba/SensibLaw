from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "src/policy/numeric_pnf_compilation.py"


def test_strict_numeric_compiler_defers_world_resolution_and_network() -> None:
    source = COMPILER.read_text(encoding="utf-8")
    assert '"world_resolution_deferred": True' in source
    assert '"network_performed": False' in source
    assert "wikidata_late_provider" not in source
    assert "execute_external_provider_batch" not in source
    assert "ExternalDemandRuntimeStore" not in source
