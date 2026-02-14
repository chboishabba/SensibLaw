from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DIM_PATH = ROOT / "data" / "ontology" / "wrong_type_dimensions_seed.yaml"
CATALOG_PATH = ROOT / "data" / "ontology" / "wrong_type_catalog_seed.yaml"


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"expected object in {path}"
    return data


def _codes(rows: list[dict]) -> list[str]:
    out: list[str] = []
    for row in rows:
        assert isinstance(row, dict), "dimension row must be object"
        code = str(row.get("code") or "").strip()
        assert code, "dimension row requires non-empty code"
        out.append(code)
    return out


def test_wrong_type_dimensions_seed_shape_and_uniqueness() -> None:
    data = _load_yaml(DIM_PATH)
    required = [
        "protected_interest_types",
        "mental_state_types",
        "interference_mode_types",
        "duty_structure_types",
        "defence_types",
        "remedy_types",
    ]
    for key in required:
        rows = data.get(key)
        assert isinstance(rows, list) and rows, f"{key} must be a non-empty list"
        codes = _codes(rows)
        assert len(codes) == len(set(codes)), f"{key} contains duplicate codes"


def test_wrong_type_catalog_mental_states_are_defined_in_dimension_seed() -> None:
    dimensions = _load_yaml(DIM_PATH)
    catalog = _load_yaml(CATALOG_PATH)

    allowed_states = set(_codes(list(dimensions.get("mental_state_types") or [])))
    assert allowed_states, "mental_state_types must be non-empty"

    catalogs = list(catalog.get("catalogs") or [])
    assert catalogs, "wrong_type catalog must include at least one catalog entry"
    for c in catalogs:
        wrong_types = list((c or {}).get("wrong_types") or [])
        for wt in wrong_types:
            for state in list((wt or {}).get("mental_states") or []):
                s = str(state or "").strip()
                assert s in allowed_states, f"unknown mental state '{s}' in wrong_type catalog"
