"""Reuse narrow candidate-link fields from already verified manifest streams.

The PostgreSQL manifest path consumes refinement, meet and demand descriptors once
for semantic persistence, then historically reopened each descriptor to obtain
only ``candidate_set_refs``. Verification of the first complete pass is already
an exact persistence precondition. Cache only the tiny link projection while that
pass is consumed, and serve the later link writer without rereading rich rows.

For the same-process immutable reader, a matching producer descriptor seal also
permits direct family iteration. This avoids constructing and discarding the
manifest record envelope for every persisted row. Any unsealed/reloaded reader
falls back to the canonical verified descriptor iterator.
"""

from __future__ import annotations

from itertools import islice
from typing import Any, Iterator, Mapping

from src.storage.postgres.sealed_manifest_family import direct_sealed_descriptor_family
from src.storage.postgres.work_conserving_stage import _runtime


_LINK_ID_FIELDS = ("refinement_ref", "meet_ref", "demand_ref")


def _batches(
    rows: tuple[Mapping[str, Any], ...], size: int = 256
) -> Iterator[tuple[Mapping[str, Any], ...]]:
    iterator = iter(rows)
    while batch := tuple(islice(iterator, size)):
        yield batch


def install_verified_candidate_link_cache(compiler: Any) -> tuple[Any, Any]:
    """Install a document-runtime-local narrow replay cache.

    Returns ``(original, replacement)`` so the activation context can restore the
    compiler module exactly. A cache entry is published only after the source
    iterator reaches EOF; interrupted/failed reads are never reused.
    """

    original = compiler._iter_descriptor_family

    def cached_iter_descriptor_family(
        reader: Any,
        descriptor: Mapping[str, Any],
        family: str,
    ) -> Iterator[tuple[Mapping[str, Any], ...]]:
        runtime = _runtime()
        artifact_key = str(descriptor.get("artifact_key") or "")
        cache_key = (artifact_key, family)
        cache = getattr(runtime, "_verified_candidate_link_cache", None)
        if cache is None:
            cache = {}
            setattr(runtime, "_verified_candidate_link_cache", cache)
        if cache_key in cache:
            yield from _batches(cache[cache_key])
            return

        direct = direct_sealed_descriptor_family(reader, descriptor, family)
        source = direct if direct is not None else original(reader, descriptor, family)
        narrow: list[Mapping[str, Any]] = []
        for rows in source:
            for row in rows:
                candidate_set_refs = tuple(
                    str(value) for value in row.get("candidate_set_refs") or ()
                )
                if not candidate_set_refs:
                    continue
                identity_field = next(
                    (field for field in _LINK_ID_FIELDS if row.get(field) is not None),
                    None,
                )
                if identity_field is None:
                    continue
                narrow.append(
                    {
                        identity_field: str(row[identity_field]),
                        "candidate_set_refs": candidate_set_refs,
                    }
                )
            yield rows

        # EOF is the publication point. For an unsealed reader it proves the
        # canonical verifier reached EOF; for the same-process direct path it
        # proves the producer-sealed immutable family was fully consumed.
        cache[cache_key] = tuple(narrow)
        setattr(
            runtime,
            "verified_candidate_link_rows_cached",
            int(getattr(runtime, "verified_candidate_link_rows_cached", 0))
            + len(narrow),
        )

    compiler._iter_descriptor_family = cached_iter_descriptor_family
    return original, cached_iter_descriptor_family


__all__ = ["install_verified_candidate_link_cache"]
