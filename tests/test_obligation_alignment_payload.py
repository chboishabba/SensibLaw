from src.obligation_alignment import ALIGNMENT_SCHEMA_VERSION, align_obligations, alignment_to_payload
from src.obligations import extract_obligations_from_text


def test_alignment_payload_changes_list():
    old = extract_obligations_from_text("The operator must keep records within 7 days.")
    new = extract_obligations_from_text("The operator must keep records within 14 days.")

    report = align_obligations(old, new)
    payload = alignment_to_payload(report)

    assert payload["version"] == ALIGNMENT_SCHEMA_VERSION
    assert not payload["added"]
    assert not payload["removed"]
    assert not payload["unchanged"]
    assert len(payload["modified"]) == 1
    changes = payload["modified"][0]["changes"]
    assert any(change["field"] == "scopes" for change in changes)
