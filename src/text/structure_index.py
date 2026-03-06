from __future__ import annotations

from src.text.lexeme_index import collect_lexeme_occurrences
from src.text.operational_structure import StructureOccurrence, collect_operational_structure_occurrences


def collect_structure_occurrences(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    include_legal: bool = True,
    include_operational: bool = True,
) -> list[StructureOccurrence]:
    combined: list[StructureOccurrence] = []
    if include_legal:
        combined.extend(
            StructureOccurrence(
                text=occ.text,
                norm_text=occ.norm_text,
                kind=occ.kind,
                start_char=occ.start_char,
                end_char=occ.end_char,
                flags=occ.flags,
            )
            for occ in collect_lexeme_occurrences(text, canonical_mode=canonical_mode)
        )
    if include_operational:
        combined.extend(collect_operational_structure_occurrences(text))
    deduped: dict[tuple[str, str, int, int], StructureOccurrence] = {}
    for occ in combined:
        deduped[(occ.kind, occ.norm_text, occ.start_char, occ.end_char)] = occ
    return sorted(
        deduped.values(),
        key=lambda occ: (occ.start_char, occ.end_char, occ.kind, occ.norm_text),
    )
