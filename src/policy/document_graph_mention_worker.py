"""Process worker for complete mention-licensing observation coverage."""

from __future__ import annotations

import os
from time import time_ns
from typing import Any, Mapping

from src.policy import entity_resolution as legacy


def scan_mention_partition(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Emit additive mention proposals from canonical and parser carriers.

    Canonical tokens drive lexical admission and suppression.  Every parser token
    in the owned sentences independently contributes numeric/eventuality evidence,
    including parser spans that do not exactly match one canonical token.
    """

    started_ns = time_ns()
    proposed: list[tuple[int, int, str, tuple[str, ...], tuple[str, ...]]] = []
    suppressed: list[tuple[int, int, str]] = []

    for row in payload["tokens"]:
        token_index = int(row["token_index"])
        token = str(row["token"])
        start_char = int(row["start_char"])
        end_char = int(row["end_char"])
        annotation = row.get("annotation")
        normalized = token.strip().lower()
        if not legacy._is_lexical_token(token):
            suppressed.append((token_index, token_index + 1, "punctuation_or_symbol"))
            continue
        if normalized in legacy._STRUCTURAL_LEXEMES:
            suppressed.append((token_index, token_index + 1, "structural_lexeme"))
            continue
        proposed.append(
            (
                start_char,
                end_char,
                "lexical_token",
                legacy._lexical_expected_kinds(annotation),
                legacy._local_types(annotation),
            )
        )

    for sentence in payload["sentences"]:
        run: list[Mapping[str, Any]] = []
        for token in sentence.get("tokens") or ():
            start_char = int(token["start"])
            end_char = int(token["end"])
            pos = str(token.get("pos") or "")
            if pos == "NUM":
                proposed.append(
                    (
                        start_char,
                        end_char,
                        "numeric_literal",
                        ("event_type", "literal"),
                        ("numeric_expression",),
                    )
                )
            if pos in {"VERB", "AUX"}:
                proposed.append(
                    (
                        start_char,
                        end_char,
                        "eventuality_annotation",
                        ("event_type", "property"),
                        ("linguistic_eventuality",),
                    )
                )
            if pos == "PROPN":
                run.append(token)
                continue
            if run:
                proposed.append(
                    (
                        int(run[0]["start"]),
                        int(run[-1]["end"]),
                        "named_entity_shape",
                        ("document_local", "instance"),
                        ("proper_name_phrase",),
                    )
                )
                run = []
        if run:
            proposed.append(
                (
                    int(run[0]["start"]),
                    int(run[-1]["end"]),
                    "named_entity_shape",
                    ("document_local", "instance"),
                    ("proper_name_phrase",),
                )
            )

    ended_ns = time_ns()
    return {
        "sequence_no": int(payload["sequence_no"]),
        "start_token": int(payload["start_token"]),
        "end_token": int(payload["end_token"]),
        "proposed": proposed,
        "suppressed": suppressed,
        "worker_pid": os.getpid(),
        "started_ns": started_ns,
        "ended_ns": ended_ns,
        "compute_ms": max(0, (ended_ns - started_ns) // 1_000_000),
    }


__all__ = ["scan_mention_partition"]
