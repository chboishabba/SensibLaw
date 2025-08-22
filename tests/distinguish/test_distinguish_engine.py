from src.distinguish.engine import (
    CaseSilhouette,
    compare_cases,
    compare_story_to_case,
    extract_case_silhouette,
)


def test_extract_case_silhouette():
    paragraphs = [
        "Fact one",
        "Fact two",
        "Fact three",
        "Held: something",
        "Other",
    ]
    sil = extract_case_silhouette(paragraphs)
    assert "Fact one" in sil.fact_tags
    assert sil.fact_tags["Fact one"] == 0
    assert "Held: something" in sil.holding_hints
    assert sil.holding_hints["Held: something"] == 3


def test_compare_cases_overlap_and_missing():
    base_paras = [
        "Base fact",
        "Held: yes",
    ]
    cand_paras = [
        "Other fact",
        "Held: yes",
    ]
    base = extract_case_silhouette(base_paras)
    cand = extract_case_silhouette(cand_paras)
    result = compare_cases(base, cand)
    texts = [o["text"] for o in result["overlaps"]]
    assert "Held: yes" in texts
    missing_texts = [m["text"] for m in result["missing"]]
    assert "Base fact" in missing_texts


def test_compare_story_to_case_overlap_and_missing():
    case = CaseSilhouette(
        fact_tags={},
        holding_hints={},
        paragraphs=[
            "There was a significant delay before trial.",
            "Some evidence was lost causing prejudice to the defence.",
        ],
    )
    story_tags = {"delay": True, "abuse_indicators": True, "lost_evidence": True}
    result = compare_story_to_case(story_tags, case)
    overlap_ids = {o["id"] for o in result["overlaps"]}
    missing_ids = {m["id"] for m in result["missing"]}
    assert "delay" in overlap_ids
    assert "lost_evidence" in overlap_ids
    assert "abuse_indicators" in missing_ids
