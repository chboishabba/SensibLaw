from src.text.profile_admissibility import apply_profile_admissibility


def _payload():
    text = "Civil Liability Act 2002 (NSW) s 5B applies to hosted service incidents."
    return {
        "source_text": text,
        "tokens": [
            {"t": "Civil", "start": 0, "end": 5},
            {"t": "Liability", "start": 6, "end": 15},
        ],
        "groups": [
            {"group_id": "statute_ref", "spans": [{"start": 0, "end": 31}]},
            {"group_id": "system_component", "spans": [{"start": 49, "end": 63}]},
        ],
        "axes": [
            {"axis_id": "jurisdiction", "value": "nsw", "spans": [{"start": 22, "end": 25}]},
            {"axis_id": "hosting", "value": "hosted", "spans": [{"start": 49, "end": 55}]},
        ],
        "overlays": [
            {"overlay_id": "citation", "spans": [{"start": 0, "end": 35}]},
            {"overlay_id": "ops_label", "spans": [{"start": 49, "end": 71}]},
        ],
    }


def test_sl_profile_filters_infra_items_and_keeps_tokens():
    payload = _payload()
    filtered, issues = apply_profile_admissibility(payload, "sl_profile")
    assert filtered["tokens"] == payload["tokens"]
    assert [g["group_id"] for g in filtered["groups"]] == ["statute_ref"]
    assert [a["axis_id"] for a in filtered["axes"]] == ["jurisdiction"]
    assert [o["overlay_id"] for o in filtered["overlays"]] == ["citation"]
    codes = [i.code for i in issues]
    assert "forbidden_group" in codes
    assert "forbidden_axis" in codes
    assert "forbidden_overlay" in codes


def test_infra_profile_filters_legal_items_and_keeps_infra_items():
    payload = _payload()
    filtered, issues = apply_profile_admissibility(payload, "infra_profile")
    assert [g["group_id"] for g in filtered["groups"]] == ["system_component"]
    assert [a["axis_id"] for a in filtered["axes"]] == ["hosting"]
    assert [o["overlay_id"] for o in filtered["overlays"]] == ["ops_label"]
    assert any(i.code == "forbidden_group" for i in issues)


def test_global_lint_rejects_empty_or_out_of_bounds_spans():
    payload = _payload()
    payload["groups"].append({"group_id": "statute_ref", "spans": []})
    payload["overlays"].append({"overlay_id": "citation", "spans": [{"start": 999, "end": 1002}]})
    _, issues = apply_profile_admissibility(payload, "sl_profile")
    codes = [i.code for i in issues]
    assert "empty_spans" in codes
    assert "span_oob" in codes


def test_unknown_profile_raises():
    payload = _payload()
    raised = False
    try:
        apply_profile_admissibility(payload, "unknown_profile")
    except ValueError:
        raised = True
    assert raised

