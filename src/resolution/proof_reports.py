"""Shared proof reports for corpus fixtures.

GWB, AU, and later corpora provide fixture data only. They do not select a
semantic pipeline or media adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_json, canonical_refs, canonical_sha256, require_text


@dataclass(frozen=True)
class ProofFixture:
    fixture_ref: str
    corpus_ref: str
    document_ref: str
    media_type: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_ref": require_text(self.fixture_ref, "fixture_ref"),
            "corpus_ref": require_text(self.corpus_ref, "corpus_ref"),
            "document_ref": require_text(self.document_ref, "document_ref"),
            "media_type": require_text(self.media_type, "media_type"),
            "metadata": canonical_json(dict(self.metadata)),
        }


def build_proof_report(
    *,
    fixture: ProofFixture,
    mentions: Sequence[Mapping[str, Any]] = (),
    form_alternatives: Sequence[Mapping[str, Any]] = (),
    local_types: Sequence[Mapping[str, Any]] = (),
    demands: Sequence[Mapping[str, Any]] = (),
    evidence: Sequence[Mapping[str, Any]] = (),
    typed_meets: Sequence[Mapping[str, Any]] = (),
    refinements: Sequence[Mapping[str, Any]] = (),
    readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    sections = {
        "mentions": canonical_json(list(mentions)),
        "form_alternatives": canonical_json(list(form_alternatives)),
        "local_types": canonical_json(list(local_types)),
        "demands": canonical_json(list(demands)),
        "evidence": canonical_json(list(evidence)),
        "typed_meets": canonical_json(list(typed_meets)),
        "pnf_refinements": canonical_json(list(refinements)),
        "readiness": canonical_json(dict(readiness or {})),
    }
    row = {
        "schema_version": "sl.resolution_proof_report.v0_1",
        "fixture": fixture.to_dict(),
        "sections": sections,
        "authority_boundary": {
            "editing_authority": False,
            "identity_resolution_establishes_claim_truth": False,
        },
        "provenance_refs": list(canonical_refs((fixture.fixture_ref, fixture.document_ref))),
    }
    row["report_sha256"] = canonical_sha256(row)
    return row
