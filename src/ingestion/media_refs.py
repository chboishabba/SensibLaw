"""Reusable immutable references for canonical media artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from src.policy.carriers.canonical import require_text


@dataclass(frozen=True)
class TextSpanRef:
    text_id: str
    start_char: int
    end_char: int

    def to_dict(self) -> dict[str, object]:
        if self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("text span must be non-empty and non-negative")
        return {
            "text_id": require_text(self.text_id, "text_id"),
            "start_char": self.start_char,
            "end_char": self.end_char,
        }


@dataclass(frozen=True)
class SegmentRef:
    text_id: str
    segment_id: str
    order_index: int
    page: int | None = None

    def to_dict(self) -> dict[str, object]:
        if self.order_index < 0:
            raise ValueError("segment order_index must be non-negative")
        row: dict[str, object] = {
            "text_id": require_text(self.text_id, "text_id"),
            "segment_id": require_text(self.segment_id, "segment_id"),
            "order_index": self.order_index,
        }
        if self.page is not None:
            if self.page < 1:
                raise ValueError("page must be positive")
            row["page"] = self.page
        return row
