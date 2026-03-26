from __future__ import annotations

import json
from pathlib import Path

from scripts.build_google_docs_contested_narrative_review import build_google_docs_contested_narrative_review


def test_google_docs_contested_narrative_review_builds_artifact(monkeypatch, tmp_path: Path) -> None:
    from scripts import build_google_docs_contested_narrative_review as module

    affidavit_text = (
        "Intro line\n\n"
        "Affidavit Text:\n"
        "The respondent cut off my internet in November 2024.\n"
        "The respondent pushed me on the back deck.\n\n"
        "Which Allegations Can You Plausibly Deny or Explain?\n"
        "Analysis starts here.\n"
    )
    response_text = (
        "Response to Affidavit\n\n"
        "Table of Contents 1\n\n"
        "Summary of Response 6\n\n"
        "1. The respondent cut off my internet in November 2024. 10\n\n"
        "2. The respondent pushed me on the back deck. 11\n\n"
        "Summary of Response\n\n"
        "I dispute the characterization of the deck incident.\n\n"
        "I cut off the internet because the router outage escalated after he would not come to the door.\n"
    )
    lookup = {
        "https://docs.google.com/document/d/aff/edit?usp=sharing": affidavit_text,
        "https://docs.google.com/document/d/resp/edit?usp=sharing": response_text,
    }
    monkeypatch.setattr(module, "fetch_google_public_export_text", lambda url: lookup[url])
    payload = build_google_docs_contested_narrative_review(
        affidavit_doc_url="https://docs.google.com/document/d/aff/edit?usp=sharing",
        response_doc_url="https://docs.google.com/document/d/resp/edit?usp=sharing",
        output_dir=tmp_path / "out",
    )
    artifact = json.loads(Path(payload["artifact_path"]).read_text(encoding="utf-8"))
    summary = Path(payload["summary_path"]).read_text(encoding="utf-8")
    assert artifact["summary"]["affidavit_proposition_count"] == 2
    assert artifact["source_input"]["path"] == "https://docs.google.com/document/d/resp/edit?usp=sharing"
    first_row = artifact["affidavit_rows"][0]
    second_row = artifact["affidavit_rows"][1]
    assert first_row["coverage_status"] in {"partial", "covered"}
    assert first_row["best_response_role"] in {"explanation", "admission"}
    assert "router outage" in first_row["best_match_excerpt"] or "internet" in first_row["best_match_excerpt"]
    assert first_row["support_status"] in {"responsive_but_non_substantive", "substantively_addressed", "evidentially_grounded_response"}
    assert isinstance(first_row["response_acts"], list)
    assert isinstance(first_row["legal_significance_signals"], list)
    assert first_row["support_direction"] in {"for", "mixed", "against", "none"}
    assert first_row["conflict_state"] in {"unanswered", "undisputed", "disputed", "partially_reconciled", "unresolved"}
    assert first_row["evidentiary_state"] in {"unassessed", "unproven", "weakly_supported", "supported"}
    assert first_row["operational_status"] in {
        "claim_only",
        "claim_with_support",
        "claim_with_opposition",
        "disputed_claim",
        "partially_reconciled_claim",
        "resolved_but_unproven",
    }
    assert first_row["claim"]["text_span"]["text"] == first_row["text"]
    assert first_row["claim"]["components"]["predicate_text"]["text"] == first_row["text"]
    assert first_row["claim"]["components"]["time"][0]["text"] == "November 2024"
    assert first_row["response"]["target_span"]["text"] == first_row["text"]
    assert first_row["response"]["speech_act"] in {"explain", "admit", "other"}
    assert isinstance(first_row["response"]["modifiers"], list)
    assert isinstance(first_row["response"]["component_bindings"], list)
    assert "predicate_text" in first_row["response"]["component_targets"]
    assert any(binding["component"] == "predicate_text" for binding in first_row["response"]["component_bindings"])
    assert isinstance(first_row["justifications"], list)
    assert second_row["best_response_role"] == "dispute"
    assert "deny_fact" in second_row["response_acts"] or "deny_characterisation" in second_row["response_acts"]
    assert second_row["response"]["speech_act"] == "deny"
    assert second_row["response"]["polarity"] == "negative"
    zelph_fact = artifact["zelph_claim_state_facts"][0]
    assert zelph_fact["fact_kind"] == "contested_claim_state"
    assert zelph_fact["fact_id"].startswith("zelph_claim_state:")
    assert zelph_fact["best_source_row_id"]
    assert zelph_fact["claim_text_span"]["text"] == first_row["text"]
    assert zelph_fact["response_text_span"]["text"] == first_row["best_match_excerpt"]
    assert zelph_fact["target_span"]["text"] == first_row["text"]
    assert zelph_fact["response_speech_act"] in {"explain", "admit", "other"}
    assert zelph_fact["response_polarity"] in {"positive", "qualified"}
    assert isinstance(zelph_fact["response_modifiers"], list)
    assert isinstance(zelph_fact["claim_time_spans"], list)
    assert zelph_fact["claim_time_spans"][0]["text"] == "November 2024"
    assert "predicate_text" in zelph_fact["response_component_targets"]
    assert isinstance(zelph_fact["justification_types"], list)
    assert isinstance(zelph_fact["justification_bindings"], list)
    assert isinstance(zelph_fact["response_acts"], list)
    assert isinstance(zelph_fact["legal_significance_signals"], list)
    assert zelph_fact["support_status"] == first_row["support_status"]
    assert zelph_fact["coverage_status"] == first_row["coverage_status"]
    assert "Table of Contents" not in first_row["best_match_excerpt"]
    assert "Support Status" in summary
    assert "Support Direction" in summary
    assert "Conflict State" in summary
    assert "Evidentiary State" in summary
    assert "Unsupported affidavit propositions" in summary
