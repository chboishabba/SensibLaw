"""Predicate-based adapter discovery for the world-model runtime.

Replaces hardcoded if-elif adapter selection with a registry where each
adapter declares a ``can_handle`` predicate.  The runtime discovers the
best-scoring adapter for a given input envelope, or raises a structured
diagnostic explaining what generic capability is missing.

The public API accepts data, not adapter names.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class InputDiagnostic:
    """Structured diagnostic for adapter discovery failure."""

    status: str  # "unsupported_input" | "ambiguous_input"
    detected: dict[str, Any]
    missing_capabilities: list[str]
    candidate_adapters: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "detected": deepcopy(self.detected),
            "missing_capabilities": list(self.missing_capabilities),
            "candidate_adapters": list(self.candidate_adapters),
            "message": self.message,
        }


class UnsupportedInputError(ValueError):
    """Raised when no adapter can handle the input.

    The ``diagnostic`` attribute carries a structured description of what
    was detected and which generic capabilities are missing.
    """

    def __init__(self, diagnostic: InputDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


class AmbiguousInputError(ValueError):
    """Raised when multiple adapters match with equal confidence.

    The ``diagnostic`` attribute lists the tied candidates so the caller
    can inspect what went wrong.
    """

    def __init__(self, diagnostic: InputDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


@dataclass(frozen=True)
class AdapterRegistration:
    """Declaration of an adapter's capabilities.

    ``can_handle`` receives the **payload** from a normalised input
    envelope and returns a score in ``[0.0, 1.0]``.  ``0.0`` means the
    adapter cannot handle this input; ``1.0`` means certainty.

    ``produces`` and ``requires`` describe the generic carrier types the
    adapter emits and depends on, for future chain planning.
    """

    adapter_id: str
    can_handle: Callable[[Any], float]
    produces: frozenset[str] = frozenset()
    requires: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AdapterChainResult:
    """Result of a successful adapter discovery."""

    adapter_id: str
    score: float


def _text(value: Any) -> str:
    return str(value or "").strip()


def _detect_input_shape(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Build a detection summary from an input envelope."""
    input_kind = _text(envelope.get("input_kind")) or "unknown"
    payload = envelope.get("payload")

    detected: dict[str, Any] = {"input_kind": input_kind}

    if isinstance(payload, Mapping):
        keys = sorted(str(k) for k in payload.keys())[:20]
        detected["payload_keys"] = keys
        schema = _text(payload.get("schema_version"))
        if schema:
            detected["schema_version"] = schema
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        detected["payload_type"] = "sequence"
        detected["payload_length"] = len(payload)
        if payload and isinstance(payload[0], Mapping):
            detected["first_row_keys"] = sorted(str(k) for k in payload[0].keys())[:20]
    elif isinstance(payload, str):
        detected["payload_type"] = "text"
        detected["payload_length"] = len(payload)
    else:
        detected["payload_type"] = type(payload).__name__

    return detected


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ADAPTER_REGISTRY: list[AdapterRegistration] = []


def register_adapter(registration: AdapterRegistration) -> None:
    """Register an adapter with the discovery system."""
    # Prevent duplicate adapter_id registrations.
    for existing in _ADAPTER_REGISTRY:
        if existing.adapter_id == registration.adapter_id:
            raise ValueError(f"adapter already registered: {registration.adapter_id}")
    _ADAPTER_REGISTRY.append(registration)


def clear_registry() -> None:
    """Remove all registered adapters.  Intended for tests only."""
    _ADAPTER_REGISTRY.clear()


def list_registered_adapters() -> list[AdapterRegistration]:
    """Return a snapshot of all registered adapters."""
    return list(_ADAPTER_REGISTRY)


def discover_adapter(envelope: Mapping[str, Any]) -> AdapterChainResult:
    """Discover the best adapter for *envelope* or raise a diagnostic.

    The discovery process:

    1. Run every registered adapter's ``can_handle`` predicate against
       the envelope payload.
    2. Collect all adapters that returned a positive score.
    3. If exactly one adapter has the highest score, return it.
    4. If multiple adapters tie at the highest score, raise
       ``AmbiguousInputError``.
    5. If no adapter scored positively, raise ``UnsupportedInputError``.
    """
    if not _ADAPTER_REGISTRY:
        raise UnsupportedInputError(
            InputDiagnostic(
                status="unsupported_input",
                detected=_detect_input_shape(envelope),
                missing_capabilities=["adapter_registry_empty"],
                candidate_adapters=[],
                message="No adapters are registered; the adapter registry is empty.",
            )
        )

    payload = envelope.get("payload")
    scored: list[tuple[float, AdapterRegistration]] = []

    for reg in _ADAPTER_REGISTRY:
        try:
            score = reg.can_handle(payload)
        except Exception:
            score = 0.0
        if score > 0.0:
            scored.append((score, reg))

    if not scored:
        detected = _detect_input_shape(envelope)
        raise UnsupportedInputError(
            InputDiagnostic(
                status="unsupported_input",
                detected=detected,
                missing_capabilities=_infer_missing_capabilities(detected),
                candidate_adapters=[],
                message="No complete adapter chain could be discovered for this input.",
            )
        )

    # Sort descending by score.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best_score = scored[0][0]
    tied = [reg for (s, reg) in scored if s == best_score]

    if len(tied) > 1:
        detected = _detect_input_shape(envelope)
        raise AmbiguousInputError(
            InputDiagnostic(
                status="ambiguous_input",
                detected=detected,
                missing_capabilities=[],
                candidate_adapters=[r.adapter_id for r in tied],
                message=(
                    f"Multiple adapters matched with equal confidence ({best_score}): "
                    + ", ".join(r.adapter_id for r in tied)
                ),
            )
        )

    winner = tied[0]
    return AdapterChainResult(adapter_id=winner.adapter_id, score=best_score)


def _infer_missing_capabilities(detected: dict[str, Any]) -> list[str]:
    """Heuristic: guess which generic capabilities might be missing."""
    missing: list[str] = []
    input_kind = detected.get("input_kind", "unknown")
    payload_type = detected.get("payload_type", "")

    if input_kind == "unknown" and payload_type not in {"dict", "list", "text", "str"}:
        missing.append("input_detection")

    if input_kind in {"document_bundle", "directory"}:
        missing.append("document_bundle_segmentation")

    if payload_type in {"bytes", "bytearray"}:
        missing.append("binary_content_parsing")

    if not missing:
        missing.append("content_structure_recognition")

    return missing


__all__ = [
    "AdapterChainResult",
    "AdapterRegistration",
    "AmbiguousInputError",
    "InputDiagnostic",
    "UnsupportedInputError",
    "clear_registry",
    "discover_adapter",
    "list_registered_adapters",
    "register_adapter",
]
