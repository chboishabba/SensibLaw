from src.models.provision import RuleReference
from src.reference_identity import normalize_for_identity


def test_same_act_same_identity():
    r1 = RuleReference(work="Western Sydney Parklands Act 2006", section="4")
    r2 = RuleReference(work="western sydney parklands act 2006", section="4")
    assert normalize_for_identity(r1).identity_hash == normalize_for_identity(r2).identity_hash


def test_ocr_variants_same_identity():
    r1 = RuleReference(work="( i ) western sydney parklands act 2006", section="4")
    r2 = RuleReference(work="western sydney parklands act 2006", section="4")
    assert normalize_for_identity(r1).identity_hash == normalize_for_identity(r2).identity_hash


def test_similar_names_different_identity():
    r1 = RuleReference(work="crimes act 1914")
    r2 = RuleReference(work="crime act 1914")
    assert normalize_for_identity(r1).identity_hash != normalize_for_identity(r2).identity_hash


def test_identity_is_pure():
    ref = RuleReference(work="crimes act 1914", section="s 5B")
    before = ref.to_dict()
    _ = normalize_for_identity(ref)
    after = ref.to_dict()
    assert before == after
