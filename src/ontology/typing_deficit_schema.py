from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


def _canonical_source_label(source: str | None) -> str:
    value = (source or "").strip()
    lower = value.lower()
    if lower.startswith("au"):
        return "au"
    if "gwb" in lower:
        return "gwb"
    if "chat" in lower or "tircorder" in lower:
        return "chat_history"
    if value:
        return value
    return "unknown"


def _infer_source(payload: Mapping[str, Any]) -> str:
    canonical = payload.get("canonical_identity")
    if isinstance(canonical, Mapping):
        identity = canonical.get("identity_class")
        if isinstance(identity, str) and identity.strip():
            return _canonical_source_label(identity)
    return _canonical_source_label(
        str(payload.get("source_system") or payload.get("artifact_id") or "unknown").strip()
    )


def _normalize_signal(signal: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    entry = dict(signal)
    entry.setdefault("signal_id", f"{source}:{entry.get('signal_id') or uuid4_signifier(entry)}")
    entry.setdefault("source", source)
    entry.setdefault("signal_kind", entry.get("signal_kind") or "missing_instance_of_typing_deficit")
    return entry


def uuid4_signifier(entry: Mapping[str, Any]) -> str:
    from uuid import uuid4

    return str(entry.get("linked_qid") or entry.get("packet_id") or uuid4())


def collect_typing_deficit_signals(payloads: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        raw_signals = payload.get("typing_deficit_signals")
        if not isinstance(raw_signals, Sequence):
            continue
        source_hint = _infer_source(payload)
        for signal in raw_signals:
            if not isinstance(signal, Mapping):
                continue
            entry_source = _canonical_source_label(str(signal.get("source") or source_hint))
            normalized = _normalize_signal(signal, source=entry_source)
            signals.append(normalized)
    return signals
