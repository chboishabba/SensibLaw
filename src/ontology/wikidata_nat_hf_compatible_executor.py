from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from src.ontology.wikidata_nat_hf_partial_read import (
    fetch_live_wikidata_statement_payload,
)
from src.ontology.wikidata_nat_hf_selector import _fetch_manifest_cached, _preflight_selector
from src.ontology.wikidata_nat_hf_strict_executor import (
    STRICT_EXECUTOR_ID,
    _strict_evaluate,
)
from src.ontology.wikidata_nat_zelph_binary_compat import (
    select_compatible_zelph_binary,
)
from src.policy.carriers.canonical import canonical_sha256


COMPAT_EXECUTOR_ID = "sensiblaw.nat_hf_selector.compat.v0_1"
QID_KEYED_OUTPUTS = (
    "statement_snapshot",
    "qualifier_snaks",
    "reference_snaks",
    "source_revision_lineage",
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return sorted({_text(value) for value in values if _text(value)})


def _merge_wikidata_outputs(base: Mapping[str, Any], extra: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in base.items():
        if key == "content_address":
            continue
        merged[key] = dict(value) if key in QID_KEYED_OUTPUTS and isinstance(value, Mapping) else value
    for key, value in extra.items():
        if key == "content_address":
            continue
        if key in QID_KEYED_OUTPUTS and isinstance(value, Mapping):
            current = dict(merged.get(key) or {})
            current.update(dict(value))
            merged[key] = current
        else:
            merged[key] = value
    merged["content_address"] = "sha256:" + canonical_sha256(merged)
    return merged


def _apply_direct_wikidata_identity_fallback(
    selector: Mapping[str, Any], result: Mapping[str, Any]
) -> dict[str, Any]:
    """Pay only the explicit-QID identity seam left by clean Zelph exhaustion.

    A requested QID is already an exact Wikidata identifier.  Clean failure to
    locate that name in the hosted Zelph nodeOfName partition is therefore a
    routing/graph-confirmation residual, not proof that the Wikidata entity is
    unavailable.  For those cleanly-unresolved QIDs only, try the existing
    revision-locked Wikidata entity-export source directly, one QID at a time.

    Successful entity export confirms the explicit Wikidata subject sufficiently
    for native Q/property coverage recomputation.  It does not create a Zelph
    route-cache entry, source-support payment, authority, consumer verification,
    semantic promotion, or edit authority.
    """

    current = dict(result)
    receipt = dict(current.get("executor_receipt") or {})
    unresolved = _text_list(receipt.get("unresolved_qids"))
    if not unresolved:
        receipt.setdefault("zelph_unresolved_qids", [])
        receipt.setdefault("wikidata_direct_identity_confirmed_qids", [])
        receipt.setdefault("wikidata_direct_identity_fallback_failures", {})
        current["executor_receipt"] = receipt
        return current

    if _text(current.get("execution_outcome")) not in {
        "executed_with_output",
        "executed_no_match",
    }:
        return current

    partial_read = receipt.get("partial_read") or {}
    if _text(partial_read.get("status")) != "partial":
        return current
    if partial_read.get("failure"):
        return current

    properties = _text_list(selector.get("properties"))
    merged_outputs = dict(current.get("outputs") or {})
    confirmed: list[str] = []
    failures: dict[str, str] = {}

    for qid in unresolved:
        try:
            extra = fetch_live_wikidata_statement_payload([qid], properties)
        except Exception as exc:
            failures[qid] = f"{type(exc).__name__}: {exc}"
            continue
        merged_outputs = _merge_wikidata_outputs(merged_outputs, extra)
        confirmed.append(qid)

    remaining = [qid for qid in unresolved if qid not in set(confirmed)]
    prior_statement_fetch_qids = _text_list(receipt.get("statement_fetch_qids"))
    statement_fetch_qids = sorted(set(prior_statement_fetch_qids + confirmed))

    receipt["zelph_unresolved_qids"] = list(unresolved)
    receipt["wikidata_direct_identity_confirmed_qids"] = sorted(confirmed)
    receipt["wikidata_direct_identity_fallback_failures"] = dict(sorted(failures.items()))
    receipt["statement_fetch_qids"] = statement_fetch_qids
    receipt["unresolved_qids"] = remaining
    receipt["all_requested_qids_resolved"] = not remaining
    receipt["partial_identity_subset"] = bool(remaining)
    receipt["identity_confirmation_sources"] = {
        "zelph_node_of_name": sorted(
            set(_text_list(receipt.get("requested_qids"))) - set(unresolved)
        ),
        "wikidata_revision_locked_entity_export": sorted(confirmed),
        "still_unresolved": remaining,
    }
    receipt["direct_wikidata_fallback_pays_zelph_route_residual"] = False
    receipt["direct_wikidata_fallback_pays_source_support"] = False
    if confirmed:
        receipt["transport_status"] = (
            "executed_via_clean_zelph_partial_plus_direct_wikidata_identity_fallback"
            if not remaining
            else "executed_via_partial_identity_subset_plus_direct_wikidata_identity_fallback"
        )
        receipt["detail"] = (
            "Hosted Zelph cleanly exhausted with explicit QIDs unresolved in nodeOfName. "
            "Revision-locked Wikidata entity export independently confirmed the listed "
            "explicit QIDs for native statement-family coverage. Zelph routing remains "
            "unconfirmed for those QIDs and no source-support or authority payment is made."
        )
        current["execution_outcome"] = "executed_with_output"
        current["outputs"] = merged_outputs

    current["executor_receipt"] = receipt
    return current


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

    result = _apply_direct_wikidata_identity_fallback(selector, result)
    receipt = dict(result.get("executor_receipt") or {})
    receipt["binary_compatibility"] = compatibility
    receipt["selected_zelph_binary"] = str(selected)
    result = dict(result)
    result["executor_id"] = COMPAT_EXECUTOR_ID
    result["executor_receipt"] = receipt
    return result


__all__ = ["COMPAT_EXECUTOR_ID", "hosted_hf_selector_executor_compatible"]
