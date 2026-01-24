from src.obligations import extract_obligations_from_text
from src.obligation_identity import compute_identities, diff_obligations


def test_numbering_changes_do_not_diff():
    a = "1. The operator must keep records."
    b = "(a) The operator must keep records."
    ids_a = compute_identities(extract_obligations_from_text(a, references=[], source_id="doc"))
    ids_b = compute_identities(extract_obligations_from_text(b, references=[], source_id="doc"))
    diff = diff_obligations(ids_a, ids_b)
    assert not diff.added
    assert not diff.removed


def test_ocr_spacing_noise_does_not_diff():
    a = "The operator must keep records."
    b = "The  operator  must   keep   records."
    ids_a = compute_identities(extract_obligations_from_text(a, references=[], source_id="doc"))
    ids_b = compute_identities(extract_obligations_from_text(b, references=[], source_id="doc"))
    diff = diff_obligations(ids_a, ids_b)
    assert not diff.added
    assert not diff.removed


def test_clause_reordering_stable_identities():
    a = "The operator must keep records. The operator must file returns."
    b = "The operator must file returns. The operator must keep records."
    ids_a = compute_identities(extract_obligations_from_text(a, references=[], source_id="doc"))
    ids_b = compute_identities(extract_obligations_from_text(b, references=[], source_id="doc"))
    diff = diff_obligations(ids_a, ids_b)
    assert not diff.added
    assert not diff.removed


def test_actor_action_flags_toggle_identity_components():
    text = "The operator must keep records."
    ids_with = compute_identities(extract_obligations_from_text(text, references=[], source_id="doc"))
    ids_no_actor = compute_identities(
        extract_obligations_from_text(
            text, references=[], source_id="doc", enable_actor_binding=False, enable_action_binding=True
        )
    )
    ids_no_action = compute_identities(
        extract_obligations_from_text(
            text, references=[], source_id="doc", enable_actor_binding=True, enable_action_binding=False
        )
    )
    assert ids_with[0].identity_hash != ids_no_actor[0].identity_hash
    assert ids_with[0].identity_hash != ids_no_action[0].identity_hash
