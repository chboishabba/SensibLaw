from __future__ import annotations

import pytest

from src.storage.postgres.factor_revision_store import (
    factor_revision_payload,
    factor_revision_ref,
)


def _factor() -> dict[str, object]:
    return {
        "factor_ref": "factor:test",
        "factor_type": "semantic.argument.subject",
        "alternatives": [
            {
                "alternative_ref": "factor:test:candidate",
                "type_ref": "semantic.argument_candidate",
                "value": {"role": "subject"},
                "derivation_refs": ["grammar:test"],
            }
        ],
        "constraints": [],
        "residuals": ["antecedent_unresolved"],
        "closure_state": "requires_external_resolution",
        "metadata": {"role": "subject"},
    }


def test_factor_revision_identity_excludes_its_derived_self_reference() -> None:
    factor = _factor()
    revision_ref = factor_revision_ref(factor)
    with_explicit = {
        **factor,
        "metadata": {
            **factor["metadata"],
            "factor_revision_ref": revision_ref,
        },
    }

    assert factor_revision_ref(with_explicit) == revision_ref
    assert "factor_revision_ref" not in factor_revision_payload(with_explicit)[
        "metadata"
    ]


def test_incorrect_explicit_factor_revision_ref_fails_closed() -> None:
    factor = _factor()
    factor["metadata"] = {
        **factor["metadata"],
        "factor_revision_ref": "factor-revision:incorrect",
    }

    with pytest.raises(ValueError, match="disagrees with canonical factor content"):
        factor_revision_ref(factor)
