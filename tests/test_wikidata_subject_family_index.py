from __future__ import annotations

import hashlib

from src.ontology.wikidata_subject_family_index import (
    SUBJECT_FAMILY_INDEX_SCHEMA_VERSION,
    build_subject_family_index,
    resolve_subject_family,
)


def test_resolve_subject_family_prefers_company_when_company_seed_present() -> None:
    assert resolve_subject_family(["Q5", "Q4830453"]) == "company"


def test_resolve_subject_family_returns_non_company_for_nonempty_non_company_closure() -> None:
    assert resolve_subject_family(["Q5", "Q215627"]) == "non_company"


def test_resolve_subject_family_returns_unknown_for_empty_closure() -> None:
    assert resolve_subject_family([]) == "unknown"


def test_build_subject_family_index_is_deterministic_and_cache_friendly() -> None:
    payload = {
        "Q1": {"type_closure": ["Q5", "Q4830453"], "source_revision_ids": ["rev-2", "rev-1"]},
        "Q2": {"closure_qids": ["Q5"], "revision_ids": ["rev-3"]},
        "Q3": {},
    }
    cache = {
        "Q1:" + "sha256:" + hashlib.sha256("\n".join(["Q4830453", "Q5"]).encode("utf-8")).hexdigest(): {
            "subject_qid": "Q1",
            "family": "company",
            "closure_qids": ["Q4830453", "Q5"],
            "closure_signature": "sha256:"
            + hashlib.sha256("\n".join(["Q4830453", "Q5"]).encode("utf-8")).hexdigest(),
            "source_revision_ids": ["rev-1", "rev-2"],
        }
    }

    report = build_subject_family_index(payload, cache=cache)

    assert report["schema_version"] == SUBJECT_FAMILY_INDEX_SCHEMA_VERSION
    assert report["summary"] == {
        "subject_count": 3,
        "family_counts": {"company": 1, "non_company": 1, "unknown": 1},
        "cache_hit_count": 1,
        "cache_miss_count": 2,
        "cache_ready": True,
    }
    assert [row["subject_qid"] for row in report["subject_families"]] == ["Q1", "Q2", "Q3"]

    first = report["subject_families"][0]
    assert first["family"] == "company"
    assert first["cache_hit"] is True
    assert first["closure_qids"] == ["Q4830453", "Q5"]
    assert first["source_revision_ids"] == ["rev-1", "rev-2"]
    assert first["cache_key"].startswith("Q1:sha256:")

    second = report["subject_families"][1]
    assert second["family"] == "non_company"
    assert second["cache_hit"] is False
    assert second["closure_qids"] == ["Q5"]

    third = report["subject_families"][2]
    assert third["family"] == "unknown"
    assert third["closure_qids"] == []
    assert report["cache_index"][first["cache_key"]]["family"] == "company"
