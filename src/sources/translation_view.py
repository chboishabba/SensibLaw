from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class TranslationView:
    source_id: str
    target_language: str
    translator: str
    consistency_score: float
    drift_flag: bool
    alignment_notes: Sequence[str] = ()
    status: str = "translation"

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v or v == 0}


def build_translation_view(
    *,
    source_id: str,
    target_language: str,
    translator: str,
    consistency_score: float,
    drift_flag: bool,
    alignment_notes: Sequence[str] | None = None,
) -> dict[str, Any]:
    if not 0 <= consistency_score <= 1:
        raise ValueError("consistency_score must be between 0 and 1")
    return TranslationView(
        source_id=source_id,
        target_language=target_language,
        translator=translator,
        consistency_score=consistency_score,
        drift_flag=drift_flag,
        alignment_notes=tuple(alignment_notes or []),
    ).to_dict()
