from __future__ import annotations

from src.policy.affidavit_candidate_arbitration import arbitrate_candidate_selection


def test_arbitration_promotes_duplicate_root_alternate() -> None:
    result = arbitrate_candidate_selection(
        comparison_mode="contested_narrative",
        candidates=[
            {
                "score": 0.52,
                "adjusted_score": 0.52,
                "match_basis": "segment",
                "match_excerpt": "The respondent cut off my internet in November 2024.",
                "response_role": "restatement_only",
                "response_cues": [],
                "predicate_alignment_score": 1.0,
                "is_duplicate_excerpt": True,
                "is_proposition_echo": True,
            },
            {
                "score": 0.55,
                "adjusted_score": 0.60,
                "match_basis": "segment",
                "match_excerpt": "I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation.",
                "response_role": "dispute",
                "response_cues": [],
                "predicate_alignment_score": 0.6,
                "is_duplicate_excerpt": False,
                "is_proposition_echo": False,
            },
        ],
    )

    assert result["match_excerpt"] == "I cut off the internet in November 2024 as a final attempt to prompt a discussion to resolve the situation."
    assert result["duplicate_match_excerpt"] == "The respondent cut off my internet in November 2024."


def test_arbitration_promotes_clause_alternate_when_duplicate_root_exists() -> None:
    result = arbitrate_candidate_selection(
        comparison_mode="contested_narrative",
        candidates=[
            {
                "score": 0.65,
                "adjusted_score": 0.70,
                "match_basis": "segment",
                "match_excerpt": "Johl came into my room and would turn off or stop what I was listening to on my computer. I acknowledge this likely occurred on many occasions.",
                "response_role": "support_or_corroboration",
                "response_cues": [],
                "predicate_alignment_score": 0.7,
                "is_duplicate_excerpt": False,
                "is_proposition_echo": False,
            },
            {
                "score": 0.64,
                "adjusted_score": 0.68,
                "match_basis": "clause",
                "match_excerpt": "I acknowledge this likely occurred on many occasions",
                "response_role": "support_or_corroboration",
                "response_cues": [],
                "predicate_alignment_score": 0.65,
                "is_duplicate_excerpt": False,
                "is_proposition_echo": False,
            },
            {
                "score": 0.52,
                "adjusted_score": 0.52,
                "match_basis": "segment",
                "match_excerpt": "Johl came into my room and would turn off or stop what I was listening to on my computer.",
                "response_role": "restatement_only",
                "response_cues": [],
                "predicate_alignment_score": 1.0,
                "is_duplicate_excerpt": True,
                "is_proposition_echo": True,
            },
        ],
    )

    assert result["match_basis"] == "clause"
    assert result["match_excerpt"] == "I acknowledge this likely occurred on many occasions"
    assert result["duplicate_match_excerpt"] == "Johl came into my room and would turn off or stop what I was listening to on my computer."


def test_arbitration_prefers_higher_predicate_on_adjusted_tie() -> None:
    result = arbitrate_candidate_selection(
        comparison_mode="contested_narrative",
        candidates=[
            {
                "score": 0.6,
                "adjusted_score": 0.7,
                "match_basis": "segment",
                "match_excerpt": "Candidate one",
                "response_role": "dispute",
                "response_cues": [],
                "predicate_alignment_score": 0.4,
                "is_duplicate_excerpt": False,
                "is_proposition_echo": False,
            },
            {
                "score": 0.59,
                "adjusted_score": 0.7,
                "match_basis": "segment",
                "match_excerpt": "Candidate two",
                "response_role": "dispute",
                "response_cues": [],
                "predicate_alignment_score": 0.6,
                "is_duplicate_excerpt": False,
                "is_proposition_echo": False,
            },
        ],
    )

    assert result["match_excerpt"] == "Candidate two"
