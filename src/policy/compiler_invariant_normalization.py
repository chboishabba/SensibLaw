"""Recoverable normalization at compiler carrier boundaries.

The compiler remains strict about canonical coordinates and unique references, but a
single parser-token mismatch or duplicate proposal must not abort an otherwise valid
legal document after expensive parsing.  Recoverable rows are normalized or rejected
with explicit diagnostics before persistence.  Nothing here resolves identity,
promotes a factor, or closes legal truth.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_json, canonical_sha256
from src.sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans


NORMALIZATION_CONTRACT = "compiler-invariant-normalization:v0_1"


def normalize_licensed_mentions(
    *, canonical_text: str, mentions: Sequence[Mapping[str, Any]]
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Return token-aligned mentions and explicit rejected-span diagnostics.

    Character coordinates remain authoritative.  Token indices are recomputed from the
    canonical tokenizer only when both character boundaries coincide exactly with token
    boundaries.  Non-aligned parser proposals are retained as diagnostics rather than
    snapped to wider text or allowed to fail the whole document during persistence.
    """

    tokens = tuple(tokenize_canonical_with_spans(canonical_text))
    start_index = {start: index for index, (_token, start, _end) in enumerate(tokens)}
    end_index = {end: index + 1 for index, (_token, _start, end) in enumerate(tokens)}
    accepted: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []

    for raw in mentions:
        row = dict(raw)
        mention_ref = str(row.get("mention_ref") or "")
        start = int(row.get("start_char", -1))
        end = int(row.get("end_char", -1))
        reason: str | None = None
        if not (0 <= start < end <= len(canonical_text)):
            reason = "character_range_outside_canonical_text"
        elif canonical_text[start:end] != str(row.get("canonical_surface") or ""):
            reason = "surface_disagrees_with_canonical_text"
        elif start not in start_index or end not in end_index:
            reason = "character_boundary_not_token_aligned"

        if reason is not None:
            rejected.append(
                {
                    "diagnostic_ref": "compiler-diagnostic:"
                    + canonical_sha256(
                        {
                            "contract": NORMALIZATION_CONTRACT,
                            "mention_ref": mention_ref,
                            "reason": reason,
                            "start_char": start,
                            "end_char": end,
                        }
                    ),
                    "mention_ref": mention_ref,
                    "reason": reason,
                    "start_char": start,
                    "end_char": end,
                    "authority": "diagnostic_only",
                }
            )
            continue

        row["start_token"] = start_index[start]
        row["end_token"] = end_index[end]
        accepted[mention_ref] = row

    return (
        tuple(accepted[key] for key in sorted(accepted)),
        tuple(sorted(rejected, key=lambda item: item["diagnostic_ref"])),
    )


def deduplicate_structural_hypotheses(
    hypotheses: Sequence[Mapping[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Deduplicate exact local-typing proposals without asserting equivalence.

    Only byte-equivalent canonical proposal rows are collapsed.  Distinct evidence,
    derivation, type, or mention coordinates remain distinct alternatives.
    """

    by_digest: dict[str, dict[str, Any]] = {}
    duplicate_counts: dict[str, int] = {}
    for raw in hypotheses:
        row = dict(raw)
        digest = canonical_sha256(canonical_json(row))
        if digest in by_digest:
            duplicate_counts[digest] = duplicate_counts.get(digest, 1) + 1
        else:
            by_digest[digest] = row

    diagnostics = tuple(
        {
            "diagnostic_ref": "compiler-diagnostic:"
            + canonical_sha256(
                {
                    "contract": NORMALIZATION_CONTRACT,
                    "proposal_digest": digest,
                    "duplicate_count": count,
                }
            ),
            "reason": "exact_duplicate_structural_hypothesis",
            "proposal_digest": digest,
            "duplicate_count": count,
            "authority": "diagnostic_only",
        }
        for digest, count in sorted(duplicate_counts.items())
    )
    return tuple(by_digest[key] for key in sorted(by_digest)), diagnostics


__all__ = [
    "NORMALIZATION_CONTRACT",
    "deduplicate_structural_hypotheses",
    "normalize_licensed_mentions",
]
