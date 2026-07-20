from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION = "sl.world_model_input_envelope.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _reject_selector(name: str, value: Any) -> None:
    if _text(value):
        raise ValueError(
            f"{name} is not part of the public world-model input boundary; "
            "pass data directly and use generic options instead"
        )


_SMUGGLED_SELECTORS = frozenset({
    "adapter_hint",
    "_compat_family",
    "_compat_profile",
    "_artifact_shape",
})


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clone(value: Any) -> Any:
    try:
        return deepcopy(value)
    except Exception:
        return value


def build_input_envelope(
    input_data: Any,
    *,
    input_id: str | None = None,
    input_kind: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION,
        "input_id": _text(input_id) or "",
        "input_kind": _text(input_kind) or "",
        "payload": _clone(input_data),
        "metadata": deepcopy(dict(metadata or {})),
    }


def _normalize_text_payload(text: str) -> dict[str, Any]:
    return {
        "input_kind": "text",
        "payload": {
            "text": text,
        },
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_path_payload(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved.is_dir():
        documents: list[dict[str, Any]] = []
        for child in sorted(resolved.rglob("*")):
            if not child.is_file():
                continue
            suffix = child.suffix.casefold()
            record: dict[str, Any] = {
                "path": str(child),
                "suffix": suffix,
                "name": child.name,
            }
            if suffix in {".txt", ".md", ".markdown", ".json", ".yml", ".yaml"}:
                try:
                    record["text"] = child.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    record["text"] = child.read_text(encoding="utf-8", errors="replace")
            documents.append(record)
        return {
            "input_kind": "document_bundle",
            "payload": {
                "root_path": str(resolved),
                "documents": documents,
            },
        }
    if resolved.suffix.casefold() == ".json":
        return {
            "input_kind": "json_file",
            "payload": _read_json(resolved),
            "metadata": {"path": str(resolved)},
        }
    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    return {
        "input_kind": "text_file",
        "payload": {
            "path": str(resolved),
            "text": text,
        },
        "metadata": {"path": str(resolved)},
    }


def normalize_input_envelope(
    input_data: Any,
    *,
    input_id: str | None = None,
    input_kind: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(input_data, Mapping) and _text(input_data.get("schema_version")) == WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION:
        payload = deepcopy(dict(input_data))
        payload["input_id"] = _text(payload.get("input_id"))
        payload["input_kind"] = _text(payload.get("input_kind"))
        _reject_selector("adapter_hint", payload.get("adapter_hint"))
        payload.pop("adapter_hint", None)
        metadata = deepcopy(dict(payload.get("metadata") or {}))
        for key in _SMUGGLED_SELECTORS:
            _reject_selector(key, metadata.get(key))
            metadata.pop(key, None)
        payload["metadata"] = metadata
        return payload

    envelope = build_input_envelope(
        input_data,
        input_id=input_id,
        input_kind=input_kind,
        metadata=metadata,
    )

    if input_kind:
        envelope["input_kind"] = _text(input_kind)
        return envelope

    if isinstance(input_data, Path):
        path_payload = _load_path_payload(input_data)
        envelope["input_kind"] = path_payload["input_kind"]
        envelope["payload"] = path_payload["payload"]
        envelope["metadata"] = {
            **deepcopy(dict(envelope.get("metadata") or {})),
            **deepcopy(dict(path_payload.get("metadata") or {})),
        }
        envelope["input_id"] = _text(envelope.get("input_id")) or _text(path_payload.get("metadata", {}).get("path"))
        return envelope

    if isinstance(input_data, str):
        candidate_path = Path(input_data)
        if candidate_path.exists():
            path_payload = _load_path_payload(candidate_path)
            envelope["input_kind"] = path_payload["input_kind"]
            envelope["payload"] = path_payload["payload"]
            envelope["metadata"] = {
                **deepcopy(dict(envelope.get("metadata") or {})),
                **deepcopy(dict(path_payload.get("metadata") or {})),
            }
            envelope["input_id"] = _text(envelope.get("input_id")) or _text(path_payload.get("metadata", {}).get("path"))
            return envelope
        text_payload = _normalize_text_payload(input_data)
        envelope["input_kind"] = text_payload["input_kind"]
        envelope["payload"] = text_payload["payload"]
        envelope["input_id"] = _text(envelope.get("input_id")) or "text_input"
        return envelope

    if isinstance(input_data, Mapping):
        envelope["input_kind"] = "mapping"
        envelope["input_id"] = _text(envelope.get("input_id")) or _text(input_data.get("artifact_id")) or _text(input_data.get("model_id"))
        return envelope

    if isinstance(input_data, Sequence) and not isinstance(input_data, (bytes, bytearray)):
        envelope["input_kind"] = "sequence"
        envelope["input_id"] = _text(envelope.get("input_id")) or "sequence_input"
        return envelope

    envelope["input_kind"] = "opaque"
    envelope["input_id"] = _text(envelope.get("input_id")) or "opaque_input"
    return envelope


__all__ = [
    "WORLD_MODEL_INPUT_ENVELOPE_SCHEMA_VERSION",
    "build_input_envelope",
    "normalize_input_envelope",
]
