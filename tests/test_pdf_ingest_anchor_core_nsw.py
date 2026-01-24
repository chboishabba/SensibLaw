from collections import Counter

from tests.conftest import iter_refs


def test_wspa_present_and_not_collapsed(native_title_nsw_doc):
    works = Counter(ref.work for ref in iter_refs(native_title_nsw_doc) if ref.work)
    assert "western sydney parklands act 2006" in works
    # Ensure extraction did not collapse everything to a single anchor.
    assert len(works) > 1


def test_non_invention_no_local_government_act(native_title_nsw_doc):
    works = {ref.work for ref in iter_refs(native_title_nsw_doc) if ref.work}
    assert not any("local government act 1993" in work for work in works)


def test_multiple_act_families_exist(native_title_nsw_doc):
    works = {ref.work for ref in iter_refs(native_title_nsw_doc) if ref.work}
    # Require at least two different act families to survive canonicalisation.
    native_title_family = {w for w in works if "native title" in w}
    parklands_family = {w for w in works if "parklands" in w}
    assert native_title_family, "Expected native title references to remain"
    assert parklands_family, "Expected parklands references to remain"
