from __future__ import annotations

from typing import Protocol, Sequence, TypeVar


class SearchHitLike(Protocol):
    url: str
    citation: str | None


HitT = TypeVar("HitT", bound=SearchHitLike)


def select_search_hit(
    hits: Sequence[HitT],
    *,
    strategy: str = "first",
    mnc: str | None = None,
    index: int = 0,
    path_contains: str | None = None,
) -> tuple[HitT, str]:
    if not hits:
        raise RuntimeError("No search hits returned")

    if strategy == "first":
        return hits[0], "first"

    if strategy == "by_index":
        if index < 0 or index >= len(hits):
            raise IndexError("Index outside search results range")
        return hits[index], f"by_index:{index}"

    if strategy == "by_mnc":
        if not mnc:
            raise ValueError("mnc must be provided for strategy=by_mnc")
        for hit in hits:
            if hit.citation and hit.citation.lower() == mnc.lower():
                return hit, f"by_mnc:{mnc}"
        raise RuntimeError("No hit matched requested MNC")

    if strategy == "by_path":
        if not path_contains:
            raise ValueError("path_contains must be provided for strategy=by_path")
        for hit in hits:
            if path_contains in hit.url:
                return hit, f"by_path:{path_contains}"
        raise RuntimeError("No hit matched requested path substring")

    raise ValueError(f"Unknown selection strategy {strategy!r}")
