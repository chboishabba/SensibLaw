from __future__ import annotations

from collections.abc import Mapping
from typing import Any

try:
    from src.sensiblaw.interfaces.shared_reducer import (
        PredicateAtom,
        QualifierState,
        WrapperState,
        collect_canonical_predicate_atoms,
    )
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    from sensiblaw.interfaces.shared_reducer import (
        PredicateAtom,
        QualifierState,
        WrapperState,
        collect_canonical_predicate_atoms,
    )


PROJECTOR_VERSION = "sensiblaw_market_news_projector_v2"
SUPPORTED_EXTRACTION_PROFILE = "market_news"
_WRAPPER_STATUS = "market_news_projection_candidate"


def _read_field(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _canonical_text_value(canonical_text: Any) -> str:
    raw = _read_field(canonical_text, "text")
    return str(raw or "").strip()


def _canonical_text_id(canonical_text: Any) -> str | None:
    raw = _read_field(canonical_text, "text_id")
    return str(raw) if raw else None


def _parsed_envelope_id(parsed_envelope: Any) -> str | None:
    raw = _read_field(parsed_envelope, "envelope_id")
    return str(raw) if raw else None


def _normalize_provenance(provenance: Mapping[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in dict(provenance or {}).items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        normalized[str(key)] = text
    return normalized


def _merge_provenance(
    atom: PredicateAtom,
    *,
    text_id: str | None,
    envelope_id: str | None,
    provenance: Mapping[str, str],
) -> tuple[str, ...]:
    refs: list[str] = list(atom.provenance)
    refs.append(f"projector:{PROJECTOR_VERSION}")
    if text_id:
        refs.append(f"text_id:{text_id}")
    if envelope_id:
        refs.append(f"envelope_id:{envelope_id}")
    for key in sorted(provenance):
        refs.append(f"{key}:{provenance[key]}")
    deduped: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        deduped.append(ref)
    return tuple(deduped)


def _provenance_modifiers(provenance: Mapping[str, str]) -> dict[str, str]:
    keep = ("provider", "root_code", "source_url", "source", "event_id", "published_at")
    return {key: provenance[key] for key in keep if key in provenance}


def project_event_text_to_predicate_atoms(
    canonical_text: Any,
    parsed_envelope: Any,
    provenance: Mapping[str, Any] | None,
    *,
    extraction_profile: str = SUPPORTED_EXTRACTION_PROFILE,
) -> list[PredicateAtom]:
    """Project canonical text to native PredicateAtom carriers via the shared reducer.

    This public surface is intentionally generic: it wraps reducer output with
    bounded provenance and evidence-only wrapper state, but it does not apply
    domain-specific market-news recovery or heuristic role filling.
    """

    if extraction_profile != SUPPORTED_EXTRACTION_PROFILE:
        raise ValueError(
            f"unsupported extraction_profile={extraction_profile!r}; expected {SUPPORTED_EXTRACTION_PROFILE!r}"
        )

    text = _canonical_text_value(canonical_text)
    if not text:
        return []

    normalized_provenance = _normalize_provenance(provenance)
    text_id = _canonical_text_id(canonical_text)
    envelope_id = _parsed_envelope_id(parsed_envelope)
    projected: list[PredicateAtom] = []
    for index, atom in enumerate(collect_canonical_predicate_atoms(text)):
        projected.append(
            PredicateAtom(
                predicate=atom.predicate,
                structural_signature=atom.structural_signature,
                roles=atom.roles,
                qualifiers=QualifierState(
                    polarity=atom.qualifiers.polarity,
                    modality=atom.qualifiers.modality or "reported",
                    tense=atom.qualifiers.tense,
                    certainty=atom.qualifiers.certainty or "candidate",
                    condition=atom.qualifiers.condition,
                    temporal_scope=atom.qualifiers.temporal_scope,
                    jurisdiction_scope=atom.qualifiers.jurisdiction_scope,
                ),
                wrapper=WrapperState(status=_WRAPPER_STATUS, evidence_only=True),
                modifiers={
                    **dict(atom.modifiers),
                    **_provenance_modifiers(normalized_provenance),
                    "extraction_profile": extraction_profile,
                    "projector_version": PROJECTOR_VERSION,
                    "candidate_status": "derived_candidate",
                    "projection_mode": "shared_reducer_only",
                },
                provenance=_merge_provenance(
                    atom,
                    text_id=text_id,
                    envelope_id=envelope_id,
                    provenance=normalized_provenance,
                ),
                atom_id=atom.atom_id or f"market_news_atom_{index}",
                domain=SUPPORTED_EXTRACTION_PROFILE,
            )
        )
    return projected


__all__ = [
    "PROJECTOR_VERSION",
    "SUPPORTED_EXTRACTION_PROFILE",
    "project_event_text_to_predicate_atoms",
]
