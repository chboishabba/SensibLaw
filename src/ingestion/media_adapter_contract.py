"""Capability-oriented media adapter contract.

Adapters are selected by media type/capability (PDF, text, HTML, etc.), never by
corpus identity. GWB and AU remain proof corpora, not adapter implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from src.policy.carriers.canonical import canonical_refs, require_text


@dataclass(frozen=True)
class MediaAdapterCapability:
    adapter_ref: str
    media_types: tuple[str, ...]
    produces: tuple[str, ...] = ("canonical_text", "segments", "units")

    def to_dict(self) -> dict[str, object]:
        return {
            "adapter_ref": require_text(self.adapter_ref, "adapter_ref"),
            "media_types": list(canonical_refs(self.media_types)),
            "produces": list(canonical_refs(self.produces)),
        }


class MediaAdapter(Protocol):
    capability: MediaAdapterCapability

    def adapt(
        self,
        *,
        source_ref: str,
        payload: bytes | str,
        metadata: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...
