"""Source-exact Mabo specimen for the Lee/SensibLaw proof-graph lane.

This is deliberately a *reviewed correspondence fixture*, not a claim that the
parser itself understands Mabo and not a substitute for authoritative judgment
text.  It consumes the non-semantic numeric-PNF bridge receipt introduced by
``evidential_pnf_receipt`` and adds an explicit human-reviewed mapping from the
small repository fixture sentence to proposition nodes.

The fixture closes only:

    exact source text -> reviewed proposition nodes -> source-linked graph

It does not invent a respondent/opposing account, a controversy residual, an
evidence discriminator, or a judicial finding.  Those require additional
source material and a declared procedural consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from src.pnf.evidential_pnf_receipt import EvidentialPNFBridgeReceipt


MABO_FIXTURE_TEXT = (
    "The High Court recognised native title in Australia and rejected the doctrine "
    "of terra nullius."
)
MABO_FIXTURE_SHA256 = sha256(MABO_FIXTURE_TEXT.encode("utf-8")).hexdigest()
MABO_FIXTURE_SOURCE_PATH = "data/corpus/mabo_v_queensland_no2.json"


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start: int
    end: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "text": self.text}


@dataclass(frozen=True, slots=True)
class ReviewedPredicateNode:
    node_ref: str
    predicate: str
    agent: str
    theme: str
    qualifier: str
    source_span: SourceSpan
    correspondence_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_ref": self.node_ref,
            "predicate": self.predicate,
            "agent": self.agent,
            "theme": self.theme,
            "qualifier": self.qualifier,
            "source_span": self.source_span.to_dict(),
            "correspondence_status": self.correspondence_status,
        }


@dataclass(frozen=True, slots=True)
class ProofGraphEdge:
    source: str
    target: str
    relation: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target, "relation": self.relation}


@dataclass(frozen=True, slots=True)
class MaboLegalProofGraphSpecimen:
    schema_version: str
    run_ref: str
    document_ref: str
    canonical_text_sha256: str
    source_path: str
    nodes: tuple[ReviewedPredicateNode, ...]
    edges: tuple[ProofGraphEdge, ...]
    source_is_repository_fixture_summary: bool
    source_is_authoritative_judgment_text: bool
    parser_observation_is_semantic_authority: bool
    reviewed_correspondence_required: bool
    world_truth_claimed: bool
    party_alignment_complete: bool
    controversy_residual_compiled: bool
    next_evidence_probe_authorised: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_ref": self.run_ref,
            "document_ref": self.document_ref,
            "canonical_text_sha256": self.canonical_text_sha256,
            "source_path": self.source_path,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "source_is_repository_fixture_summary": self.source_is_repository_fixture_summary,
            "source_is_authoritative_judgment_text": self.source_is_authoritative_judgment_text,
            "parser_observation_is_semantic_authority": self.parser_observation_is_semantic_authority,
            "reviewed_correspondence_required": self.reviewed_correspondence_required,
            "world_truth_claimed": self.world_truth_claimed,
            "party_alignment_complete": self.party_alignment_complete,
            "controversy_residual_compiled": self.controversy_residual_compiled,
            "next_evidence_probe_authorised": self.next_evidence_probe_authorised,
        }


def _exact_span(source_text: str, expected: str) -> SourceSpan:
    start = source_text.find(expected)
    if start < 0:
        raise ValueError(f"reviewed clause is absent from exact source text: {expected!r}")
    second = source_text.find(expected, start + 1)
    if second >= 0:
        raise ValueError(f"reviewed clause is not unique in exact source text: {expected!r}")
    end = start + len(expected)
    return SourceSpan(start=start, end=end, text=source_text[start:end])


def build_mabo_legal_proof_graph_specimen(
    *,
    bridge_receipt: EvidentialPNFBridgeReceipt,
    source_text: str,
) -> MaboLegalProofGraphSpecimen:
    """Build the first source-linked legal proposition graph specimen.

    The source must be byte-for-byte the repository fixture body.  This makes
    accidental concatenation with later cases/citations fail closed rather than
    allowing a convenient semantic-looking graph to outrun its source span.
    """

    source_hash = sha256(source_text.encode("utf-8")).hexdigest()
    if source_hash != MABO_FIXTURE_SHA256:
        raise ValueError("Mabo specimen requires the exact bounded repository fixture text")
    if bridge_receipt.canonical_text_sha256 != source_hash:
        raise ValueError("bridge receipt canonical-text hash does not match Mabo source text")
    if bridge_receipt.parser_observation_is_semantic_authority:
        raise ValueError("parser observation may not become semantic authority")
    if not bridge_receipt.semantic_correspondence_required:
        raise ValueError("Mabo specimen requires an explicit reviewed correspondence layer")
    if not bridge_receipt.world_resolution_deferred:
        raise ValueError("Mabo document-level specimen may not claim world resolution closure")
    if bridge_receipt.cross_document_identity_closed:
        raise ValueError("Mabo document-level specimen may not claim cross-document identity closure")

    recognition = ReviewedPredicateNode(
        node_ref="mabo-fixture:recognise-native-title",
        predicate="recognise_native_title",
        agent="High Court",
        theme="native title in Australia",
        qualifier="asserted_by_fixture_summary",
        source_span=_exact_span(
            source_text,
            "The High Court recognised native title in Australia",
        ),
        correspondence_status="human_reviewed_fixture_correspondence",
    )
    rejection = ReviewedPredicateNode(
        node_ref="mabo-fixture:reject-terra-nullius",
        predicate="reject_doctrine",
        agent="High Court",
        theme="doctrine of terra nullius",
        qualifier="asserted_by_fixture_summary",
        source_span=_exact_span(
            source_text,
            "rejected the doctrine of terra nullius",
        ),
        correspondence_status="human_reviewed_fixture_correspondence",
    )

    return MaboLegalProofGraphSpecimen(
        schema_version="sl.mabo_legal_proof_graph_specimen.v0_1",
        run_ref=bridge_receipt.run_ref,
        document_ref=bridge_receipt.document_ref,
        canonical_text_sha256=source_hash,
        source_path=MABO_FIXTURE_SOURCE_PATH,
        nodes=(recognition, rejection),
        edges=(
            ProofGraphEdge(
                source=recognition.node_ref,
                target=rejection.node_ref,
                relation="coordinated_in_same_fixture_sentence",
            ),
        ),
        source_is_repository_fixture_summary=True,
        source_is_authoritative_judgment_text=False,
        parser_observation_is_semantic_authority=False,
        reviewed_correspondence_required=True,
        world_truth_claimed=False,
        party_alignment_complete=False,
        controversy_residual_compiled=False,
        next_evidence_probe_authorised=False,
    )


__all__ = [
    "MABO_FIXTURE_SHA256",
    "MABO_FIXTURE_SOURCE_PATH",
    "MABO_FIXTURE_TEXT",
    "MaboLegalProofGraphSpecimen",
    "ProofGraphEdge",
    "ReviewedPredicateNode",
    "SourceSpan",
    "build_mabo_legal_proof_graph_specimen",
]
