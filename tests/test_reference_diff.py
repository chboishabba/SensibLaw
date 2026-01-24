from src.models.provision import RuleReference
from src.reference_diff import diff_references


def test_ocr_noise_produces_empty_diff():
    clean = [RuleReference(work="Crimes Act 1914", section="s 5B")]
    noisy = [RuleReference(work="crimes  act 1914", section="s 5B")]
    diff = diff_references(clean, noisy)
    assert not diff.added
    assert not diff.removed


def test_single_new_act_added():
    old = [RuleReference(work="Crimes Act 1914")]
    new = old + [RuleReference(work="Evidence Act 1995")]
    diff = diff_references(old, new)
    assert diff.added
    assert not diff.removed


def test_reordering_no_diff():
    refs_a = [
        RuleReference(work="Crimes Act 1914", section="s 5"),
        RuleReference(work="Evidence Act 1995", section="s 10"),
    ]
    refs_b = list(reversed(refs_a))
    diff = diff_references(refs_a, refs_b)
    assert not diff.added
    assert not diff.removed
