from __future__ import annotations

from src.reporting.affidavit_plantuml import (
    build_affidavit_mechanical_plantuml,
    build_affidavit_resolution_plantuml,
)


def test_affidavit_resolution_plantuml_renders_claim_root_and_relation() -> None:
    payload = {
        "summary": {
            "affidavit_proposition_count": 1,
            "supported_affidavit_count": 0,
            "disputed_affidavit_count": 1,
        },
        "affidavit_rows": [
            {
                "proposition_id": "aff-prop:p1-s1",
                "text": "The respondent cut off my internet in November 2024.",
                "coverage_status": "covered",
                "best_source_row_id": "fact:f1",
                "best_match_excerpt": "I cut off the internet in November 2024 as a final attempt to prompt a discussion.",
                "duplicate_match_excerpt": "The respondent cut off my internet in November 2024.",
                "claim_root_text": "The respondent cut off my internet in November 2024.",
                "claim_root_basis": "duplicate_excerpt",
                "best_response_role": "dispute",
                "semantic_basis": "structural",
                "support_status": "substantively_addressed",
                "support_direction": "against",
                "conflict_state": "disputed",
                "relation_root": "invalidates",
                "relation_leaf": "explicit_dispute",
                "explanation": {"classification": "disputed"},
                "matched_source_rows": [
                    {
                        "source_row_id": "fact:f1",
                        "match_excerpt": "I cut off the internet in November 2024 as a final attempt to prompt a discussion.",
                        "match_basis": "segment",
                        "score": 0.7,
                    }
                ],
            }
        ],
        "source_review_rows": [
            {
                "source_row_id": "fact:f1",
                "text": "I cut off the internet in November 2024 as a final attempt to prompt a discussion.",
            }
        ],
        "zelph_claim_state_facts": [
            {
                "fact_id": "zelph_claim_state:demo",
                "best_source_row_id": "fact:f1",
                "claim_text_span": {"text": "The respondent cut off my internet in November 2024."},
                "promotion_status": "candidate_conflict",
                "semantic_basis": "structural",
            }
        ],
    }

    puml = build_affidavit_resolution_plantuml(payload, title="Demo Resolution")
    assert "Demo Resolution" in puml
    assert "p1-s1" in puml
    assert "claim_root" in puml
    assert "invalidates / explicit_dispute" in puml
    assert "zelph_claim_state" in puml


def test_affidavit_mechanical_plantuml_renders_tokens_and_duplicate_root() -> None:
    payload = {
        "affidavit_rows": [
            {
                "proposition_id": "aff-prop:p1-s1",
                "text": "The respondent cut off my internet in November 2024.",
                "tokens": ["respondent", "cut", "internet", "november", "2024"],
                "best_source_row_id": "fact:f1",
                "best_match_excerpt": "I cut off the internet in November 2024 as a final attempt to prompt a discussion.",
                "best_match_basis": "segment",
                "best_adjusted_match_score": 0.7,
                "duplicate_match_excerpt": "The respondent cut off my internet in November 2024.",
                "claim_root_text": "The respondent cut off my internet in November 2024.",
                "claim_root_basis": "duplicate_excerpt",
                "best_response_role": "dispute",
                "semantic_basis": "structural",
                "relation_root": "invalidates",
                "relation_leaf": "explicit_dispute",
                "matched_source_rows": [
                    {
                        "source_row_id": "fact:f1",
                        "match_excerpt": "I cut off the internet in November 2024 as a final attempt to prompt a discussion.",
                        "match_basis": "segment",
                        "score": 0.7,
                    }
                ],
            }
            ,
            {
                "proposition_id": "aff-prop:p1-s2",
                "text": "The respondent pushed me on the back deck.",
                "tokens": ["respondent", "pushed", "back", "deck"],
                "best_source_row_id": "fact:f2",
                "best_match_excerpt": "I dispute the characterization of the deck incident.",
                "best_match_basis": "segment",
                "best_adjusted_match_score": 0.4,
                "claim_root_text": "The respondent pushed me on the back deck.",
                "claim_root_basis": "proposition_text",
                "best_response_role": "dispute",
                "semantic_basis": "structural",
                "relation_root": "invalidates",
                "relation_leaf": "explicit_dispute",
                "matched_source_rows": [
                    {
                        "source_row_id": "fact:f2",
                        "match_excerpt": "I dispute the characterization of the deck incident.",
                        "match_basis": "segment",
                        "score": 0.4,
                    }
                ],
            },
        ],
        "source_review_rows": [
            {
                "source_row_id": "fact:f1",
                "text": "I cut off the internet in November 2024 as a final attempt to prompt a discussion.",
            },
            {
                "source_row_id": "fact:f2",
                "text": "I dispute the characterization of the deck incident.",
            },
        ],
    }

    puml = build_affidavit_mechanical_plantuml(payload, title="Demo Mechanical")
    assert "Demo Mechanical" in puml
    assert "p1-s1 tokens\\\\nrespondent\\\\ncut\\\\ninternet" in puml
    assert "duplicate_root" in puml
    assert "root_selection" in puml
    assert "invalidates / explicit_dispute" in puml
    assert "next_sentence" in puml
    assert "next_source" in puml
    assert "extracted p1-s1" in puml
    assert "from_response_sentence" in puml
