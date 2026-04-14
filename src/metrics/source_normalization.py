from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple


DEFAULT_NORMALIZATION_THRESHOLDS = {
    "contract": 1.0,
    "authority": 0.8,
    "provenance": 0.9,
    "live_or_fallback": 0.9,
    "follow_ready": 0.85,
    "translation_alignment": 0.8,
}


@dataclass(frozen=True)
class SourceNormalizationResult:
    total_families: int
    contract_completeness_share: float
    authority_clarity_share: float
    provenance_completeness_share: float
    live_observability_share: float
    fallback_observability_share: float
    live_or_fallback_share: float
    follow_ready_share: float
    translation_alignment_share: float
    territory_hybrid_risk_share: float
    normalized: bool
    violations: Tuple[str, ...]


@dataclass(frozen=True)
class UnAdopterReadinessResult:
    total_units: int
    contract_share: float
    provenance_share: float
    translation_alignment_share: float
    authority_share: float
    follow_ready_share: float
    normalized: bool
    violations: Tuple[str, ...]


def _authority_count(entry: Mapping[str, object]) -> int:
    if "authority_nodes" in entry:
        value = entry["authority_nodes"]
        if isinstance(value, int):
            return value
    labels = entry.get("authority_labels")
    if isinstance(labels, Sequence):
        return len(labels)
    return 0


def compute_source_normalization_metrics(
    families: Iterable[Mapping[str, object]],
    *,
    required_authority_nodes: int = 1,
    thresholds: Mapping[str, float] | None = None,
) -> SourceNormalizationResult:
    thresholds = {**DEFAULT_NORMALIZATION_THRESHOLDS, **(thresholds or {})}
    total = 0
    contract_yes = 0
    authority_yes = 0
    provenance_yes = 0
    live_yes = 0
    fallback_yes = 0
    follow_ready_yes = 0
    translation_alignment_yes = 0
    live_or_fallback_yes = 0
    violations: list[str] = []

    for idx, entry in enumerate(families):
        total += 1
        family_id = entry.get("id") or f"family#{idx}"
        contract = bool(entry.get("contract_complete"))
        authority_nodes = _authority_count(entry)
        authority_ok = authority_nodes >= required_authority_nodes
        provenance_ok = bool(entry.get("provenance_links"))
        live_visible = bool(entry.get("visible_in_live"))
        fallback_visible = bool(entry.get("visible_in_fallback"))
        follow_ready = bool(entry.get("follow_ready"))
        translation_flag = bool(
            entry.get("translation_aligned")
            or entry.get("translation_alignment_score")
        )

        contract_yes += contract
        if authority_ok:
            authority_yes += 1
        provenance_yes += int(provenance_ok)
        live_yes += int(live_visible)
        fallback_yes += int(fallback_visible)
        follow_ready_yes += int(follow_ready)
        translation_alignment_yes += int(translation_flag)
        if live_visible or fallback_visible:
            live_or_fallback_yes += 1

        missing: list[str] = []
        if not contract:
            missing.append("contract")
        if not authority_ok:
            missing.append("authority")
        if not provenance_ok:
            missing.append("provenance")
        if not (live_visible or fallback_visible):
            missing.append("observability")
        if not follow_ready:
            missing.append("follow_ready")
        if not translation_flag:
            missing.append("translation_alignment")
        if missing:
            violations.append(f"{family_id} missing {', '.join(missing)}")

    if total == 0:
        return SourceNormalizationResult(
            total_families=0,
            contract_completeness_share=0.0,
            authority_clarity_share=0.0,
            provenance_completeness_share=0.0,
            live_observability_share=0.0,
            fallback_observability_share=0.0,
            live_or_fallback_share=0.0,
            follow_ready_share=0.0,
            translation_alignment_share=0.0,
            normalized=False,
            violations=(),
        )

    contract_share = contract_yes / total
    authority_share = authority_yes / total
    provenance_share = provenance_yes / total
    live_share = live_yes / total
    fallback_share = fallback_yes / total
    live_or_fallback_share = live_or_fallback_yes / total
    follow_ready_share = follow_ready_yes / total
    translation_alignment_share = translation_alignment_yes / total

    normalized = (
        contract_share >= thresholds["contract"]
        and authority_share >= thresholds["authority"]
        and provenance_share >= thresholds["provenance"]
        and live_or_fallback_share >= thresholds["live_or_fallback"]
        and follow_ready_share >= thresholds["follow_ready"]
        and translation_alignment_share >= thresholds["translation_alignment"]
    )

    return SourceNormalizationResult(
        total_families=total,
        contract_completeness_share=contract_share,
        authority_clarity_share=authority_share,
        provenance_completeness_share=provenance_share,
        live_observability_share=live_share,
        fallback_observability_share=fallback_share,
        live_or_fallback_share=live_or_fallback_share,
        follow_ready_share=follow_ready_share,
        translation_alignment_share=translation_alignment_share,
        normalized=normalized,
        violations=tuple(violations),
    )


def evaluate_un_adopter_readiness(
    families: Iterable[Mapping[str, object]],
    *,
    required_authority_nodes: int = 1,
    thresholds: Mapping[str, float] | None = None,
) -> UnAdopterReadinessResult:
    thresholds = {
        "contract": 1.0,
        "provenance": 0.9,
        "translation_alignment": 0.8,
        "authority": 0.8,
        "follow_ready": 0.85,
        **(thresholds or {}),
    }

    metrics = compute_source_normalization_metrics(
        families,
        required_authority_nodes=required_authority_nodes,
        thresholds=thresholds,
    )

    normalized = (
        metrics.contract_completeness_share >= thresholds["contract"]
        and metrics.provenance_completeness_share >= thresholds["provenance"]
        and metrics.translation_alignment_share >= thresholds["translation_alignment"]
        and metrics.authority_clarity_share >= thresholds["authority"]
        and metrics.follow_ready_share >= thresholds["follow_ready"]
    )

    return UnAdopterReadinessResult(
        total_units=metrics.total_families,
        contract_share=metrics.contract_completeness_share,
        provenance_share=metrics.provenance_completeness_share,
        translation_alignment_share=metrics.translation_alignment_share,
        authority_share=metrics.authority_clarity_share,
        follow_ready_share=metrics.follow_ready_share,
        normalized=normalized,
        violations=metrics.violations,
    )


@dataclass(frozen=True)
class LiveUnReadinessResult:
    total_units: int
    contract_share: float
    provenance_share: float
    translation_alignment_share: float
    live_share: float
    follow_ready_share: float
    live_document_share: float
    normalized: bool
    violations: Tuple[str, ...]


@dataclass(frozen=True)
class WorldBankReadinessResult:
    total_units: int
    contract_share: float
    provenance_share: float
    translation_alignment_share: float
    live_share: float
    fallbacks_share: float
    follow_ready_share: float
    normalized: bool
    violations: Tuple[str, ...]


@dataclass(frozen=True)
class IccReadinessResult:
    total_units: int
    contract_share: float
    provenance_share: float
    translation_alignment_share: float
    live_share: float
    fallback_share: float
    follow_ready_share: float
    normalized: bool
    violations: Tuple[str, ...]


def evaluate_icc_readiness(
    families: Iterable[Mapping[str, object]],
    *,
    thresholds: Mapping[str, float] | None = None,
) -> IccReadinessResult:
    thresholds = {
        "contract": 0.95,
        "provenance": 0.9,
        "translation_alignment": 0.85,
        "live": 0.8,
        "fallback": 0.8,
        "follow_ready": 0.85,
        **(thresholds or {}),
    }

    metrics = compute_source_normalization_metrics(families)
    normalized = (
        metrics.contract_completeness_share >= thresholds["contract"]
        and metrics.provenance_completeness_share >= thresholds["provenance"]
        and metrics.translation_alignment_share >= thresholds["translation_alignment"]
        and metrics.live_observability_share >= thresholds["live"]
        and metrics.fallback_observability_share >= thresholds["fallback"]
        and metrics.follow_ready_share >= thresholds["follow_ready"]
    )

    return IccReadinessResult(
        total_units=metrics.total_families,
        contract_share=metrics.contract_completeness_share,
        provenance_share=metrics.provenance_completeness_share,
        translation_alignment_share=metrics.translation_alignment_share,
        live_share=metrics.live_observability_share,
        fallback_share=metrics.fallback_observability_share,
        follow_ready_share=metrics.follow_ready_share,
        normalized=normalized,
        violations=metrics.violations,
    )


def evaluate_live_un_readiness(
    families: Iterable[Mapping[str, object]],
    *,
    thresholds: Mapping[str, float] | None = None,
) -> LiveUnReadinessResult:
    thresholds = {
        "contract": 1.0,
        "provenance": 0.9,
        "translation_alignment": 0.9,
        "live": 0.9,
        "live_document": 0.9,
        "follow_ready": 0.85,
        **(thresholds or {}),
    }

    metrics = compute_source_normalization_metrics(families)
    total = 0
    live_document_yes = 0
    for entry in families:
        total += 1
        live_visible = bool(entry.get("visible_in_live"))
        live_document_ready = bool(entry.get("live_document_ready"))
        if live_visible and live_document_ready:
            live_document_yes += 1
    live_document_share = live_document_yes / total if total else 0.0

    normalized = (
        metrics.contract_completeness_share >= thresholds["contract"]
        and metrics.provenance_completeness_share >= thresholds["provenance"]
        and metrics.translation_alignment_share >= thresholds["translation_alignment"]
        and metrics.live_observability_share >= thresholds["live"]
        and metrics.follow_ready_share >= thresholds["follow_ready"]
        and live_document_share >= thresholds["live_document"]
    )

    return LiveUnReadinessResult(
        total_units=metrics.total_families,
        contract_share=metrics.contract_completeness_share,
        provenance_share=metrics.provenance_completeness_share,
        translation_alignment_share=metrics.translation_alignment_share,
        live_share=metrics.live_observability_share,
        follow_ready_share=metrics.follow_ready_share,
        live_document_share=live_document_share,
        normalized=normalized,
        violations=metrics.violations,
    )


def evaluate_world_bank_readiness(
    families: Iterable[Mapping[str, object]],
    *,
    thresholds: Mapping[str, float] | None = None,
) -> WorldBankReadinessResult:
    thresholds = {
        "contract": 1.0,
        "provenance": 0.9,
        "translation_alignment": 0.85,
        "live": 0.85,
        "fallback": 0.85,
        "follow_ready": 0.8,
        **(thresholds or {}),
    }

    metrics = compute_source_normalization_metrics(families)
    normalized = (
        metrics.contract_completeness_share >= thresholds["contract"]
        and metrics.provenance_completeness_share >= thresholds["provenance"]
        and metrics.translation_alignment_share >= thresholds["translation_alignment"]
        and metrics.live_observability_share >= thresholds["live"]
        and metrics.fallback_observability_share >= thresholds["fallback"]
        and metrics.follow_ready_share >= thresholds["follow_ready"]
    )

    return WorldBankReadinessResult(
        total_units=metrics.total_families,
        contract_share=metrics.contract_completeness_share,
        provenance_share=metrics.provenance_completeness_share,
        translation_alignment_share=metrics.translation_alignment_share,
        live_share=metrics.live_observability_share,
        fallbacks_share=metrics.fallback_observability_share,
        follow_ready_share=metrics.follow_ready_share,
        normalized=normalized,
        violations=metrics.violations,
    )
