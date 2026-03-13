from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "docs" / "planning" / "assumption_controls_registry.json"


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_assumption_controls_registry_is_complete_and_unique() -> None:
    data = _load_registry()
    controls = data.get("controls")
    assert isinstance(controls, list) and controls, "Registry must declare controls."

    seen: set[str] = set()
    for row in controls:
        aid = str((row or {}).get("aid") or "").strip().upper()
        assert aid.startswith("A"), f"Invalid AID: {aid!r}"
        assert aid not in seen, f"Duplicate AID in registry: {aid}"
        seen.add(aid)

    expected = {f"A{i}" for i in range(1, 11)}
    assert seen == expected, f"Registry must enumerate A1..A10 exactly; got={sorted(seen)}"


def test_assumption_controls_fail_closed_for_unresolved_items() -> None:
    data = _load_registry()
    controls = data.get("controls") if isinstance(data.get("controls"), list) else []
    assert controls, "No controls found in registry."

    for row in controls:
        aid = str((row or {}).get("aid") or "").strip().upper()
        status = str((row or {}).get("status") or "").strip().lower()
        assert status in {"implemented", "waived"}, f"{aid}: invalid status={status!r}"

        if status == "implemented":
            tests = (row or {}).get("test_refs")
            assert isinstance(tests, list) and tests, f"{aid}: implemented controls must declare test_refs."
            continue

        waiver_rel = str((row or {}).get("waiver_receipt") or "").strip()
        assert waiver_rel, f"{aid}: unresolved control must declare waiver_receipt."
        waiver_path = REPO_ROOT / waiver_rel
        assert waiver_path.exists(), f"{aid}: waiver receipt missing at {waiver_path}"
        waiver_text = waiver_path.read_text(encoding="utf-8")
        assert aid in waiver_text, f"{aid}: waiver receipt must mention control ID."
