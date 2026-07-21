"""Content-addressed transport contract for Legal IR federation artifacts.

SensibLaw owns semantics, authority, review, and promotion.  ZOS/eRDFa/Kant may
publish, replicate, recover, and verify immutable bytes.  Successful transport or
digest verification never promotes PNF, Legal IR, identity, or legal truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping

LEGAL_ARTIFACT_TRANSPORT_CONTRACT = "sensiblaw-legal-artifact/v0_1"
ZOS_SYNC_IDENTITY_CONTRACT = "canonical-sync-identity/v1"

_ALLOWED_KINDS = frozenset({"artifact", "receipt"})


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_ref(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class LegalArtifactMember:
    member_ref: str
    member_kind: str
    content_digest: str
    producer_contract: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LegalArtifactEnvelope:
    kind: str
    object_id: str
    content_digest: str
    producer_contract: str
    producer_locator_set: tuple[str, ...]
    semantic_build_ref: str | None
    source_revision_refs: tuple[str, ...]
    member_artifacts: tuple[LegalArtifactMember, ...]
    payload_media_type: str
    payload_size: int

    def __post_init__(self) -> None:
        if self.kind not in _ALLOWED_KINDS:
            raise ValueError(f"unsupported transport kind: {self.kind}")
        if not self.content_digest.startswith("sha256:"):
            raise ValueError("content_digest must be a sha256 reference")
        if self.payload_size < 0:
            raise ValueError("payload_size must be non-negative")

    @property
    def sync_identity(self) -> tuple[str, str, str, str, tuple[str, ...]]:
        return (
            self.kind,
            self.object_id,
            self.content_digest,
            self.producer_contract,
            self.producer_locator_set,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": LEGAL_ARTIFACT_TRANSPORT_CONTRACT,
            "syncIdentityContract": ZOS_SYNC_IDENTITY_CONTRACT,
            "kind": self.kind,
            "objectId": self.object_id,
            "contentDigest": self.content_digest,
            "producerContract": self.producer_contract,
            "producerLocatorSet": list(self.producer_locator_set),
            "semanticBuildRef": self.semantic_build_ref,
            "sourceRevisionRefs": list(self.source_revision_refs),
            "memberArtifacts": [row.to_dict() for row in self.member_artifacts],
            "payloadMediaType": self.payload_media_type,
            "payloadSize": self.payload_size,
            "authority": "transport_and_availability_only",
            "semanticPromotionPerformed": False,
            "trustImported": False,
            "truthClosed": False,
        }


@dataclass(frozen=True)
class LegalArtifactVerificationReceipt:
    receipt_ref: str
    object_id: str
    expected_digest: str
    observed_digest: str
    locator_ref: str
    verification_state: str
    member_states: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "member_states": dict(self.member_states),
            "contract_ref": LEGAL_ARTIFACT_TRANSPORT_CONTRACT,
            "authority": "transport_verification_only",
            "semantic_promotion_performed": False,
            "review_state_imported": False,
            "truth_closed": False,
        }


def export_legal_artifact(
    *,
    object_id: str,
    payload: Mapping[str, Any],
    producer_contract: str,
    locators: Iterable[str] = (),
    semantic_build_ref: str | None = None,
    source_revision_refs: Iterable[str] = (),
    members: Iterable[LegalArtifactMember] = (),
    kind: str = "artifact",
    payload_media_type: str = "application/json",
) -> tuple[LegalArtifactEnvelope, bytes]:
    payload_bytes = canonical_json_bytes(payload)
    envelope = LegalArtifactEnvelope(
        kind=kind,
        object_id=object_id,
        content_digest=sha256_ref(payload_bytes),
        producer_contract=producer_contract,
        producer_locator_set=tuple(sorted(set(locators))),
        semantic_build_ref=semantic_build_ref,
        source_revision_refs=tuple(sorted(set(source_revision_refs))),
        member_artifacts=tuple(sorted(members, key=lambda row: row.member_ref)),
        payload_media_type=payload_media_type,
        payload_size=len(payload_bytes),
    )
    return envelope, payload_bytes


def verify_imported_artifact(
    *,
    envelope: LegalArtifactEnvelope,
    payload_bytes: bytes,
    locator_ref: str,
    available_member_refs: Iterable[str] = (),
) -> LegalArtifactVerificationReceipt:
    observed = sha256_ref(payload_bytes)
    available = set(available_member_refs)
    member_states = {
        row.member_ref: "available" if row.member_ref in available else "explicitly_missing"
        for row in envelope.member_artifacts
    }
    state = "verified_available" if observed == envelope.content_digest else "digest_mismatch"
    identity = canonical_json_bytes(
        {
            "contract": LEGAL_ARTIFACT_TRANSPORT_CONTRACT,
            "object_id": envelope.object_id,
            "expected": envelope.content_digest,
            "observed": observed,
            "locator": locator_ref,
            "member_states": member_states,
        }
    )
    return LegalArtifactVerificationReceipt(
        receipt_ref="legal-artifact-verification:" + hashlib.sha256(identity).hexdigest(),
        object_id=envelope.object_id,
        expected_digest=envelope.content_digest,
        observed_digest=observed,
        locator_ref=locator_ref,
        verification_state=state,
        member_states=member_states,
    )


__all__ = [
    "LEGAL_ARTIFACT_TRANSPORT_CONTRACT",
    "LegalArtifactEnvelope",
    "LegalArtifactMember",
    "LegalArtifactVerificationReceipt",
    "export_legal_artifact",
    "verify_imported_artifact",
]
