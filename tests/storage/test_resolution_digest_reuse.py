from __future__ import annotations

from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres.work_conserving_resolution_persistence import (
    _demand_semantic_key_digest,
)


def test_demand_ref_digest_is_exact_semantic_key_sha() -> None:
    semantic_key = {
        "document_ref": "document:1",
        "factor_ref": "factor:1",
        "factor_revision_ref": "factor-revision:" + "a" * 64,
        "factor_type": "semantic.argument_reference",
        "residuals": ["antecedent_unresolved"],
        "candidate_set_refs": ["binding-candidate-set:1"],
    }
    digest = canonical_sha256(semantic_key)
    demand_ref = "demand:" + digest

    assert _demand_semantic_key_digest(demand_ref) == bytes.fromhex(digest)
