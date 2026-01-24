from src.models.provision import RuleReference
from src.pdf_ingest import _canonicalize_references


def test_anchor_core_merges_ocr_variants():
    refs = [
        RuleReference(
            work="( i ) western sydney parklands act 2006",
            section="section",
            pinpoint="4",
        ),
        RuleReference(
            work="Western Sydney Parklands Act 2006",
            section="section",
            pinpoint="4",
        ),
    ]

    canonical = _canonicalize_references(refs, anchor_core_merge=True)
    assert len(canonical) == 1
    assert canonical[0].work == "western sydney parklands act 2006"


def test_anchor_core_resolves_deictic_and_ocr_to_anchor():
    refs = [
        RuleReference(work="the act", section="section", pinpoint="7"),
        RuleReference(
            work="new south wales ) act",
            section="section",
            pinpoint="7",
        ),
        RuleReference(
            work="Native Title (New South Wales) Act 1994",
            section="section",
            pinpoint="23b",
        ),
    ]

    canonical = _canonicalize_references(refs, anchor_core_merge=True)
    assert {ref.work for ref in canonical} == {
        "native title (new south wales) act 1994"
    }
    assert len(canonical) == 2
    assert {ref.pinpoint for ref in canonical} == {"7", "23b"}


def test_anchor_core_skips_when_no_anchor_exists():
    refs = [RuleReference(work="the act", section="section", pinpoint=None)]
    canonical = _canonicalize_references(refs, anchor_core_merge=True)
    assert canonical == []


def test_anchor_core_does_not_overwrite_links():
    refs = [
        RuleReference(
            work="( i ) western sydney parklands act 2006",
            section="section",
            pinpoint="4",
        ),
        RuleReference(
            work="Western Sydney Parklands Act 2006",
            section="section",
            pinpoint="4",
            source="link",
        ),
    ]

    canonical = _canonicalize_references(
        refs, preferred_sources=("link", None), anchor_core_merge=True
    )

    assert len(canonical) == 1
    ref = canonical[0]
    assert ref.work == "western sydney parklands act 2006"
    assert ref.source == "link"
