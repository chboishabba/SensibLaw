from __future__ import annotations

from typing import Any


def pnf_candidate(predicate: str, signature: str, roles: dict[str, tuple[str, str]], provenance: str) -> dict[str, Any]:
    return {
        "predicate": predicate,
        "structural_signature": signature,
        "roles": {key: {"value": value, "entity_type": entity_type} for key, (value, entity_type) in roles.items()},
        "qualifiers": {"polarity": "positive"},
        "wrapper": {"status": "observed_syntax", "evidence_only": True},
        "provenance": [provenance],
        "source_observation_schema": "code_observation_v1",
        "domain": "code_structure",
    }
