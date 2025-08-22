from src.distinguish.engine import (
    extract_holding_and_facts,
    extract_case_silhouette,
    compare_cases,
)


def test_extract_holding_and_facts():
    paragraphs = [
        "Fact alpha",
        "Fact beta",
        "Fact gamma",
        "Held: something",
        "Other text",
    ]
    holdings, facts = extract_holding_and_facts(paragraphs)
    assert holdings == {"Held: something"}
    assert facts == {"Fact alpha", "Fact beta", "Fact gamma"}


def test_compare_cases_token_sets():
    base_paras = ["Fact A", "Common fact"]
    cand_paras = ["Common fact", "Fact B"]
    base = extract_case_silhouette(base_paras)
    cand = extract_case_silhouette(cand_paras)
    result = compare_cases(base, cand)
    assert result["overlap_tokens"] == ["Common fact"]
    assert result["a_only_tokens"] == ["Fact A"]
    assert result["b_only_tokens"] == ["Fact B"]
