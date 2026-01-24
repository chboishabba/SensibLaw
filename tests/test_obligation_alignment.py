from src.obligation_alignment import align_obligations
from src.obligations import extract_obligations_from_text


def test_alignment_detects_added_removed_and_metadata_change():
    old_text = "The operator must keep records within 7 days."
    new_text = (
        "The operator must keep records within 14 days.\n"
        "A person must not enter the area."
    )

    old_obs = extract_obligations_from_text(old_text)
    new_obs = extract_obligations_from_text(new_text)

    report = align_obligations(old_obs, new_obs)

    assert len(report.added) == 1  # new prohibition
    assert len(report.removed) == 0
    assert len(report.unchanged) == 0  # scope change -> modified
    assert len(report.modified) == 1
    delta = report.modified[0]
    assert ("scopes" in delta.changes) or ("modality" in delta.changes)
    old_scope, new_scope = delta.changes.get("scopes")
    assert old_scope != new_scope


def test_alignment_is_stable_to_numbering_noise():
    base = extract_obligations_from_text("The operator must keep records.")
    noisy = extract_obligations_from_text("(1) The operator must keep records.")

    report = align_obligations(base, noisy)
    assert not report.added
    assert not report.removed
    assert not report.modified
    assert len(report.unchanged) == 1
