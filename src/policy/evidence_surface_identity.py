"""Deterministic content identity for governed evidence surfaces.

Archive donor: RequestProject.Publish proves its canonical publication round-trip
and uses canonical rendered content to name an ontology. SensibLaw adopts only
the structural principle here: canonical JSON bytes receive a deterministic
SHA-256 content identifier suitable for replay/provenance references.

A content identifier proves byte/content identity under this renderer only. It
creates no source truth, identity alignment, migration safety, or promotion.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

EVIDENCE_SURFACE_IDENTITY_SCHEMA_VERSION = "sl.evidence_surface_identity.v0_1"


def canonical_surface_json(surface: Mapping[str, Any]) -> str:
    if not isinstance(surface, Mapping):
        raise ValueError("surface must be a mapping")
    return json.dumps(
        surface,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def build_evidence_surface_identity(surface: Mapping[str, Any]) -> dict[str, Any]:
    canonical = canonical_surface_json(surface)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schema_version": EVIDENCE_SURFACE_IDENTITY_SCHEMA_VERSION,
        "algorithm": "sha256-canonical-json-v1",
        "content_id": f"sl-surface-sha256:{digest}",
        "canonical_byte_length": len(canonical.encode("utf-8")),
        "identity_scope": "rendered_content_only",
        "truth_authority": False,
        "identity_alignment_authority": False,
        "promotion_authority": False,
        "edit_authority": False,
    }


__all__ = [
    "EVIDENCE_SURFACE_IDENTITY_SCHEMA_VERSION",
    "canonical_surface_json",
    "build_evidence_surface_identity",
]
