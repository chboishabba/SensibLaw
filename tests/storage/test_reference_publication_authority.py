from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.storage.postgres import reference_publication_authority as authority


@dataclass
class RecordingStore:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def persist_fixed_point_receipt(self, cursor: Any, **kwargs: Any) -> None:
        self.calls.append(("fixed_point", dict(kwargs)))

    def persist_execution_receipt(self, cursor: Any, **kwargs: Any) -> None:
        self.calls.append(("execution_receipt", dict(kwargs)))

    def stage_publication(self, cursor: Any, **kwargs: Any) -> None:
        self.calls.append(("stage", dict(kwargs)))

    def commit_publication(self, cursor: Any, **kwargs: Any) -> None:
        self.calls.append(("commit", dict(kwargs)))


def test_publication_authority_commits_compact_manifest_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = RecordingStore()
    monkeypatch.setattr(
        authority,
        "DistributedSemanticExecutionStore",
        lambda: store,
    )
    build = {
        "reference_finalization_contract": "reference-backed-finalization:v1",
        "owner_fingerprint": {"coverage_manifest_ref": "coverage:1"},
        "fixed_point_certificate": {
            "certificate_ref": "certificate:1",
            "revision": 9,
            "local_fixed_point": "reached",
        },
        "family_manifests": {
            "solver_jobs": {
                "record_count": 12,
                "byte_count": 1200,
                "ordered_digest": "11" * 32,
                "path": "/tmp/jobs.jsonl",
            },
            "residuals": {
                "record_count": 0,
                "byte_count": 0,
                "ordered_digest": "22" * 32,
                "path": "/tmp/residuals.jsonl",
            },
            "factors": {
                "record_count": 4,
                "byte_count": 400,
                "ordered_digest": "33" * 32,
                "path": "/tmp/factors.jsonl",
            },
        },
    }

    result = authority.commit_reference_publication_authority(
        object(),
        document_ref="document:1",
        streaming_build=build,
        persistence_counts={
            "graph_manifest_ref": "manifest:graph",
            "factors": 4,
            "residuals": 0,
        },
    )

    assert [name for name, _kwargs in store.calls] == [
        "fixed_point",
        "execution_receipt",
        "stage",
        "commit",
    ]
    fixed = store.calls[0][1]
    assert fixed["accepted_job_set_digest"] == "11" * 32
    assert fixed["unresolved_demand_digest"] == "22" * 32
    assert fixed["local_fixed_point"] is True

    execution = store.calls[1][1]
    payload = execution["payload"]
    assert payload["full_document_payload_embedded"] is False
    assert payload["family_manifests"]["factors"] == {
        "record_count": 4,
        "byte_count": 400,
        "ordered_digest": "33" * 32,
    }
    assert "path" not in payload["family_manifests"]["factors"]

    staged = store.calls[2][1]
    committed = store.calls[3][1]
    assert staged["publication_ref"] == committed["publication_ref"]
    assert staged["publication_digest"] == committed["expected_digest"]
    assert result["publication_state"] == "committed"
