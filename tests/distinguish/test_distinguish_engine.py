from src.distinguish.engine import (
    CaseSilhouette,
    compare_cases,
    compare_story_to_case,
    extract_case_silhouette,
)


def test_extract_case_silhouette():
    paragraphs = [
        "[1] Fact one",
        "¶2 Fact two",
        "3 Fact three",
        "Held: something",
        "Other",
    ]
    sil = extract_case_silhouette(paragraphs)
    assert "[1] Fact one" in sil.fact_tags
    assert sil.fact_tags["[1] Fact one"] == 0
    assert sil.anchors[0] == "[1]"
    assert sil.anchors[1] == "¶2"
    assert sil.anchors[2] == "3"
    assert "Held: something" in sil.holding_hints
    assert sil.holding_hints["Held: something"] == 3


def test_compare_cases_overlap_and_missing():
    base_paras = [
        "[1] Base fact",
        "¶2 Held: yes",
    ]
    cand_paras = [
        "[3] Other fact",
        "¶2 Held: yes",
    ]
    base = extract_case_silhouette(base_paras)
    cand = extract_case_silhouette(cand_paras)
    result = compare_cases(base, cand)
    texts = [o["text"] for o in result["overlaps"]]
    assert "¶2 Held: yes" in texts
    missing_texts = [m["text"] for m in result["missing"]]
    assert "[1] Base fact" in missing_texts
    # token overlaps unaffected by anchors
    assert result["overlap_tokens"] == ["¶2 Held: yes"]
    assert result["a_only_tokens"] == ["[1] Base fact"]
    assert result["b_only_tokens"] == ["[3] Other fact"]
    # anchors propagated in results
    assert result["overlaps"][0]["base"]["anchor"] == "¶2"
    assert result["overlaps"][0]["candidate"]["anchor"] == "¶2"
    assert result["missing"][0]["base"]["anchor"] == "[1]"


def test_compare_story_to_case_overlap_and_missing():
    paragraphs = [
        "[1] There was a significant delay before trial.",
        "¶2 Some evidence was lost causing prejudice to the defence.",
    ]
    case = extract_case_silhouette(paragraphs)
    case.fact_tags = {}
    case.holding_hints = {}
    story_tags = {"delay": True, "abuse_indicators": True, "lost_evidence": True}
    result = compare_story_to_case(story_tags, case)
    overlap_ids = {o["id"] for o in result["overlaps"]}
    missing_ids = {m["id"] for m in result["missing"]}
    assert "delay" in overlap_ids
    assert "lost_evidence" in overlap_ids
    assert "abuse_indicators" in missing_ids
    # anchors included
    assert any(o["candidate"]["anchor"] for o in result["overlaps"])
    assert all("anchor" in o["base"] and "anchor" in o["candidate"] for o in result["overlaps"])
    assert all("anchor" in m["base"] and "anchor" in m["candidate"] for m in result["missing"])
