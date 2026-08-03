"""Indexed execution strategy for canonical semantic annotation projection.

The canonical projection semantics remain in ``corpus_compilation``.  This strategy
preserves the same output contract while replacing the per-atom linear parser-token
scan with one immutable span index.  It also emits diagnostics at the existing
4,096-item boundary so local complexity can be measured without nested stages.
"""

from __future__ import annotations

from bisect import bisect_left
import gc
import os
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.language import (
    AnnotationLayer,
    RelationAnnotation,
    SpanAnnotation,
    TokenAnnotation,
)
from src.policy.carriers.canonical import canonical_sha256
from src.sensiblaw.interfaces.shared_reducer import collect_canonical_relational_bundle

from .bounded_operational_execution import current_process_tree_rss_bytes


_INSTALL_MARKER = "_indexed_projection_execution_installed"


def indexed_semantic_annotation_layer(
    *,
    document_ref: str,
    source_ref: str,
    content_sha256: str,
    tokens: Sequence[tuple[str, int, int]],
    base_layer: AnnotationLayer,
    text: str,
    parsed_document: Mapping[str, Any],
    progress_observer: Callable[[Mapping[str, int]], None] | None = None,
) -> tuple[AnnotationLayer, Mapping[str, Any], dict[str, str]]:
    """Project parser observations using O(1)-expected exact-span token lookup."""

    def observe_bundle_progress(_event: str, payload: Mapping[str, Any]) -> None:
        if progress_observer is None:
            return
        progress_observer(
            {
                "bundle_batches_completed": int(payload.get("batch_index", 0)),
                "bundle_sentences_scanned": int(payload.get("sentences_done", 0)),
                "bundle_words_scanned": int(payload.get("words_done", 0)),
                "bundle_tokens_scanned": int(payload.get("tokens_done", 0)),
                "semantic_atoms_projected": int(payload.get("atom_count", 0)),
                "semantic_relations_projected": int(payload.get("relation_count", 0)),
            }
        )

    bundle = collect_canonical_relational_bundle(
        text,
        parsed_document=parsed_document,
        progress_callback=observe_bundle_progress,
    )
    semantic_atoms = tuple(bundle.get("atoms") or ())
    semantic_relations = tuple(bundle.get("relations") or ())
    parser_receipt = dict(parsed_document.get("parser_receipt") or {})
    parser_tokens = tuple(
        token
        for sentence in parsed_document.get("sents") or ()
        for token in sentence.get("tokens") or ()
    )
    parser_tokens_by_span = {
        (int(token["start"]), int(token["end"])): token for token in parser_tokens
    }
    token_indexes_by_span = {
        (start_char, end_char): index
        for index, (_token, start_char, end_char) in enumerate(tokens)
    }
    token_starts = [start_char for _token, start_char, _end_char in tokens]
    token_ends = [end_char for _token, _start_char, end_char in tokens]
    parser_token_total = len(parser_tokens)
    sentence_total = len(parsed_document.get("sents") or ())
    progress_counts = {
        "parser_tokens_projected": 0,
        "sentences_projected": 0,
        "observations_emitted": 0,
        "deltas_emitted": 0,
        "relations_projected": 0,
        "semantic_atoms_projected": 0,
        "semantic_relations_projected": 0,
        "token_coverage_lookups": 0,
        "lookup_operations": 0,
        "batch_elapsed_ms": 0,
        "process_tree_rss_bytes": 0,
        "gc_collection_counts": 0,
        "retained_object_counts": 0,
        "last_batch_size": 0,
    }
    batch_started = monotonic_ns()
    prior_atom_count = 0

    def gc_collection_count() -> int:
        return sum(int(row.get("collections", 0)) for row in gc.get_stats())

    def observe_progress(**updates: int) -> None:
        if progress_observer is None:
            return
        progress_counts.update(updates)
        progress_observer(dict(progress_counts))

    def covered_token_indexes(start_char: int, end_char: int) -> list[int]:
        """Return overlapping canonical tokens without rescanning the document."""

        first = bisect_left(token_ends, start_char + 1)
        last = bisect_left(token_starts, end_char)
        return [
            index
            for index in range(first, last)
            if token_starts[index] < end_char and token_ends[index] > start_char
        ]

    parser_span_refs: dict[int, str] = {}
    token_annotations: list[TokenAnnotation] = []
    parser_spans: list[SpanAnnotation] = []
    parser_relations: list[RelationAnnotation] = []
    for sentence_index, sentence in enumerate(parsed_document.get("sents") or ()):
        for token in sentence.get("tokens") or ():
            parser_index = int(token["index"])
            start_char, end_char = int(token["start"]), int(token["end"])
            canonical_index = token_indexes_by_span.get((start_char, end_char))
            if canonical_index is None:
                progress_counts["token_coverage_lookups"] += 1
                progress_counts["lookup_operations"] += 1
                overlapping = covered_token_indexes(start_char, end_char)
                if len(overlapping) == 1:
                    canonical_index = overlapping[0]
            if canonical_index is None:
                continue
            span_ref = "parser-token:" + canonical_sha256(
                {
                    "document_ref": document_ref,
                    "parser_index": parser_index,
                    "start": start_char,
                    "end": end_char,
                }
            )
            parser_span_refs[parser_index] = span_ref
            parser_spans.append(
                SpanAnnotation(
                    span_ref=span_ref,
                    start_token=canonical_index,
                    end_token=canonical_index + 1,
                    annotation_type="parser_token",
                    value={"start_char": start_char, "end_char": end_char},
                    provenance_refs=(source_ref,),
                )
            )
            for annotation_type, value in (
                ("parser.surface", token.get("text")),
                ("parser.lemma", token.get("lemma")),
                ("parser.pos", token.get("pos")),
                ("parser.tag", token.get("tag")),
                ("parser.morphology", token.get("morph") or {}),
                ("parser.dependency", token.get("dep")),
                ("parser.sentence", sentence_index),
            ):
                token_annotations.append(
                    TokenAnnotation(
                        canonical_index,
                        annotation_type,
                        value,
                        (source_ref,),
                    )
                )
            progress_counts["parser_tokens_projected"] += 1
        progress_counts["sentences_projected"] = sentence_index + 1
        if (progress_counts["parser_tokens_projected"] % 4096 == 0) or (
            progress_counts["sentences_projected"] == sentence_total
        ):
            observe_progress()

    for token in parser_tokens:
        parser_index = int(token["index"])
        head_index = int(token.get("head_index", parser_index))
        left_ref = parser_span_refs.get(parser_index)
        right_ref = parser_span_refs.get(head_index)
        if left_ref is None or right_ref is None:
            continue
        parser_relations.append(
            RelationAnnotation(
                relation_ref="parser-dependency:"
                + canonical_sha256(
                    {
                        "document_ref": document_ref,
                        "token": parser_index,
                        "head": head_index,
                        "dependency": token.get("dep"),
                    }
                ),
                relation_type="parser.dependency_head",
                left_ref=left_ref,
                right_ref=right_ref,
                payload={"dependency": token.get("dep"), "head_index": head_index},
                provenance_refs=(source_ref,),
            )
        )
        progress_counts["relations_projected"] += 1
        if progress_counts["relations_projected"] % 4096 == 0:
            observe_progress()

    parser_relations.append(
        RelationAnnotation(
            relation_ref="parser-capabilities:"
            + canonical_sha256(
                {"document_ref": document_ref, "receipt": parser_receipt}
            ),
            relation_type="parser.capability_receipt",
            left_ref="document:" + document_ref,
            right_ref="document:" + document_ref,
            payload=parser_receipt,
            provenance_refs=(source_ref,),
        )
    )

    atom_span_refs: dict[str, str] = {}
    spans: list[SpanAnnotation] = []
    for atom_index, atom in enumerate(semantic_atoms, start=1):
        start_char, end_char = (int(value) for value in atom["span"])
        progress_counts["token_coverage_lookups"] += 1
        progress_counts["lookup_operations"] += 1
        covered = covered_token_indexes(start_char, end_char)
        if not covered:
            continue
        atom_ref = str(atom["id"])
        span_ref = "semantic-atom:" + canonical_sha256(
            {"document_ref": document_ref, "atom": atom}
        )
        atom_span_refs[atom_ref] = span_ref
        parser_token = parser_tokens_by_span.get((start_char, end_char), {})
        spans.append(
            SpanAnnotation(
                span_ref=span_ref,
                start_token=min(covered),
                end_token=max(covered) + 1,
                annotation_type="semantic_atom",
                value={
                    "text": atom.get("text"),
                    "lemma": atom.get("lemma"),
                    "pos": parser_token.get("pos"),
                    "morph": parser_token.get("morph") or atom.get("morph"),
                    "dependency": parser_token.get("dep"),
                    "head_index": parser_token.get("head_index"),
                },
                provenance_refs=(source_ref,),
            )
        )
        progress_counts["semantic_atoms_projected"] = atom_index
        if atom_index % 4096 == 0:
            now = monotonic_ns()
            observe_progress(
                batch_elapsed_ms=max(0, (now - batch_started) // 1_000_000),
                process_tree_rss_bytes=current_process_tree_rss_bytes(),
                gc_collection_counts=gc_collection_count(),
                retained_object_counts=(
                    len(spans) + len(atom_span_refs) + len(parser_tokens_by_span)
                ),
                last_batch_size=atom_index - prior_atom_count,
            )
            batch_started = now
            prior_atom_count = atom_index

    relations: list[RelationAnnotation] = []
    for relation_index, relation in enumerate(semantic_relations, start=1):
        relation_ref = "semantic-relation:" + canonical_sha256(
            {"document_ref": document_ref, "relation": relation}
        )
        atom_refs = [
            atom_span_refs.get(str(row.get("atom") or ""))
            for row in relation.get("roles") or ()
        ]
        linked = [item for item in atom_refs if item]
        if linked:
            left_ref, right_ref = linked[0], linked[-1]
        else:
            left_ref = right_ref = "document:" + document_ref
        relations.append(
            RelationAnnotation(
                relation_ref=relation_ref,
                relation_type="semantic." + str(relation.get("type") or "unknown"),
                left_ref=left_ref,
                right_ref=right_ref,
                payload={"roles": tuple(relation.get("roles") or ())},
                provenance_refs=(source_ref,),
            )
        )
        progress_counts["semantic_relations_projected"] = relation_index
        if relation_index % 4096 == 0:
            observe_progress()

    observe_progress(
        parser_tokens_projected=parser_token_total,
        sentences_projected=sentence_total,
        relations_projected=len(parser_relations),
        semantic_atoms_projected=len(semantic_atoms),
        semantic_relations_projected=len(semantic_relations),
        retained_object_counts=(
            len(spans) + len(atom_span_refs) + len(parser_tokens_by_span)
        ),
    )
    layer = AnnotationLayer(
        layer_ref="annotation-layer:semantic:"
        + canonical_sha256({"base": base_layer.layer_ref, "bundle": bundle}),
        tokenizer_ref="annotation:public-parser-observations:v0_1",
        text_sha256=content_sha256,
        token_annotations=tuple(token_annotations),
        span_annotations=tuple(parser_spans + spans),
        relation_annotations=tuple(parser_relations + relations),
        provenance_refs=(source_ref, base_layer.layer_ref),
    )
    return layer, bundle, atom_span_refs


def install_indexed_projection_execution() -> None:
    """Install the indexed strategy while retaining the serial parity surface."""

    from src.policy import corpus_compilation as legacy

    if getattr(legacy, _INSTALL_MARKER, False):
        return
    if not hasattr(legacy, "_serial_semantic_annotation_layer"):
        legacy._serial_semantic_annotation_layer = legacy._semantic_annotation_layer
    legacy._semantic_annotation_layer = indexed_semantic_annotation_layer
    setattr(legacy, _INSTALL_MARKER, True)


def indexed_projection_enabled() -> bool:
    value = os.environ.get("SENSIBLAW_INDEXED_SEMANTIC_PROJECTION", "1")
    return value.strip().lower() not in {"0", "false", "no", "off"}


__all__ = [
    "indexed_projection_enabled",
    "indexed_semantic_annotation_layer",
    "install_indexed_projection_execution",
]
