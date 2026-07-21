"""Deterministic local-only corpus compilation orchestration.

The directory is not a semantic source type.  This module inventories media,
invokes one shared document compiler, persists immutable projections, and
groups unresolved demands.  It deliberately does not perform registry I/O,
cross-document identity closure, readiness promotion, or corpus-specific
interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import mimetypes
import os
import tempfile
from typing import Any, Iterable, Mapping, Protocol, Sequence

from src.ingestion.media_adapter_contract import MediaAdapterCapability
from src.ingestion.media_adapter import HtmlDocumentMediaAdapter
from src.language import (
    AnnotationGraph,
    AnnotationLayer,
    RelationAnnotation,
    SpanAnnotation,
    TokenAnnotation,
    diagnose_untyped_mentions,
    default_semantic_reduction_declarations,
    derive_relational_type_hypotheses,
    reduce_relational_bundle,
    summarize_untyped_diagnostics,
)
from src.pnf import PNFGraph, derive_resolution_demands
from src.policy.algebra import (
    ConstraintAssessment,
    Factor,
    FactorConstraint,
    FactorRefinement,
    MeetState,
    ResidualTransition,
    TypedAlternative,
    TypedMeet,
)
from src.policy.carriers.canonical import (
    canonical_json,
    canonical_refs,
    canonical_sha256,
    require_text,
)
from src.policy.entity_resolution import (
    build_form_derivation_carrier,
    build_local_typing_carrier,
    build_mention_licensing_carrier,
    build_mention_recurrence_carrier,
)
from src.sensiblaw.interfaces.shared_reducer import (
    collect_canonical_relational_bundle,
    tokenize_canonical_with_spans,
)
from src.sensiblaw.interfaces import parse_canonical_text


CORPUS_MANIFEST_SCHEMA_VERSION = "sl.corpus_manifest.v0_1"
DOCUMENT_COMPILATION_SCHEMA_VERSION = "sl.document_compilation.v0_1"
LOCAL_EVIDENCE_SCHEMA_VERSION = "sl.local_evidence.v0_1"

_TEXT_MEDIA_TYPES = {"text/plain", "text/markdown", "text/html"}
_TEXT_SUFFIXES = {
    ".htm": "text/html",
    ".html": "text/html",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".text": "text/plain",
}


class CompilationArtifactStore(Protocol):
    """Optional persistence boundary; the compiler remains storage-neutral."""

    def load_completed(
        self, *, document_ref: str, build_key_sha256: str
    ) -> Mapping[str, Any] | None: ...

    def persist(
        self,
        *,
        compilation: Mapping[str, Any],
        context: Mapping[str, Any],
        build_key_sha256: str,
    ) -> None: ...


@dataclass(frozen=True)
class CompilerContext:
    """Declared generic compiler capabilities, never a corpus/profile selector."""

    context_ref: str
    compiler_version: str
    media_normalization_ref: str
    media_capabilities: tuple[MediaAdapterCapability, ...] = (
        MediaAdapterCapability("media:utf8-text:v0_1", ("text/plain", "text/markdown")),
        MediaAdapterCapability("media:html:v0_1", ("text/html",)),
    )
    annotation_backend_ref: str = "annotation:public-parser:v0_1"
    reduction_grammar_refs: tuple[str, ...] = ()
    type_system_refs: tuple[str, ...] = ()
    relation_algebra_refs: tuple[str, ...] = ()
    external_registry_capability_refs: tuple[str, ...] = ()
    closure_policy_ref: str = "closure:local-only:v0_1"
    readiness_policy_ref: str = "readiness:not-invoked:v0_1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "sl.compiler_context.v0_1",
            "context_ref": require_text(self.context_ref, "context_ref"),
            "compiler_version": require_text(self.compiler_version, "compiler_version"),
            "media_normalization_ref": require_text(
                self.media_normalization_ref, "media_normalization_ref"
            ),
            "media_capabilities": [
                row.to_dict()
                for row in sorted(
                    self.media_capabilities, key=lambda value: value.adapter_ref
                )
            ],
            "annotation_backend_ref": require_text(
                self.annotation_backend_ref, "annotation_backend_ref"
            ),
            "reduction_grammar_refs": list(canonical_refs(self.reduction_grammar_refs)),
            "type_system_refs": list(canonical_refs(self.type_system_refs)),
            "relation_algebra_refs": list(canonical_refs(self.relation_algebra_refs)),
            "external_registry_capability_refs": list(
                canonical_refs(self.external_registry_capability_refs)
            ),
            "closure_policy_ref": require_text(
                self.closure_policy_ref, "closure_policy_ref"
            ),
            "readiness_policy_ref": require_text(
                self.readiness_policy_ref, "readiness_policy_ref"
            ),
            "authority": "configuration_only",
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CompilerContext":
        capabilities = tuple(
            MediaAdapterCapability(
                adapter_ref=str(row["adapter_ref"]),
                media_types=tuple(str(item) for item in row.get("media_types") or ()),
                produces=tuple(str(item) for item in row.get("produces") or ()),
            )
            for row in value.get("media_capabilities") or ()
        )
        return cls(
            context_ref=str(value["context_ref"]),
            compiler_version=str(value["compiler_version"]),
            media_normalization_ref=str(value["media_normalization_ref"]),
            media_capabilities=capabilities
            or cls.__dataclass_fields__["media_capabilities"].default,
            annotation_backend_ref=str(
                value.get("annotation_backend_ref") or "annotation:public-parser:v0_1"
            ),
            reduction_grammar_refs=tuple(value.get("reduction_grammar_refs") or ()),
            type_system_refs=tuple(value.get("type_system_refs") or ()),
            relation_algebra_refs=tuple(value.get("relation_algebra_refs") or ()),
            external_registry_capability_refs=tuple(
                value.get("external_registry_capability_refs") or ()
            ),
            closure_policy_ref=str(
                value.get("closure_policy_ref") or "closure:local-only:v0_1"
            ),
            readiness_policy_ref=str(
                value.get("readiness_policy_ref") or "readiness:not-invoked:v0_1"
            ),
        )


def default_compiler_context() -> CompilerContext:
    """Return the explicit default local-only declaration bundle."""

    return CompilerContext(
        context_ref="compiler-context:local-only:v0_1",
        compiler_version="directory-kernel:v0_1",
        media_normalization_ref="media-normalization:utf8:v0_1",
    )


@dataclass(frozen=True)
class DocumentManifestEntry:
    document_ref: str
    relative_path: str
    media_type: str
    content_sha256: str
    byte_size: int
    adapter_capability_ref: str | None
    status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "document_ref": require_text(self.document_ref, "document_ref"),
            "relative_path": require_text(self.relative_path, "relative_path"),
            "media_type": require_text(self.media_type, "media_type"),
            "content_sha256": require_text(self.content_sha256, "content_sha256"),
            "byte_size": self.byte_size,
            "status": require_text(self.status, "status"),
        }
        if self.byte_size < 0:
            raise ValueError("byte_size must be non-negative")
        if self.adapter_capability_ref:
            row["adapter_capability_ref"] = require_text(
                self.adapter_capability_ref, "adapter_capability_ref"
            )
        if self.reason:
            row["reason"] = require_text(self.reason, "reason")
        return row


@dataclass(frozen=True)
class CorpusManifest:
    corpus_ref: str
    root_ref: str
    compiler_context_ref: str
    documents: tuple[DocumentManifestEntry, ...]
    ignored_entries: tuple[Mapping[str, Any], ...] = ()
    unsupported_entries: tuple[Mapping[str, Any], ...] = ()
    inventory_failures: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        row = {
            "schema_version": CORPUS_MANIFEST_SCHEMA_VERSION,
            "corpus_ref": require_text(self.corpus_ref, "corpus_ref"),
            "root_ref": require_text(self.root_ref, "root_ref"),
            "compiler_context_ref": require_text(
                self.compiler_context_ref, "compiler_context_ref"
            ),
            "ordered_documents": [
                item.to_dict()
                for item in sorted(
                    self.documents, key=lambda value: value.relative_path
                )
            ],
            "ignored_entries": canonical_json(list(self.ignored_entries)),
            "unsupported_entries": canonical_json(list(self.unsupported_entries)),
            "inventory_failures": canonical_json(list(self.inventory_failures)),
            "authority": "inventory_only",
        }
        row["manifest_sha256"] = canonical_sha256(row)
        return row


@dataclass(frozen=True)
class LocalEvidence:
    """Document-bounded evidence projection that cannot resolve identity."""

    evidence_ref: str
    document_ref: str
    evidence_type: str
    subject_refs: tuple[str, ...]
    relation: str
    payload: Mapping[str, Any]
    derivation_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        row = {
            "schema_version": LOCAL_EVIDENCE_SCHEMA_VERSION,
            "evidence_ref": require_text(self.evidence_ref, "evidence_ref"),
            "document_ref": require_text(self.document_ref, "document_ref"),
            "evidence_type": require_text(self.evidence_type, "evidence_type"),
            "subject_refs": list(canonical_refs(self.subject_refs)),
            "relation": require_text(self.relation, "relation"),
            "payload": canonical_json(dict(self.payload)),
            "derivation_refs": list(canonical_refs(self.derivation_refs)),
            "provenance_refs": list(canonical_refs(self.provenance_refs)),
            "authority": "evidence_only",
        }
        if not row["subject_refs"] or not row["provenance_refs"]:
            raise ValueError("local evidence requires subjects and provenance")
        return row


@dataclass(frozen=True)
class DocumentCompilation:
    document_ref: str
    content_sha256: str
    media_type: str
    artifacts: Mapping[str, Any]
    status: str = "compiled"
    failure: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "schema_version": DOCUMENT_COMPILATION_SCHEMA_VERSION,
            "document_ref": require_text(self.document_ref, "document_ref"),
            "content_sha256": require_text(self.content_sha256, "content_sha256"),
            "media_type": require_text(self.media_type, "media_type"),
            "status": require_text(self.status, "status"),
            "artifacts": canonical_json(dict(self.artifacts)),
            "authority": "candidate_only",
        }
        if self.failure:
            row["failure"] = canonical_json(dict(self.failure))
        row["compilation_sha256"] = canonical_sha256(row)
        return row


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _media_type(path: Path) -> str:
    suffix_type = _TEXT_SUFFIXES.get(path.suffix.casefold())
    if suffix_type:
        return suffix_type
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _adapter_for(media_type: str, context: CompilerContext) -> str | None:
    for capability in sorted(
        context.media_capabilities, key=lambda value: value.adapter_ref
    ):
        if media_type in set(capability.media_types):
            return capability.adapter_ref
    return None


def _document_ref(
    content_sha256: str, media_type: str, context: CompilerContext
) -> str:
    return "document:" + canonical_sha256(
        {
            "content_sha256": content_sha256,
            "media_type": media_type,
            "media_normalization_ref": context.media_normalization_ref,
        }
    )


def _safe_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def build_corpus_manifest(
    input_dir: str | Path,
    *,
    context: CompilerContext,
    recursive: bool = True,
    follow_symlinks: bool = False,
    include_globs: Sequence[str] = (),
    exclude_globs: Sequence[str] = (),
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
    excluded_roots: Sequence[str | Path] = (),
) -> CorpusManifest:
    """Inventory bounded input without parsing or silently dropping entries."""

    root = Path(input_dir).resolve()
    if not root.is_dir():
        raise ValueError("input_dir must be an existing directory")
    if max_files is not None and max_files < 1:
        raise ValueError("max_files must be positive")
    if max_file_bytes is not None and max_file_bytes < 1:
        raise ValueError("max_file_bytes must be positive")
    if max_total_bytes is not None and max_total_bytes < 1:
        raise ValueError("max_total_bytes must be positive")
    excluded = tuple(Path(item).resolve() for item in excluded_roots)
    documents: list[DocumentManifestEntry] = []
    ignored: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    total_bytes = 0
    iterator: Iterable[Path] = root.rglob("*") if recursive else root.iterdir()
    for path in sorted(iterator, key=lambda item: item.as_posix()):
        try:
            relative_path = _safe_relative(path, root)
        except ValueError:
            continue
        if any(
            path == excluded_root or excluded_root in path.parents
            for excluded_root in excluded
        ):
            ignored.append(
                {"relative_path": relative_path, "reason": "excluded_output_or_cache"}
            )
            continue
        if path.is_symlink() and not follow_symlinks:
            ignored.append(
                {"relative_path": relative_path, "reason": "symlink_not_followed"}
            )
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            ignored.append(
                {"relative_path": relative_path, "reason": "non_regular_entry"}
            )
            continue
        if exclude_globs and any(path.match(pattern) for pattern in exclude_globs):
            ignored.append({"relative_path": relative_path, "reason": "excluded_glob"})
            continue
        if include_globs and not any(path.match(pattern) for pattern in include_globs):
            ignored.append(
                {"relative_path": relative_path, "reason": "not_included_glob"}
            )
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(
                {
                    "relative_path": relative_path,
                    "reason": "read_failed",
                    "detail": str(error),
                }
            )
            continue
        if max_files is not None and len(documents) >= max_files:
            ignored.append(
                {"relative_path": relative_path, "reason": "max_files_exceeded"}
            )
            continue
        if max_file_bytes is not None and len(payload) > max_file_bytes:
            ignored.append(
                {"relative_path": relative_path, "reason": "max_file_bytes_exceeded"}
            )
            continue
        if max_total_bytes is not None and total_bytes + len(payload) > max_total_bytes:
            ignored.append(
                {"relative_path": relative_path, "reason": "max_total_bytes_exceeded"}
            )
            continue
        media_type = _media_type(path)
        content_sha256 = _sha256(payload)
        document_ref = _document_ref(content_sha256, media_type, context)
        adapter_ref = _adapter_for(media_type, context)
        entry = DocumentManifestEntry(
            document_ref=document_ref,
            relative_path=relative_path,
            media_type=media_type,
            content_sha256=content_sha256,
            byte_size=len(payload),
            adapter_capability_ref=adapter_ref,
            status="inventoried" if adapter_ref else "unsupported_media",
            reason=None if adapter_ref else "no_declared_media_capability",
        )
        documents.append(entry)
        total_bytes += len(payload)
        if not adapter_ref:
            unsupported.append(entry.to_dict())
    root_ref = "corpus-root:" + canonical_sha256(
        {"root": root.name, "context": context.to_dict()}
    )
    identity = {
        "root_ref": root_ref,
        "context": context.to_dict(),
        "documents": [item.to_dict() for item in documents],
        "ignored": ignored,
        "unsupported": unsupported,
        "failures": failures,
    }
    return CorpusManifest(
        corpus_ref="corpus:" + canonical_sha256(identity),
        root_ref=root_ref,
        compiler_context_ref=context.context_ref,
        documents=tuple(documents),
        ignored_entries=tuple(ignored),
        unsupported_entries=tuple(unsupported),
        inventory_failures=tuple(failures),
    )


def _local_evidence(
    *, document_ref: str, recurrence: Mapping[str, Any], local_typing: Mapping[str, Any]
) -> tuple[LocalEvidence, ...]:
    evidence: list[LocalEvidence] = []
    for group in recurrence.get("recurrence_groups") or ():
        members = tuple(group.get("member_mention_refs") or ())
        payload = {"normalized_surface": group.get("normalized_surface")}
        identity = {
            "document_ref": document_ref,
            "kind": "form_recurrence",
            "members": members,
            "payload": payload,
        }
        evidence.append(
            LocalEvidence(
                evidence_ref="local-evidence:" + canonical_sha256(identity),
                document_ref=document_ref,
                evidence_type="form_recurrence",
                subject_refs=members,
                relation="same_surface_within_document",
                payload=payload,
                derivation_refs=(str(group["group_ref"]),),
                provenance_refs=(f"document:{document_ref}",),
            )
        )
    for alternative in local_typing.get("local_type_alternatives") or ():
        mention_ref = str(alternative["mention_ref"])
        identity = {
            "document_ref": document_ref,
            "kind": "local_type",
            "type_ref": alternative["type_ref"],
        }
        evidence.append(
            LocalEvidence(
                evidence_ref="local-evidence:" + canonical_sha256(identity),
                document_ref=document_ref,
                evidence_type="local_type",
                subject_refs=(mention_ref,),
                relation="locally_typed_as",
                payload={
                    "semantic_family": alternative["semantic_family"],
                    "local_type": alternative["local_type"],
                },
                derivation_refs=(str(alternative["type_ref"]),),
                provenance_refs=tuple(
                    alternative.get("evidence_refs") or (f"document:{document_ref}",)
                ),
            )
        )
    return tuple(sorted(evidence, key=lambda item: item.evidence_ref))


def _span_context_by_ref(
    semantic_layer: AnnotationLayer,
) -> dict[str, Mapping[str, Any]]:
    """Return parser-observed position context keyed by graph span reference."""

    annotations = {
        (annotation.token_index, annotation.annotation_type): annotation.value
        for annotation in semantic_layer.token_annotations
    }
    contexts: dict[str, Mapping[str, Any]] = {}
    parser_spans = tuple(
        span
        for span in semantic_layer.span_annotations
        if span.annotation_type == "parser_token"
    )
    for span in parser_spans:
        index = span.start_token
        contexts[span.span_ref] = {
            "start_token": span.start_token,
            "end_token": span.end_token,
            "sentence_index": annotations.get((index, "parser.sentence")),
            "pos": annotations.get((index, "parser.pos")),
            "morphology": annotations.get((index, "parser.morphology")) or {},
        }
    for span in semantic_layer.span_annotations:
        if span.annotation_type != "semantic_atom":
            continue
        overlaps = [
            contexts[parser_span.span_ref]
            for parser_span in parser_spans
            if parser_span.span_ref in contexts
            and span.start_token < parser_span.end_token
            and span.end_token > parser_span.start_token
        ]
        if overlaps:
            contexts[span.span_ref] = min(
                overlaps, key=lambda row: int(row["start_token"])
            )
    return contexts


def _factor_position_context(
    factor: Factor[Any], span_context: Mapping[str, Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    """Find the observed anchor for a factor without interpreting its meaning."""

    span_refs: list[str] = []
    direct = factor.metadata.get("atom_span_ref")
    if isinstance(direct, str):
        span_refs.append(direct)
    for binding in factor.metadata.get("bindings") or ():
        if isinstance(binding, Mapping) and isinstance(binding.get("atom_ref"), str):
            span_refs.append(str(binding["atom_ref"]))
    observed = [span_context[ref] for ref in span_refs if ref in span_context]
    if not observed:
        return None
    return min(observed, key=lambda row: int(row["start_token"]))


def _binding_evidence(
    *,
    graph: PNFGraph,
    mentions: Sequence[Mapping[str, Any]],
    semantic_layer: AnnotationLayer,
    document_ref: str,
    source_ref: str,
) -> tuple[LocalEvidence, ...]:
    """Generate bounded, typed document-local reference candidates.

    This is candidate generation only.  Position, parser morphology and PNF
    factor kind bound the pool; they do not establish coreference or resolve an
    entity, occurrence, proposition, or truth value.
    """

    span_context = _span_context_by_ref(semantic_layer)
    mention_context: dict[str, Mapping[str, Any]] = {}
    parser_spans = tuple(
        span
        for span in semantic_layer.span_annotations
        if span.annotation_type == "parser_token"
    )
    for mention in mentions:
        matched = [
            span_context[span.span_ref]
            for span in parser_spans
            if span.span_ref in span_context
            and int(mention["start_token"]) < span.end_token
            and int(mention["end_token"]) > span.start_token
        ]
        if matched:
            mention_context[str(mention["mention_ref"])] = min(
                matched, key=lambda row: int(row["start_token"])
            )

    candidates: dict[str, list[tuple[str, Mapping[str, Any]]]] = {
        "entity_reference": [],
        "eventuality_reference": [],
        "proposition_reference": [],
    }
    for factor in graph.factors:
        context = _factor_position_context(factor, span_context)
        if factor.factor_type == "semantic.mention_identity":
            mention_ref = str(factor.metadata.get("mention_ref") or "")
            context = mention_context.get(mention_ref, context)
            if context and str(context.get("pos") or "") in {"NOUN", "PROPN"}:
                candidates["entity_reference"].append((factor.factor_ref, context))
        elif factor.factor_type == "semantic.eventuality" and context:
            candidates["eventuality_reference"].append((factor.factor_ref, context))
        elif factor.factor_type == "semantic.embedded_proposition" and context:
            candidates["proposition_reference"].append((factor.factor_ref, context))

    evidence: list[LocalEvidence] = []
    for reference_factor in graph.factors:
        if not any(
            alternative.type_ref == "semantic.reference_candidate"
            for alternative in reference_factor.alternatives
        ):
            continue
        reference_context = _factor_position_context(reference_factor, span_context)
        if reference_context is None:
            continue
        reference_start = int(reference_context["start_token"])
        reference_sentence = reference_context.get("sentence_index")
        allowed_types = {
            str(alternative.value.get("referential_type"))
            for alternative in reference_factor.alternatives
            if alternative.type_ref == "semantic.reference_candidate"
            and isinstance(alternative.value, Mapping)
        }
        for referential_type in sorted(allowed_types.intersection(candidates)):
            for candidate_ref, candidate_context in candidates[referential_type]:
                if candidate_ref == reference_factor.factor_ref:
                    continue
                candidate_start = int(candidate_context["start_token"])
                candidate_sentence = candidate_context.get("sentence_index")
                accessible = candidate_start < reference_start
                if (
                    accessible
                    and isinstance(reference_sentence, int)
                    and isinstance(candidate_sentence, int)
                ):
                    accessible = 0 <= reference_sentence - candidate_sentence <= 2
                relation = (
                    {
                        "entity_reference": "possible_coreference_with",
                        "eventuality_reference": "possible_eventuality_reference",
                        "proposition_reference": "possible_proposition_reference",
                    }[referential_type]
                    if accessible
                    else "binding_incompatible_with"
                )
                identity = {
                    "document_ref": document_ref,
                    "reference_factor_ref": reference_factor.factor_ref,
                    "candidate_factor_ref": candidate_ref,
                    "referential_type": referential_type,
                    "relation": relation,
                }
                evidence.append(
                    LocalEvidence(
                        evidence_ref="local-evidence:" + canonical_sha256(identity),
                        document_ref=document_ref,
                        evidence_type="typed_binding_candidate",
                        subject_refs=(reference_factor.factor_ref, candidate_ref),
                        relation=relation,
                        payload={
                            "referential_type": referential_type,
                            "reference_position": dict(reference_context),
                            "candidate_position": dict(candidate_context),
                        },
                        derivation_refs=("grammar:pnf:document-local-binding:v0_1",),
                        provenance_refs=(source_ref,),
                    )
                )
    return tuple(sorted(evidence, key=lambda item: item.evidence_ref))


def _constraint_assessments(graph: PNFGraph) -> tuple[ConstraintAssessment, ...]:
    """Assess parser-supported structural constraints without semantic closure."""

    factor_refs = {factor.factor_ref for factor in graph.factors}
    assessments: list[ConstraintAssessment] = []
    for constraint in graph.constraints:
        supported = {
            "syntactic_subject_of",
            "syntactic_object_of",
            "syntactic_oblique_of",
            "syntactic_complement_of",
            "content_of",
            "host_of_embedded_proposition",
            "nominal_head_of",
            "nominal_modifier_of",
        }
        source_ok = set(constraint.source_factor_refs).issubset(factor_refs)
        target_ok = set(constraint.target_factor_refs).issubset(factor_refs)
        state = (
            "satisfied_with_alternatives"
            if constraint.constraint_type in supported and source_ok and target_ok
            else "insufficient_evidence"
        )
        assessments.append(
            ConstraintAssessment(
                assessment_ref="constraint-assessment:"
                + canonical_sha256(
                    {
                        "constraint_ref": constraint.constraint_ref,
                        "state": state,
                        "provenance_refs": constraint.provenance_refs,
                    }
                ),
                constraint_ref=constraint.constraint_ref,
                state=state,
                evidence_refs=constraint.provenance_refs,
                residual_refs=(constraint.residual_on_failure,)
                if constraint.residual_on_failure
                else (),
            )
        )
    return tuple(sorted(assessments, key=lambda item: item.assessment_ref))


def _semantic_annotation_layer(
    *,
    document_ref: str,
    source_ref: str,
    content_sha256: str,
    tokens: Sequence[tuple[str, int, int]],
    base_layer: AnnotationLayer,
    text: str,
    parsed_document: Mapping[str, Any],
) -> tuple[AnnotationLayer, Mapping[str, Any], dict[str, str]]:
    """Project one public parser observation stream into the annotation graph.

    The relational bundle below is derived from ``parsed_document``; it is not
    permitted to create a second parser boundary.
    """

    bundle = collect_canonical_relational_bundle(text, parsed_document=parsed_document)
    parser_receipt = dict(parsed_document.get("parser_receipt") or {})
    parser_tokens = tuple(
        token
        for sentence in parsed_document.get("sents") or ()
        for token in sentence.get("tokens") or ()
    )
    token_indexes_by_span = {
        (start_char, end_char): index
        for index, (_token, start_char, end_char) in enumerate(tokens)
    }
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
                overlapping = [
                    index
                    for index, (_surface, token_start, token_end) in enumerate(tokens)
                    if token_start < end_char and token_end > start_char
                ]
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
    for atom in bundle.get("atoms") or ():
        start_char, end_char = (int(value) for value in atom["span"])
        covered = [
            index
            for index, (_token, token_start, token_end) in enumerate(tokens)
            if token_start < end_char and token_end > start_char
        ]
        if not covered:
            continue
        atom_ref = str(atom["id"])
        span_ref = "semantic-atom:" + canonical_sha256(
            {"document_ref": document_ref, "atom": atom}
        )
        atom_span_refs[atom_ref] = span_ref
        parser_token = next(
            (
                token
                for token in parser_tokens
                if int(token["start"]) == start_char and int(token["end"]) == end_char
            ),
            {},
        )
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
    relations: list[RelationAnnotation] = []
    for relation in bundle.get("relations") or ():
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


def _atom_mention_refs(
    *,
    semantic_layer: AnnotationLayer,
    atom_span_refs: Mapping[str, str],
    mentions: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    """Return licensed mentions overlapping each public semantic atom.

    Overlap only licenses a local structural alternative. It does not assert
    coreference, identity, or that a relation role is semantically closed.
    """

    spans_by_ref = {span.span_ref: span for span in semantic_layer.span_annotations}
    rows: dict[str, tuple[str, ...]] = {}
    for atom_ref, span_ref in sorted(atom_span_refs.items()):
        atom = spans_by_ref.get(span_ref)
        if atom is None:
            continue
        matched = tuple(
            sorted(
                str(mention["mention_ref"])
                for mention in mentions
                if int(mention["start_token"]) < atom.end_token
                and int(mention["end_token"]) > atom.start_token
            )
        )
        if matched:
            rows[atom_ref] = matched
    return rows


def _parser_observation_refs_by_mention(
    *,
    semantic_layer: AnnotationLayer,
    mentions: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    """Return graph-projected parser observations overlapping each mention.

    These references account for observation availability in diagnostics; they
    do not type the mention or infer a binding.
    """

    parser_spans = tuple(
        span
        for span in semantic_layer.span_annotations
        if span.annotation_type == "parser_token"
    )
    refs: dict[str, tuple[str, ...]] = {}
    for mention in mentions:
        mention_ref = str(mention["mention_ref"])
        start_token, end_token = int(mention["start_token"]), int(mention["end_token"])
        matched = tuple(
            sorted(
                span.span_ref
                for span in parser_spans
                if start_token < span.end_token and end_token > span.start_token
            )
        )
        if matched:
            refs[mention_ref] = matched
    return refs


def _compiler_declarations() -> tuple[Mapping[str, Any], ...]:
    """Return immutable generic declarations consumed by every local build."""

    grammar_rows = tuple(
        {"declaration_kind": "grammar", **row.to_dict()}
        for row in default_semantic_reduction_declarations()
    )
    shared_rows: tuple[Mapping[str, Any], ...] = (
        {
            "declaration_ref": "type-system:semantic-core:v0_1",
            "declaration_kind": "type_system",
            "types": (
                "semantic.argument_candidate",
                "semantic.eventuality_candidate",
                "semantic.temporal_candidate",
                "semantic.spatial_candidate",
                "semantic.coordination_candidate",
            ),
            "authority": "configuration_only",
        },
        {
            "declaration_ref": "grammar:semantic:role-typing:v0_3",
            "declaration_kind": "grammar",
            "input": "public_relational_annotation",
            "output": "branch_preserving_local_type_hypothesis",
            "authority": "configuration_only",
        },
        {
            "declaration_ref": "relation-algebra:public-relational-bundle:v0_1",
            "declaration_kind": "relation_algebra",
            "relations": (
                "predicate",
                "temporal",
                "spatial",
                "conjunction",
                "modifier",
                "composition",
            ),
            "authority": "configuration_only",
        },
        {
            "declaration_ref": "closure-contract:local-semantic:v0_1",
            "declaration_kind": "closure_contract",
            "local_residuals": ("document_local_recurrence_unchecked",),
            "external_residuals": ("external_identity_unresolved",),
            "authority": "configuration_only",
        },
        {
            "declaration_ref": "authority-policy:candidate-only:v0_1",
            "declaration_kind": "authority_policy",
            "permitted_authority": "candidate_only",
            "prohibited": ("identity_resolution", "claim_promotion"),
            "authority": "configuration_only",
        },
    )
    return tuple(
        sorted(grammar_rows + shared_rows, key=lambda row: str(row["declaration_ref"]))
    )


def _build_pnf_graph(
    *,
    document_ref: str,
    mentions: Sequence[Mapping[str, Any]],
    local_types: Sequence[Mapping[str, Any]],
    semantic_factors: Sequence[Factor[Any]],
    semantic_constraints: Sequence[FactorConstraint],
    semantic_relation_refs: Sequence[str],
    source_ref: str,
) -> PNFGraph:
    types_by_mention: dict[str, list[Mapping[str, Any]]] = {}
    for local_type in local_types:
        types_by_mention.setdefault(str(local_type["mention_ref"]), []).append(
            local_type
        )
    factors: list[Factor[Any]] = []
    for mention in sorted(mentions, key=lambda row: str(row["mention_ref"])):
        mention_ref = str(mention["mention_ref"])
        local_rows = sorted(
            types_by_mention.get(mention_ref, ()), key=lambda row: str(row["type_ref"])
        )
        alternatives = tuple(
            TypedAlternative(
                alternative_ref=str(row["type_ref"]),
                value={
                    "mention_ref": mention_ref,
                    "semantic_family": row["semantic_family"],
                    "local_type": row["local_type"],
                },
                type_ref=str(row["local_type"]),
                derivation_refs=tuple(row.get("evidence_refs") or ()),
            )
            for row in local_rows
        )
        families = {str(row["semantic_family"]) for row in local_rows}
        if not alternatives:
            alternatives = (
                TypedAlternative(
                    alternative_ref=f"{mention_ref}:generic-mention",
                    value={"mention_ref": mention_ref},
                    type_ref="semantic.mention_candidate",
                    derivation_refs=(mention_ref,),
                ),
            )
            closure_state, residuals = (
                "requires_local_typing",
                ("document_local_recurrence_unchecked", "local_type_unresolved"),
            )
        elif families.intersection(
            {"entity", "eventuality", "role", "property", "relation", "class"}
        ):
            closure_state, residuals = (
                "requires_external_resolution",
                ("document_local_recurrence_unchecked", "external_identity_unresolved"),
            )
        else:
            closure_state, residuals = "locally_closed", ()
        factors.append(
            Factor(
                factor_ref=f"factor:{document_ref}:{canonical_sha256(mention_ref)}",
                factor_type="semantic.mention_identity",
                alternatives=alternatives,
                residuals=residuals,
                closure_state=closure_state,
                metadata={"mention_ref": mention_ref},
            )
        )
        for local_row in local_rows:
            family = str(local_row["semantic_family"])
            if family not in {"quantity", "time", "location"}:
                continue
            factor_type = {
                "quantity": "semantic.quantity_measurement",
                "time": "semantic.temporal_expression",
                "location": "semantic.spatial_expression",
            }[family]
            factor_ref = "factor:" + canonical_sha256(
                {
                    "document_ref": document_ref,
                    "type_ref": local_row["type_ref"],
                    "factor_type": factor_type,
                }
            )
            factors.append(
                Factor(
                    factor_ref=factor_ref,
                    factor_type=factor_type,
                    alternatives=(
                        TypedAlternative(
                            alternative_ref=f"{factor_ref}:candidate",
                            value={
                                "mention_ref": mention_ref,
                                "local_type": local_row["local_type"],
                            },
                            type_ref=str(local_row["local_type"]),
                            derivation_refs=tuple(local_row.get("evidence_refs") or ()),
                        ),
                    ),
                    closure_state="locally_closed",
                    metadata={"mention_ref": mention_ref},
                )
            )
    source_factor_ref = "factor:" + canonical_sha256(
        {"document_ref": document_ref, "source_ref": source_ref, "kind": "attribution"}
    )
    factors.append(
        Factor(
            factor_ref=source_factor_ref,
            factor_type="semantic.source_attribution",
            alternatives=(
                TypedAlternative(
                    alternative_ref=f"{source_factor_ref}:candidate",
                    value={"source_ref": source_ref},
                    type_ref="semantic.source_document",
                    derivation_refs=(source_ref,),
                ),
            ),
            closure_state="locally_closed",
        )
    )
    factors.extend(semantic_factors)
    factor_by_ref = {factor.factor_ref: factor for factor in factors}
    return PNFGraph(
        graph_ref="pnf-graph:"
        + canonical_sha256(
            {
                "document_ref": document_ref,
                "factors": [row.to_dict() for row in factor_by_ref.values()],
            }
        ),
        document_ref=document_ref,
        factors=tuple(sorted(factor_by_ref.values(), key=lambda row: row.factor_ref)),
        constraints=tuple(
            sorted(
                {row.constraint_ref: row for row in semantic_constraints}.values(),
                key=lambda row: row.constraint_ref,
            )
        ),
        relation_refs=tuple(sorted(set(semantic_relation_refs))),
    )


def _local_meets_and_refinements(
    *,
    graph: PNFGraph,
    evidence: Sequence[LocalEvidence],
    constraint_assessments: Sequence[ConstraintAssessment],
) -> tuple[
    tuple[Mapping[str, Any], ...],
    tuple[TypedMeet[Any], ...],
    tuple[FactorRefinement[Any], ...],
]:
    evidence_by_subject: dict[str, list[LocalEvidence]] = {}
    for item in evidence:
        for subject_ref in item.subject_refs:
            evidence_by_subject.setdefault(subject_ref, []).append(item)
    meets: list[TypedMeet[Any]] = []
    refinements: list[FactorRefinement[Any]] = []
    plan: list[Mapping[str, Any]] = []
    assessments_by_constraint = {
        item.constraint_ref: item for item in constraint_assessments
    }
    factor_by_ref = {factor.factor_ref: factor for factor in graph.factors}
    for factor in graph.factors:
        if not factor.residuals:
            continue
        mention_ref = str(factor.metadata.get("mention_ref") or "")
        evidence_by_ref = {
            item.evidence_ref: item
            for item in (
                *evidence_by_subject.get(mention_ref, ()),
                *evidence_by_subject.get(factor.factor_ref, ()),
            )
        }
        matched_evidence = tuple(
            sorted(evidence_by_ref.values(), key=lambda item: item.evidence_ref)
        )
        factor_assessments = tuple(
            assessment
            for constraint in factor.constraints
            if (assessment := assessments_by_constraint.get(constraint.constraint_ref))
            is not None
        )
        if not matched_evidence and not factor_assessments:
            continue
        plan.append(
            {
                "plan_ref": "local-meet-plan:"
                + canonical_sha256(
                    {
                        "factor_ref": factor.factor_ref,
                        "evidence_refs": [
                            item.evidence_ref for item in matched_evidence
                        ],
                        "constraint_assessment_refs": [
                            item.assessment_ref for item in factor_assessments
                        ],
                    }
                ),
                "factor_ref": factor.factor_ref,
                "candidate_evidence_refs": [
                    item.evidence_ref for item in matched_evidence
                ],
                "constraint_assessment_refs": [
                    item.assessment_ref for item in factor_assessments
                ],
                "candidate_index": "mention_ref_to_document_local_evidence",
                "authority": "candidate_only",
            }
        )
        state = MeetState.COMPATIBLE_WITH_REFINEMENT
        evidence_refs = tuple(
            sorted(
                {item.evidence_ref for item in matched_evidence}
                | {
                    ref
                    for assessment in factor_assessments
                    for ref in assessment.evidence_refs
                }
            )
        )
        meet = TypedMeet(
            meet_ref="typed-meet:"
            + canonical_sha256(
                {
                    "factor": factor.factor_ref,
                    "evidence": evidence_refs,
                    "state": state.value,
                }
            ),
            left_ref=factor.factor_ref,
            right_ref=matched_evidence[0].evidence_ref
            if matched_evidence
            else "local-evidence:absent",
            meet_type="document_local_evidence",
            state=state,
            evidence_refs=evidence_refs,
            residual_refs=factor.residuals,
        )
        meets.append(meet)
        resulting_factor = factor
        transitions: list[ResidualTransition] = []
        added_alternatives: list[str] = []
        rejected_candidates: list[str] = []
        if (
            matched_evidence
            and "document_local_recurrence_unchecked" in factor.residuals
        ):
            resulting_factor = factor.transition_residuals(
                remove=("document_local_recurrence_unchecked",),
                closure_state="requires_external_resolution",
            )
            transitions.append(
                ResidualTransition(
                    residual_ref="document_local_recurrence_unchecked",
                    prior_state="open",
                    resulting_state="closed",
                    evidence_refs=evidence_refs,
                )
            )
        if (
            any(
                assessment.state == "satisfied_with_alternatives"
                for assessment in factor_assessments
            )
            and "syntactic_argument_structure_unchecked" in resulting_factor.residuals
        ):
            resulting_factor = resulting_factor.transition_residuals(
                remove=("syntactic_argument_structure_unchecked",),
                add=("semantic_role_unresolved",),
                closure_state="requires_external_resolution",
            )
            transitions.extend(
                (
                    ResidualTransition(
                        residual_ref="syntactic_argument_structure_unchecked",
                        prior_state="open",
                        resulting_state="closed",
                        evidence_refs=evidence_refs,
                    ),
                    ResidualTransition(
                        residual_ref="semantic_role_unresolved",
                        prior_state="absent",
                        resulting_state="open",
                        evidence_refs=evidence_refs,
                    ),
                )
            )
            role = str(factor.metadata.get("role") or "")
            dependency = str(factor.metadata.get("parser_dependency") or "")
            role_types = (
                ("patient", "theme")
                if role == "subject" and dependency == "nsubjpass"
                else ("agent", "experiencer", "theme")
                if role == "subject"
                else ("patient", "theme")
                if role in {"object", "argument"}
                else ()
            )
            for role_type in role_types:
                alternative = TypedAlternative(
                    alternative_ref=f"{factor.factor_ref}:role:{role_type}",
                    value={
                        "role": role,
                        "semantic_role": role_type,
                        "syntactic_dependency": dependency,
                    },
                    type_ref="semantic.role_candidate",
                    derivation_refs=tuple(
                        assessment.assessment_ref for assessment in factor_assessments
                    ),
                )
                resulting_factor = resulting_factor.add_alternatives(alternative)
                added_alternatives.append(alternative.alternative_ref)

        binding_evidence = tuple(
            item
            for item in matched_evidence
            if item.evidence_type == "typed_binding_candidate"
            and item.subject_refs
            and item.subject_refs[0] == factor.factor_ref
        )
        for item in binding_evidence:
            referential_type = str(item.payload.get("referential_type") or "")
            candidate_ref = next(
                (
                    subject_ref
                    for subject_ref in item.subject_refs
                    if subject_ref != factor.factor_ref
                ),
                "",
            )
            if item.relation == "binding_incompatible_with":
                rejected_candidates.append(
                    f"{factor.factor_ref}:binding:{referential_type}:{candidate_ref}"
                )
                continue
            if not candidate_ref:
                continue
            if candidate_ref not in factor_by_ref:
                continue
            alternative = TypedAlternative(
                alternative_ref=f"{factor.factor_ref}:binding:{referential_type}:{candidate_ref}",
                value={
                    "referential_type": referential_type,
                    "candidate_factor_ref": candidate_ref,
                    "relation": item.relation,
                },
                type_ref="semantic.binding_candidate",
                derivation_refs=(item.evidence_ref,),
            )
            resulting_factor = resulting_factor.add_alternatives(alternative)
            added_alternatives.append(alternative.alternative_ref)

        if resulting_factor.to_dict() == factor.to_dict():
            continue
        revision_ref = "factor-revision:" + canonical_sha256(
            {
                "prior": factor.to_dict(),
                "result": resulting_factor.to_dict(),
                "evidence": evidence_refs,
                "meet": meet.meet_ref,
            }
        )
        resulting_factor = replace(
            resulting_factor,
            metadata={**resulting_factor.metadata, "factor_revision_ref": revision_ref},
        )
        refinements.append(
            FactorRefinement(
                refinement_ref="factor-refinement:"
                + canonical_sha256(
                    {"factor": factor.factor_ref, "meet": meet.meet_ref}
                ),
                prior_factor=factor,
                resulting_factor=resulting_factor,
                added_alternative_refs=tuple(sorted(set(added_alternatives))),
                retained_alternative_refs=tuple(
                    item.alternative_ref for item in factor.alternatives
                ),
                rejected_candidate_refs=tuple(sorted(set(rejected_candidates))),
                residual_transitions=tuple(transitions),
                evidence_refs=evidence_refs,
            )
        )
    return (
        tuple(sorted(plan, key=lambda row: str(row["plan_ref"]))),
        tuple(meets),
        tuple(refinements),
    )


def compile_document(
    document_input: Mapping[str, Any],
    compiler_context: CompilerContext,
    *,
    artifact_store: CompilationArtifactStore | None = None,
) -> DocumentCompilation:
    """Compile one supported document through the shared local semantic core."""

    media_type = require_text(document_input.get("media_type"), "media_type")
    if (
        media_type not in _TEXT_MEDIA_TYPES
        or _adapter_for(media_type, compiler_context) is None
    ):
        raise ValueError(
            "compile_document requires a declared supported text capability"
        )
    source_text = document_input.get("canonical_text")
    if not isinstance(source_text, str) or not source_text:
        raise ValueError("document_input requires non-empty canonical_text")
    content_sha256 = require_text(
        document_input.get("content_sha256"), "content_sha256"
    )
    document_ref = require_text(document_input.get("document_ref"), "document_ref")
    source_ref = require_text(document_input.get("source_ref"), "source_ref")
    if media_type == "text/html":
        canonical = HtmlDocumentMediaAdapter(source_artifact_ref=source_ref).adapt(
            source_text
        )
        text = canonical.text
        source_normalisation = {
            "adapter_ref": "media:html:v0_1",
            "canonical_text_ref": canonical.text_id,
            "source_media_type": media_type,
            "warnings": list(canonical.warnings),
            "authority": "normalisation_only",
        }
    else:
        text = source_text
        source_normalisation = {
            "adapter_ref": "media:utf8-text:v0_1",
            "source_media_type": media_type,
            "authority": "normalisation_only",
        }
    if not text:
        raise ValueError("source normalisation produced empty canonical text")
    context_payload = compiler_context.to_dict()
    build_key_sha256 = canonical_sha256(
        {
            "document_ref": document_ref,
            "content_sha256": content_sha256,
            "context": context_payload,
            "compiler_contract": "postgres-semantic-compiler:v0_6",
        }
    )
    if artifact_store is not None:
        cached = artifact_store.load_completed(
            document_ref=document_ref, build_key_sha256=build_key_sha256
        )
        cached_compilation = cached.get("compilation") if cached else None
        if isinstance(cached_compilation, Mapping):
            return DocumentCompilation(
                document_ref=str(cached_compilation["document_ref"]),
                content_sha256=str(cached_compilation["content_sha256"]),
                media_type=str(cached_compilation["media_type"]),
                artifacts=dict(cached_compilation["artifacts"]),
                status=str(cached_compilation.get("status") or "compiled"),
                failure=cached_compilation.get("failure"),
            )
    parsed_document = parse_canonical_text(text)
    licensing = build_mention_licensing_carrier(
        canonical_text=text,
        source_ref=source_ref,
        document_ref=document_ref,
        parsed_document=parsed_document,
    )
    mentions = tuple(licensing["mentions"])
    recurrence = build_mention_recurrence_carrier(mentions=mentions)
    forms = build_form_derivation_carrier(mentions=mentions)
    tokens = tokenize_canonical_with_spans(text)
    layer = AnnotationLayer(
        layer_ref="annotation-layer:"
        + canonical_sha256({"document_ref": document_ref, "content": content_sha256}),
        tokenizer_ref=compiler_context.annotation_backend_ref,
        text_sha256=content_sha256,
        token_annotations=tuple(
            TokenAnnotation(index, "canonical_token", token, (source_ref,))
            for index, (token, _start, _end) in enumerate(tokens)
        ),
        span_annotations=tuple(
            SpanAnnotation(
                span_ref=str(row["mention_ref"]),
                start_token=int(row["start_token"]),
                end_token=int(row["end_token"]),
                annotation_type="licensed_mention",
                value={
                    "generation_reason": row["generation_reason"],
                    "surface": row["canonical_surface"],
                },
                provenance_refs=(source_ref,),
            )
            for row in mentions
        ),
        provenance_refs=(source_ref,),
    )
    annotation_graph = AnnotationGraph(
        graph_ref="annotation-graph:" + canonical_sha256(layer.to_dict()),
        layers=(layer,),
    )
    semantic_layer, relational_bundle, atom_span_refs = _semantic_annotation_layer(
        document_ref=document_ref,
        source_ref=source_ref,
        content_sha256=content_sha256,
        tokens=tokens,
        base_layer=layer,
        text=text,
        parsed_document=parsed_document,
    )
    annotation_graph = AnnotationGraph(
        graph_ref="annotation-graph:"
        + canonical_sha256({"layers": [layer.to_dict(), semantic_layer.to_dict()]}),
        layers=(layer, semantic_layer),
    )
    declarations = default_semantic_reduction_declarations()
    atom_mentions = _atom_mention_refs(
        semantic_layer=semantic_layer,
        atom_span_refs=atom_span_refs,
        mentions=mentions,
    )
    parser_observation_refs = _parser_observation_refs_by_mention(
        semantic_layer=semantic_layer,
        mentions=mentions,
    )
    structural_hypotheses = derive_relational_type_hypotheses(
        bundle=relational_bundle,
        atom_mention_refs=atom_mentions,
        declarations=declarations,
    )
    local_typing = build_local_typing_carrier(
        mentions=mentions,
        forms=forms["forms"],
        structural_hypotheses=structural_hypotheses,
    )
    unresolved_span_diagnostics = diagnose_untyped_mentions(
        mentions=mentions,
        local_typing=local_typing,
        bundle=relational_bundle,
        atom_mention_refs=atom_mentions,
        parser_observation_refs=parser_observation_refs,
        parser_capabilities=(parsed_document.get("parser_receipt") or {}).get(
            "capabilities", {}
        ),
    )
    semantic_output = reduce_relational_bundle(
        document_ref=document_ref,
        bundle=relational_bundle,
        atom_span_refs=atom_span_refs,
        declarations=declarations,
    )
    local_evidence = _local_evidence(
        document_ref=document_ref, recurrence=recurrence, local_typing=local_typing
    )
    pnf_graph = _build_pnf_graph(
        document_ref=document_ref,
        mentions=mentions,
        local_types=local_typing["local_type_alternatives"],
        semantic_factors=semantic_output.factors,
        semantic_constraints=semantic_output.constraints,
        semantic_relation_refs=semantic_output.relation_refs,
        source_ref=source_ref,
    )
    binding_evidence = _binding_evidence(
        graph=pnf_graph,
        mentions=mentions,
        semantic_layer=semantic_layer,
        document_ref=document_ref,
        source_ref=source_ref,
    )
    local_evidence = tuple(
        sorted((*local_evidence, *binding_evidence), key=lambda item: item.evidence_ref)
    )
    constraint_assessments = _constraint_assessments(pnf_graph)
    local_meet_plan, typed_meets, refinements = _local_meets_and_refinements(
        graph=pnf_graph,
        evidence=local_evidence,
        constraint_assessments=constraint_assessments,
    )
    refined_pnf_graph = pnf_graph
    for refinement in refinements:
        refined_pnf_graph = refined_pnf_graph.replace_factor(
            refinement.resulting_factor
        )
    demands = derive_resolution_demands(refined_pnf_graph)
    artifacts = {
        "canonical_text": text,
        "source_normalisation": source_normalisation,
        "build_key_sha256": build_key_sha256,
        "licensing": licensing,
        "recurrence": recurrence,
        "forms": forms,
        "local_typing": local_typing,
        "structural_type_hypotheses": [
            canonical_json(row) for row in structural_hypotheses
        ],
        "unresolved_span_diagnostics": [
            canonical_json(row) for row in unresolved_span_diagnostics
        ],
        "unresolved_span_diagnostic_summary": [
            canonical_json(row)
            for row in summarize_untyped_diagnostics(unresolved_span_diagnostics)
        ],
        "annotation_layer": layer.to_dict(),
        "parser_receipt": canonical_json(parsed_document.get("parser_receipt") or {}),
        "annotation_graph": {
            "graph_ref": annotation_graph.graph_ref,
            "layer_refs": [layer.layer_ref, semantic_layer.layer_ref],
        },
        "semantic_annotation_layer": semantic_layer.to_dict(),
        "relational_bundle": canonical_json(relational_bundle),
        "semantic_reduction_declarations": [row.to_dict() for row in declarations],
        "compiler_declarations": [
            canonical_json(row) for row in _compiler_declarations()
        ],
        "semantic_reduction_refs": list(semantic_output.declaration_refs),
        "semantic_reduction_constraints": [
            row.to_dict() for row in semantic_output.constraints
        ],
        "constraint_assessments": [row.to_dict() for row in constraint_assessments],
        "local_evidence": [row.to_dict() for row in local_evidence],
        "local_meet_plan": [canonical_json(row) for row in local_meet_plan],
        "pnf_graph": pnf_graph.to_dict(),
        "refined_pnf_graph": refined_pnf_graph.to_dict(),
        "resolution_demands": [canonical_json(row) for row in demands],
        "typed_meets": [row.to_dict() for row in typed_meets],
        "factor_refinements": [row.to_dict() for row in refinements],
        "phase_boundary": {
            "completed": ["inventory", "local_compile"],
            "network_performed": False,
            "cross_document_identity_closed": False,
            "readiness_invoked": False,
        },
    }
    compilation = DocumentCompilation(
        document_ref=document_ref,
        content_sha256=content_sha256,
        media_type=media_type,
        artifacts=artifacts,
    )
    if artifact_store is not None:
        artifact_store.persist(
            compilation=compilation.to_dict(),
            context=context_payload,
            build_key_sha256=build_key_sha256,
        )
    return compilation


def _write_json_append_only(path: Path, value: Mapping[str, Any]) -> str:
    payload = (
        json.dumps(
            canonical_json(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    encoded = payload.encode("utf-8")
    digest = _sha256(encoded)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"append-only artifact differs at {path}")
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".artifact-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return digest


def _write_content_addressed(
    output_dir: Path, value: Mapping[str, Any]
) -> tuple[str, str]:
    canonical = canonical_json(value)
    digest = canonical_sha256(canonical)
    path = output_dir / "objects" / "sha256" / f"{digest}.json"
    _write_json_append_only(path, canonical)
    return digest, str(path.relative_to(output_dir))


def _demand_groups(compilations: Sequence[DocumentCompilation]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for compilation in compilations:
        for demand in compilation.artifacts.get("resolution_demands") or ():
            semantic_key = demand.get("semantic_key") or {
                "document_ref": compilation.document_ref,
                "factor_ref": demand.get("factor_ref"),
                "factor_type": demand.get("factor_type"),
                "requested_facets": demand.get("requested_facets") or (),
            }
            key = canonical_sha256(semantic_key)
            group = groups.setdefault(
                key,
                {"semantic_key": canonical_json(semantic_key), "members": []},
            )
            group["members"].append(
                {
                    "document_ref": compilation.document_ref,
                    "demand_ref": demand["demand_ref"],
                }
            )
    rows = [
        {
            "demand_group_ref": f"demand-group:{key}",
            "semantic_key": group["semantic_key"],
            "members": sorted(
                group["members"],
                key=lambda item: (item["document_ref"], item["demand_ref"]),
            ),
            "authority": "candidate_only",
        }
        for key, group in sorted(groups.items())
    ]
    return {
        "schema_version": "sl.corpus_demand_groups.v0_1",
        "groups": rows,
        "cross_document_identity_closed": False,
        "authority": "candidate_only",
    }


def compile_directory(
    input_dir: str | Path,
    *,
    context: CompilerContext,
    output_store: str | Path,
    recursive: bool = True,
    follow_symlinks: bool = False,
    include_globs: Sequence[str] = (),
    exclude_globs: Sequence[str] = (),
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
    execution_phase: str = "local",
    artifact_store: CompilationArtifactStore | None = None,
) -> dict[str, Any]:
    """Compile phase 0--2 artifacts with per-document failure isolation."""

    if execution_phase not in {"inventory", "local", "demand_planning"}:
        raise ValueError(
            "initial directory kernel supports inventory, local, or demand_planning"
        )
    root = Path(input_dir).resolve()
    output = Path(output_store).resolve()
    manifest = build_corpus_manifest(
        root,
        context=context,
        recursive=recursive,
        follow_symlinks=follow_symlinks,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
        excluded_roots=(output,),
    )
    manifest_row = manifest.to_dict()
    context_row = context.to_dict()
    _write_json_append_only(output / "compiler-context.json", context_row)
    _write_json_append_only(output / "manifest.json", manifest_row)
    _write_content_addressed(output, context_row)
    _write_content_addressed(output, manifest_row)
    if execution_phase == "inventory":
        return {"manifest": manifest_row, "compilations": [], "phase": "inventory"}
    compilations: list[DocumentCompilation] = []
    failures: list[dict[str, Any]] = []
    by_path = {entry.relative_path: entry for entry in manifest.documents}
    compiled_refs: set[str] = set()
    for relative_path, entry in sorted(by_path.items()):
        if entry.status != "inventoried":
            continue
        # Multiple occurrences of identical content remain distinct manifest
        # rows, but they share one immutable document compilation.
        if entry.document_ref in compiled_refs:
            continue
        compiled_refs.add(entry.document_ref)
        try:
            payload = (root / relative_path).read_bytes()
            text = payload.decode("utf-8")
            compilation = compile_document(
                {
                    "document_ref": entry.document_ref,
                    "content_sha256": entry.content_sha256,
                    "media_type": entry.media_type,
                    "canonical_text": text,
                    "source_ref": f"document-source:{entry.document_ref}",
                },
                context,
                artifact_store=artifact_store,
            )
        except (OSError, UnicodeDecodeError, ValueError) as error:
            failure = {
                "document_ref": entry.document_ref,
                "relative_path": relative_path,
                "status": "normalisation_failed",
                "reason": str(error),
            }
            failures.append(failure)
            compilation = DocumentCompilation(
                document_ref=entry.document_ref,
                content_sha256=entry.content_sha256,
                media_type=entry.media_type,
                artifacts={},
                status="normalisation_failed",
                failure=failure,
            )
        row = compilation.to_dict()
        digest, object_path = _write_content_addressed(output, row)
        document_dir = (
            output / "documents" / compilation.document_ref.removeprefix("document:")
        )
        _write_json_append_only(document_dir / "compilation.json", row)
        _write_json_append_only(
            document_dir / "projection.json",
            {
                "document_ref": compilation.document_ref,
                "compilation_object_sha256": digest,
                "object_path": object_path,
            },
        )
        compilations.append(compilation)
    demand_groups = _demand_groups(compilations)
    _write_json_append_only(output / "corpus" / "demand-groups.json", demand_groups)
    _write_content_addressed(output, demand_groups)
    summary = {
        "schema_version": "sl.corpus_compilation_summary.v0_1",
        "corpus_ref": manifest.corpus_ref,
        "phase": execution_phase,
        "compiled_document_count": sum(
            item.status == "compiled" for item in compilations
        ),
        "failed_document_count": len(failures),
        "unsupported_document_count": sum(
            item.status == "unsupported_media" for item in manifest.documents
        ),
        "demand_group_count": len(demand_groups["groups"]),
        "network_performed": False,
        "cross_document_identity_closed": False,
        "readiness_invoked": False,
        "authority": "orchestration_only",
    }
    summary["summary_sha256"] = canonical_sha256(summary)
    _write_json_append_only(output / "corpus" / "run-summary.json", summary)
    _write_content_addressed(output, summary)
    return {
        "manifest": manifest_row,
        "compilations": [item.to_dict() for item in compilations],
        "demand_groups": demand_groups,
        "summary": summary,
    }


__all__ = [
    "COMPILATION_SCHEMA_VERSION",
    "CompilerContext",
    "CorpusManifest",
    "DocumentCompilation",
    "DocumentManifestEntry",
    "LOCAL_EVIDENCE_SCHEMA_VERSION",
    "LocalEvidence",
    "build_corpus_manifest",
    "compile_directory",
    "compile_document",
    "default_compiler_context",
]

# Compatibility name for callers that distinguish the package schema from its
# individual artifact schema versions.
COMPILATION_SCHEMA_VERSION = DOCUMENT_COMPILATION_SCHEMA_VERSION
