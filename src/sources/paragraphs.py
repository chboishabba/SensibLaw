from __future__ import annotations

from typing import Protocol, Sequence, TypeVar


class NumberedParagraph(Protocol):
    number: int


ParagraphT = TypeVar("ParagraphT", bound=NumberedParagraph)


def select_paragraphs(
    paragraphs: Sequence[ParagraphT],
    *,
    requested: Sequence[int],
    window: int = 0,
) -> list[ParagraphT]:
    if not requested:
        return []

    by_number = {paragraph.number: paragraph for paragraph in paragraphs}
    radius = max(0, window)
    selected_numbers: set[int] = set()
    for number in requested:
        for candidate in range(number - radius, number + radius + 1):
            if candidate in by_number:
                selected_numbers.add(candidate)
    return [paragraph for paragraph in paragraphs if paragraph.number in selected_numbers]
