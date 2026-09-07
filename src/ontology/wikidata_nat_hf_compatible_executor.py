from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from src.ontology.wikidata_nat_hf_selector import _fetch_manifest_cached, _preflight_selector
from src.ontology.wikidata_nat_hf_strict_executor import (
    STRICT_EXECUTOR_ID,
    _strict_evaluate,
)
from src.ontology.wikidata_nat_zelph_binary_compat import (
    select_compatible_zelph_binary,
)


COMPAT_EXECUTOR_ID = "sensiblaw.nat_hf_selector.compat.v0_1"


def hosted_hf_selector_executor_compatible(selector: Mapping[str, Any]) -> dict[str, Any]:
    """Run the strict selector only after a successful manifest meta-only ABI probe."""

    preflight = _preflight_selector(selector)
    if isinstance(preflight, dict):
        return preflight

    try:
        manifest, headers = _fetch_manifest_cached()
    except Exception as exc:
        return {
            "executor_id": COMPAT_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": {
                "network_performed": True,
                "transport": "hf-object-fetch",
                "transport_status": "manifest_fetch_failed",
                "detail": f"{type(exc).__name__}: {exc}",
                "source_support_paid": False,
                "consumer_verification_performed": False,
                "semantic_promotion_performed": False,
                "edits_performed": False,
            },
            "outputs": {},
        }

    compatibility = select_compatible_zelph_binary(manifest)
    selected = compatibility.get("selected_binary")
    if not selected:
        return {
            "executor_id": COMPAT_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": {
                "network_performed": True,
                "transport": "hf-object-fetch",
                "transport_status": "zelph_binary_manifest_incompatible",
                "detail": (
                    "No candidate Zelph binary passed the canonical v2 manifest meta-only "
                    "compatibility probe. Nat acquisition was not attempted."
                ),
                "binary_compatibility": compatibility,
                "source_support_paid": False,
                "consumer_verification_performed": False,
                "semantic_promotion_performed": False,
                "edits_performed": False,
            },
            "outputs": {},
        }

    old = os.environ.get("ZELPH_BIN")
    os.environ["ZELPH_BIN"] = str(selected)
    try:
        result = _strict_evaluate(selector, manifest=manifest, headers=headers)
    finally:
        if old is None:
            os.environ.pop("ZELPH_BIN", None)
        else:
            os.environ["ZELPH_BIN"] = old

    receipt = dict(result.get("executor_receipt") or {})
    receipt["binary_compatibility"] = compatibility
    receipt["selected_zelph_binary"] = str(selected)
    result = dict(result)
    result["executor_id"] = COMPAT_EXECUTOR_ID
    result["executor_receipt"] = receipt
    return result


__all__ = ["COMPAT_EXECUTOR_ID", "hosted_hf_selector_executor_compatible"]
