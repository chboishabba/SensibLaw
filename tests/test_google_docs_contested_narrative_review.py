from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from scripts.build_google_docs_contested_narrative_review import build_google_docs_contested_narrative_review


def test_google_docs_contested_narrative_review_builds_artifact(monkeypatch, tmp_path: Path) -> None:
    from scripts import build_google_docs_contested_narrative_review as module
    from scripts import build_affidavit_coverage_review as review_module

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
    monkeypatch.setattr(
        review_module,
        "_analyze_structural_sentence",
        lambda text: {
            "subject_texts": ["I"] if text.casefold().startswith("i ") else [],
            "verb_lemmas": (
                ["dispute"] if "i dispute" in text.casefold()
                else ["cut"] if text.casefold().startswith("i cut off")
                else []
            ),
            "has_negation": "i dispute" in text.casefold(),
            "has_first_person_subject": text.casefold().startswith("i "),
            "has_hedge_verb": False,
        },
    )
    payload = build_google_docs_contested_narrative_review(
        affidavit_doc_url="https://docs.google.com/document/d/aff/edit?usp=sharing",
        response_doc_url="https://docs.google.com/document/d/resp/edit?usp=sharing",
        output_dir=tmp_path / "out",
    )
    artifact = json.loads(Path(payload["artifact_path"]).read_text(encoding="utf-8"))
    summary = Path(payload["summary_path"]).read_text(encoding="utf-8")
    assert artifact["summary"]["affidavit_proposition_count"] == 2
    assert artifact["summary"]["semantic_basis_counts"]["structural"] == 2
    assert artifact["source_input"]["path"] == "https://docs.google.com/document/d/resp/edit?usp=sharing"
    first_row = artifact["affidavit_rows"][0]
    second_row = artifact["affidavit_rows"][1]
    assert first_row["coverage_status"] in {"partial", "covered"}
    assert first_row["best_response_role"] in {"admission", "dispute", "other", "procedural_frame", "restatement_only"}
    assert "router outage" in first_row["best_match_excerpt"] or "internet" in first_row["best_match_excerpt"]
    assert first_row["support_status"] in {"responsive_but_non_substantive", "substantively_addressed", "evidentially_grounded_response"}
    assert first_row["semantic_candidate"]["schema_version"] == "contested.semantic_candidate.v1"
    assert first_row["semantic_candidate"]["candidate_kind"] == "contested_claim"
    assert first_row["semantic_candidate"]["basis"] in {"structural", "heuristic", "mixed"}
    assert first_row["semantic_candidate"]["target_component"] in {"predicate_text", "characterization", "time"}
    assert first_row["semantic_basis"] in {"structural", "heuristic", "mixed"}
    assert first_row["promotion_status"] in {"promoted_true", "promoted_false", "candidate_conflict", "abstained"}
    assert first_row["promotion_basis"] == first_row["semantic_basis"]
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
    assert first_row["response"]["speech_act"] in {"deny", "explain", "admit", "other"}
    assert isinstance(first_row["response"]["modifiers"], list)
    assert isinstance(first_row["response"]["component_bindings"], list)
    assert "predicate_text" in first_row["response"]["component_targets"]
    assert any(binding["component"] == "predicate_text" for binding in first_row["response"]["component_bindings"])
    assert isinstance(first_row["justifications"], list)
    assert second_row["best_response_role"] in {"admission", "dispute"}
    assert any(
        act in second_row["response_acts"]
        for act in {"deny_fact", "deny_characterisation", "admit_fact"}
    )
    assert second_row["response"]["speech_act"] in {"admit", "deny"}
    assert second_row["response"]["polarity"] in {"negative", "positive"}
    zelph_fact = artifact["zelph_claim_state_facts"][0]
    assert zelph_fact["fact_kind"] == "contested_claim_state"
    assert zelph_fact["fact_id"].startswith("zelph_claim_state:")
    assert zelph_fact["best_source_row_id"]
    assert zelph_fact["claim_text_span"]["text"] == first_row["text"]
    assert zelph_fact["response_text_span"]["text"] == first_row["best_match_excerpt"]
    assert zelph_fact["target_span"]["text"] == first_row["text"]
    assert zelph_fact["response_speech_act"] in {"deny", "explain", "admit", "other"}
    assert zelph_fact["response_polarity"] in {"negative", "positive", "qualified"}
    assert zelph_fact["semantic_basis"] in {"structural", "heuristic"}
    assert zelph_fact["promotion_status"] in {"promoted_true", "promoted_false", "candidate_conflict", "abstained"}
    assert zelph_fact["promotion_basis"] == zelph_fact["semantic_basis"]
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


def test_google_docs_contested_narrative_review_reports_progress(monkeypatch, tmp_path: Path) -> None:
    from scripts import build_google_docs_contested_narrative_review as module
    from scripts import build_affidavit_coverage_review as review_module

    affidavit_text = "Affidavit Text:\nThe respondent cut off my internet in November 2024."
    response_text = "Summary of Response\n\nI dispute that allegation."
    lookup = {
        "https://docs.google.com/document/d/aff/edit?usp=sharing": affidavit_text,
        "https://docs.google.com/document/d/resp/edit?usp=sharing": response_text,
    }
    seen: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(module, "fetch_google_public_export_text", lambda url: lookup[url])
    monkeypatch.setattr(
        review_module,
        "_analyze_structural_sentence",
        lambda text: {
            "subject_texts": ["I"] if text.casefold().startswith("i ") else [],
            "verb_lemmas": ["dispute"] if "i dispute" in text.casefold() else [],
            "has_negation": "i dispute" in text.casefold(),
            "has_first_person_subject": text.casefold().startswith("i "),
            "has_hedge_verb": False,
        },
    )

    build_google_docs_contested_narrative_review(
        affidavit_doc_url="https://docs.google.com/document/d/aff/edit?usp=sharing",
        response_doc_url="https://docs.google.com/document/d/resp/edit?usp=sharing",
        output_dir=tmp_path / "out",
        progress_callback=lambda stage, details: seen.append((stage, details)),
    )

    stages = [stage for stage, _ in seen]
    assert "google_affidavit_fetch_started" in stages
    assert "google_affidavit_fetch_finished" in stages
    assert "google_response_fetch_started" in stages
    assert "google_response_fetch_finished" in stages
    assert "google_doc_extract_finished" in stages
    assert "google_response_units_grouped" in stages
    assert "google_affidavit_review_started" in stages
    assert "artifact_write_finished" in stages
    assert "google_affidavit_review_finished" in stages


def test_google_docs_contested_narrative_review_reports_trace(monkeypatch, tmp_path: Path) -> None:
    from scripts import build_google_docs_contested_narrative_review as module
    from scripts import build_affidavit_coverage_review as review_module

    affidavit_text = "Affidavit Text:\nThe respondent cut off my internet in November 2024."
    response_text = "Summary of Response\n\nI dispute that allegation."
    lookup = {
        "https://docs.google.com/document/d/aff/edit?usp=sharing": affidavit_text,
        "https://docs.google.com/document/d/resp/edit?usp=sharing": response_text,
    }
    seen: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(module, "fetch_google_public_export_text", lambda url: lookup[url])
    monkeypatch.setattr(
        review_module,
        "_analyze_structural_sentence",
        lambda text: {
            "subject_texts": ["I"] if text.casefold().startswith("i ") else [],
            "verb_lemmas": ["dispute"] if "i dispute" in text.casefold() else [],
            "has_negation": "i dispute" in text.casefold(),
            "has_first_person_subject": text.casefold().startswith("i "),
            "has_hedge_verb": False,
        },
    )

    build_google_docs_contested_narrative_review(
        affidavit_doc_url="https://docs.google.com/document/d/aff/edit?usp=sharing",
        response_doc_url="https://docs.google.com/document/d/resp/edit?usp=sharing",
        output_dir=tmp_path / "out",
        trace_callback=lambda stage, details: seen.append((stage, details)),
        trace_level="verbose",
    )

    stages = [stage for stage, _ in seen]
    assert "google_docs_run_started" in stages
    assert "google_docs_text_extracted" in stages
    assert "google_docs_units_grouped" in stages
    assert "proposition_started" in stages
    assert "proposition_classified" in stages


def test_google_docs_contested_narrative_review_groups_duplicate_heading_blocks(monkeypatch, tmp_path: Path) -> None:
    from scripts import build_google_docs_contested_narrative_review as module
    from scripts import build_affidavit_coverage_review as review_module

    affidavit_text = (
        "Affidavit Text:\n"
        "The respondent cut off my internet in November 2024.\n"
        "The respondent pushed me on the back deck.\n"
    )
    response_text = (
        "Summary of Response\n\n"
        "1. The respondent cut off my internet in November 2024.\n\n"
        "I cut off the internet because the router outage escalated.\n\n"
        "2. The respondent pushed me on the back deck.\n\n"
        "I dispute the characterization of the deck incident.\n"
    )
    lookup = {
        "https://docs.google.com/document/d/aff/edit?usp=sharing": affidavit_text,
        "https://docs.google.com/document/d/resp/edit?usp=sharing": response_text,
    }
    monkeypatch.setattr(module, "fetch_google_public_export_text", lambda url: lookup[url])
    monkeypatch.setattr(
        review_module,
        "_analyze_structural_sentence",
        lambda text: {
            "subject_texts": ["I"] if text.casefold().startswith("i ") else [],
            "verb_lemmas": ["dispute"] if "dispute" in text.casefold() else ["cut"] if "cut off" in text.casefold() else [],
            "has_negation": "dispute" in text.casefold(),
            "has_first_person_subject": text.casefold().startswith("i "),
            "has_hedge_verb": False,
        },
    )

    payload = build_google_docs_contested_narrative_review(
        affidavit_doc_url="https://docs.google.com/document/d/aff/edit?usp=sharing",
        response_doc_url="https://docs.google.com/document/d/resp/edit?usp=sharing",
        output_dir=tmp_path / "out",
    )

    meta = json.loads(Path(payload["meta_path"]).read_text(encoding="utf-8"))
    assert meta["response_unit_count"] == 3


def test_google_docs_contested_narrative_review_persists_sqlite_without_bulky_artifacts(monkeypatch, tmp_path: Path) -> None:
    from scripts import build_google_docs_contested_narrative_review as module

    affidavit_text = "Affidavit Text:\nThe respondent cut off my internet in November 2024."
    response_text = (
        "Summary of Response\n\n"
        "1. The respondent cut off my internet in November 2024.\n\n"
        "I acknowledge this likely occurred on many occasions."
    )
    lookup = {
        "https://docs.google.com/document/d/aff/edit?usp=sharing": affidavit_text,
        "https://docs.google.com/document/d/resp/edit?usp=sharing": response_text,
    }
    monkeypatch.setattr(module, "fetch_google_public_export_text", lambda url: lookup[url])

    db_path = tmp_path / "itir.sqlite"
    output_dir = tmp_path / "out"
    payload = build_google_docs_contested_narrative_review(
        affidavit_doc_url="https://docs.google.com/document/d/aff/edit?usp=sharing",
        response_doc_url="https://docs.google.com/document/d/resp/edit?usp=sharing",
        output_dir=output_dir,
        db_path=db_path,
    )

    assert "artifact_path" not in payload
    assert "summary_path" not in payload
    assert Path(payload["meta_path"]).exists()
    assert payload["persist_summary"]["review_run_id"]

    with sqlite3.connect(str(db_path)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM contested_review_runs").fetchone()[0]
    assert count == 1
