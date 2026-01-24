import copy

from src.models.provision import RuleReference
from src.reference_identity import ReferenceDiff, ReferenceIdentity, diff_references


def test_identity_stable_and_collapses_variants():
    base = RuleReference(work="Western Sydney Parklands Act 2006", section="section", pinpoint="4")
    variant = RuleReference(work="western sydney parklands act 2006", section="section", pinpoint="4")

    ident_base = ReferenceIdentity.compute(base)
    ident_variant = ReferenceIdentity.compute(variant)

    assert ident_base.identity_hash == ident_variant.identity_hash
    assert ident_base.family_key == ident_variant.family_key
    assert ident_base.year == 2006


def test_identity_distinct_for_different_acts():
    a = ReferenceIdentity.compute(RuleReference(work="Crimes Act 1914", section="section", pinpoint="7"))
    b = ReferenceIdentity.compute(RuleReference(work="Crimes (Sentencing Procedure) Act 1999", section="section", pinpoint="7"))

    assert a.identity_hash != b.identity_hash
    assert a.family_key != b.family_key


def test_diff_reports_only_real_changes():
    old = [
        RuleReference(work="Crimes Act 1914", section="section", pinpoint="7"),
        RuleReference(work="Western Sydney Parklands Act 2006", section="section", pinpoint="4"),
    ]
    new = copy.deepcopy(old)
    new.append(RuleReference(work="Native Title Act 1993", section="section", pinpoint="217"))
    new = new[1:]  # drop Crimes Act, keep WSPA, add Native Title

    diff = diff_references(old, new)
    assert isinstance(diff, ReferenceDiff)
    assert len(diff.added) == 1
    assert len(diff.removed) == 1
    assert len(diff.unchanged) == 1


def test_provenance_is_metadata_only():
    ref = RuleReference(work="Western Sydney Parklands Act 2006", section="section", pinpoint="4", provenance={"clause_id": "c-1"})
    ident = ReferenceIdentity.compute(ref)
    assert ident.identity_hash
    # provenance does not affect identity
    ref_no_prov = RuleReference(work="Western Sydney Parklands Act 2006", section="section", pinpoint="4")
    ident2 = ReferenceIdentity.compute(ref_no_prov)
    assert ident.identity_hash == ident2.identity_hash
