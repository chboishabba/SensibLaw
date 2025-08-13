from src.distinguish.engine import compare_cases, extract_case_silhouette


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
