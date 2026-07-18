"""Deterministic local-only corpus compilation orchestration.

The directory is not a semantic source type.  This module inventories media,
invokes one shared document compiler, persists immutable projections, and
groups unresolved demands.  It deliberately does not perform registry I/O,
cross-document identity closure, readiness promotion, or corpus-specific
interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import mimetypes
import os
import tempfile
from typing import Any, Iterable, Mapping, Sequence

from src.ingestion.media_adapter_contract import MediaAdapterCapability
from src.language import (
    AnnotationGraph,
    AnnotationLayer,
    SpanAnnotation,
    TokenAnnotation,
)
from src.pnf import PNFGraph, derive_resolution_demands
from src.policy.algebra import (
    Factor,
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
from src.sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans


CORPUS_MANIFEST_SCHEMA_VERSION = "sl.corpus_manifest.v0_1"
DOCUMENT_COMPILATION_SCHEMA_VERSION = "sl.document_compilation.v0_1"
LOCAL_EVIDENCE_SCHEMA_VERSION = "sl.local_evidence.v0_1"

_TEXT_MEDIA_TYPES = {"text/plain", "text/markdown"}
_TEXT_SUFFIXES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".text": "text/plain",
}


@dataclass(frozen=True)
class CompilerContext:
    """Declared generic compiler capabilities, never a corpus/profile selector."""

    context_ref: str
    compiler_version: str
    media_normalization_ref: str
    media_capabilities: tuple[MediaAdapterCapability, ...] = (
        MediaAdapterCapability("media:utf8-text:v0_1", ("text/plain", "text/markdown")),
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


def _build_pnf_graph(
    *,
    document_ref: str,
    mentions: Sequence[Mapping[str, Any]],
    local_types: Sequence[Mapping[str, Any]],
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
            closure_state, residuals = (
                "requires_local_typing",
                ("local_type_unresolved",),
            )
        elif families.intersection(
            {"entity", "eventuality", "role", "property", "relation"}
        ):
            closure_state, residuals = (
                "requires_external_resolution",
                ("external_identity_unresolved",),
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
    return PNFGraph(
        graph_ref="pnf-graph:"
        + canonical_sha256(
            {
                "document_ref": document_ref,
                "factors": [row.to_dict() for row in factors],
            }
        ),
        document_ref=document_ref,
        factors=tuple(factors),
    )


def _local_meets_and_refinements(
    *, graph: PNFGraph, evidence: Sequence[LocalEvidence]
) -> tuple[tuple[TypedMeet[Any], ...], tuple[FactorRefinement[Any], ...]]:
    evidence_by_subject: dict[str, list[LocalEvidence]] = {}
    for item in evidence:
        for subject_ref in item.subject_refs:
            evidence_by_subject.setdefault(subject_ref, []).append(item)
    meets: list[TypedMeet[Any]] = []
    refinements: list[FactorRefinement[Any]] = []
    for factor in graph.factors:
        if not factor.residuals:
            continue
        mention_ref = str(factor.metadata.get("mention_ref") or "")
        matched_evidence = tuple(
            sorted(
                evidence_by_subject.get(mention_ref, ()),
                key=lambda item: item.evidence_ref,
            )
        )
        state = (
            MeetState.COMPATIBLE_WITH_REFINEMENT
            if matched_evidence
            else MeetState.NOT_EVALUATED
        )
        evidence_refs = tuple(item.evidence_ref for item in matched_evidence)
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
        refinements.append(
            FactorRefinement(
                refinement_ref="factor-refinement:"
                + canonical_sha256(
                    {"factor": factor.factor_ref, "meet": meet.meet_ref}
                ),
                prior_factor=factor,
                resulting_factor=factor,
                retained_alternative_refs=tuple(
                    item.alternative_ref for item in factor.alternatives
                ),
                residual_transitions=tuple(
                    ResidualTransition(
                        residual_ref=residual,
                        prior_state="open",
                        resulting_state="open",
                        evidence_refs=evidence_refs,
                    )
                    for residual in factor.residuals
                ),
                evidence_refs=evidence_refs,
            )
        )
    return tuple(meets), tuple(refinements)


def compile_document(
    document_input: Mapping[str, Any], compiler_context: CompilerContext
) -> DocumentCompilation:
    """Compile one supported document through the shared local semantic core."""

    media_type = require_text(document_input.get("media_type"), "media_type")
    if (
        media_type not in _TEXT_MEDIA_TYPES
        or _adapter_for(media_type, compiler_context) is None
    ):
        raise ValueError(
            "compile_document currently requires a declared UTF-8 text capability"
        )
    text = document_input.get("canonical_text")
    if not isinstance(text, str) or not text:
        raise ValueError("document_input requires non-empty canonical_text")
    content_sha256 = require_text(
        document_input.get("content_sha256"), "content_sha256"
    )
    document_ref = require_text(document_input.get("document_ref"), "document_ref")
    source_ref = require_text(document_input.get("source_ref"), "source_ref")
    licensing = build_mention_licensing_carrier(
        canonical_text=text, source_ref=source_ref, document_ref=document_ref
    )
    mentions = tuple(licensing["mentions"])
    recurrence = build_mention_recurrence_carrier(mentions=mentions)
    forms = build_form_derivation_carrier(mentions=mentions)
    local_typing = build_local_typing_carrier(mentions=mentions, forms=forms["forms"])
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
    local_evidence = _local_evidence(
        document_ref=document_ref, recurrence=recurrence, local_typing=local_typing
    )
    pnf_graph = _build_pnf_graph(
        document_ref=document_ref,
        mentions=mentions,
        local_types=local_typing["local_type_alternatives"],
    )
    demands = derive_resolution_demands(pnf_graph)
    typed_meets, refinements = _local_meets_and_refinements(
        graph=pnf_graph, evidence=local_evidence
    )
    artifacts = {
        "licensing": licensing,
        "recurrence": recurrence,
        "forms": forms,
        "local_typing": local_typing,
        "annotation_layer": layer.to_dict(),
        "annotation_graph": {
            "graph_ref": annotation_graph.graph_ref,
            "layer_refs": [layer.layer_ref],
        },
        "local_evidence": [row.to_dict() for row in local_evidence],
        "pnf_graph": pnf_graph.to_dict(),
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
    return DocumentCompilation(
        document_ref=document_ref,
        content_sha256=content_sha256,
        media_type=media_type,
        artifacts=artifacts,
    )


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
