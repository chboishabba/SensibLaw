from src.concepts.matcher import MATCHER


def test_matcher_offsets():
    text = "The court ordered a permanent stay today."
    hits = MATCHER.match(text)
    hit = next(h for h in hits if h.concept_id == "stay_permanent")
    assert text[hit.start:hit.end] == "permanent stay"
