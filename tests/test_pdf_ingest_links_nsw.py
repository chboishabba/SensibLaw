from tests.conftest import iter_refs


def test_no_spurious_link_sources(native_title_nsw_doc):
    # This PDF lacks embedded hyperlinks; ensure we do not invent link-sourced refs.
    assert all(getattr(ref, "source", None) is None for ref in iter_refs(native_title_nsw_doc))
