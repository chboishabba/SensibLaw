"""Bounded parser execution fibres over one document-level semantic carrier.

Chunks in this module are physical parser work units only. They have disjoint
ownership intervals, overlapping context intervals, and global source
coordinates. Their observations are reconstructed into one parser document
before mention licensing, PNF construction, constraint closure, or persistence.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterator, Mapping, MutableMapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.runtime.active_document_resources import (
    ActiveDocumentResourceGuard,
    DocumentResourceLimitError,
)
from src.sensiblaw.interfaces import parse_canonical_text


DOCUMENT_FIBRE_CONTRACT = "parser-document-fibres:v0_2"
DOCUMENT_FIBRE_SCHEMA_VERSION = "sl.pnf.document_fibre.v0_1"
DOCUMENT_CARRIER_SCHEMA_VERSION = "sl.pnf.document_structural_carrier.v0_1"


@dataclass(frozen=True)
class DocumentFibrePolicy:
    """Physical chunk policy; none of these values changes semantic authority."""

    parser_limit_chars: int = 1_000_000
    target_chars: int = 400_000
    overlap_chars: int = 8_192
    workers: int = 2
    adaptive_partitioning: bool = True

    def estimate_workload(self, canonical_text: str) -> dict[str, int]:
        """Return cheap scheduling signals without invoking the parser."""

        return {
            "canonical_chars": len(canonical_text),
            "estimated_tokens": max(1, len(canonical_text) // 4),
            "estimated_sentences": max(
                1,
                sum(
                    canonical_text.count(separator)
                    for separator in (". ", "! ", "? ", "\n\n")
                ),
            ),
        }

    def should_partition(self, canonical_text: str) -> bool:
        """Schedule fibres from workload, not the parser safety ceiling."""

        if not self.adaptive_partitioning:
            return len(canonical_text) >= self.parser_limit_chars
        workload = self.estimate_workload(canonical_text)
        return (
            workload["canonical_chars"] >= self.target_chars
            or workload["estimated_tokens"] >= max(1, self.target_chars // 4)
        )

    def __post_init__(self) -> None:
        if self.parser_limit_chars < 1:
            raise ValueError("parser_limit_chars must be positive")
        if not 1 <= self.workers <= 32:
            raise ValueError("parser fibre workers must be between 1 and 32")
        if self.target_chars < 1:
            raise ValueError("parser fibre target_chars must be positive")
        if self.overlap_chars < 0:
            raise ValueError("parser fibre overlap_chars must be non-negative")
        if self.target_chars + (2 * self.overlap_chars) >= self.parser_limit_chars:
            raise ValueError(
                "parser fibre target plus bilateral overlap must stay below "
                "parser limit"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": DOCUMENT_FIBRE_CONTRACT,
            "parser_limit_chars": self.parser_limit_chars,
            "target_chars": self.target_chars,
            "overlap_chars": self.overlap_chars,
            "workers": self.workers,
            "adaptive_partitioning": self.adaptive_partitioning,
            "workload_estimator_ref": "chars_tokens_sentences:v0_1",
            "worker_count_semantic_effect": "none",
        }


@dataclass(frozen=True)
class DocumentFibre:
    document_ref: str
    fibre_ref: str
    sequence_no: int
    owner_start: int
    owner_end: int
    context_start: int
    context_end: int
    text_sha256: str

    def __post_init__(self) -> None:
        if self.sequence_no < 0:
            raise ValueError("fibre sequence_no must be non-negative")
        if not 0 <= self.context_start <= self.owner_start:
            raise ValueError("fibre left context does not contain ownership")
        if not self.owner_start < self.owner_end <= self.context_end:
            raise ValueError("fibre right context does not contain ownership")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DOCUMENT_FIBRE_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "fibre_ref": self.fibre_ref,
            "sequence_no": self.sequence_no,
            "owner_start": self.owner_start,
            "owner_end": self.owner_end,
            "context_start": self.context_start,
            "context_end": self.context_end,
            "text_sha256": self.text_sha256,
        }


@dataclass(frozen=True)
class DocumentStructuralCarrier:
    document_ref: str
    canonical_text_sha256: str
    canonical_length: int
    policy: DocumentFibrePolicy
    fibres: tuple[DocumentFibre, ...]

    @property
    def carrier_ref(self) -> str:
        return "document-structural-carrier:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": DOCUMENT_CARRIER_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "canonical_text_sha256": self.canonical_text_sha256,
            "canonical_length": self.canonical_length,
            "policy": self.policy.to_dict(),
            "fibres": [row.to_dict() for row in self.fibres],
            "ownership_coverage": "exactly_once",
            "context_overlap_semantic_effect": "evidence_only",
        }
        if include_ref:
            payload["carrier_ref"] = self.carrier_ref
        return payload


class _OwnedSentenceSequence(Sequence[Mapping[str, Any]]):
    """Replay owned parser sentences one physical fibre at a time."""

    def __init__(self, carrier: "DocumentSentenceCarrier", sentence_count: int):
        self._carrier = carrier
        self._sentence_count = sentence_count

    def __len__(self) -> int:
        return self._sentence_count

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        yield from self._carrier._iter_sentences()

    def __getitem__(self, index: int | slice) -> Mapping[str, Any] | tuple[Mapping[str, Any], ...]:
        if isinstance(index, slice):
            return tuple(self)[index]
        if index < 0:
            index += self._sentence_count
        if not 0 <= index < self._sentence_count:
            raise IndexError(index)
        for sentence_index, sentence in enumerate(self):
            if sentence_index == index:
                return sentence
        raise IndexError(index)


class DocumentSentenceCarrier(Mapping[str, Any]):
    """Checkpoint-backed document parser mapping with a bounded sentence view.

    It intentionally preserves the historical mapping shape while ensuring that
    a caller cannot retain every physical parser response merely by receiving a
    fibred parse result.  Each iteration reloads and releases one owned fibre.
    """

    def __init__(
        self,
        *,
        carrier: DocumentStructuralCarrier,
        canonical_text: str,
        checkpoint_dir: Path,
        parser_receipt: Mapping[str, Any],
        sentence_count: int,
        temporary_checkpoint_dir: tempfile.TemporaryDirectory[str] | None = None,
    ) -> None:
        self._carrier = carrier
        self._canonical_text = canonical_text
        self._checkpoint_dir = checkpoint_dir
        self._parser_receipt = dict(parser_receipt)
        self._sentences = _OwnedSentenceSequence(self, sentence_count)
        self._temporary_checkpoint_dir = temporary_checkpoint_dir

    def __getitem__(self, key: str) -> Any:
        if key == "text":
            return self._canonical_text
        if key == "sents":
            return self._sentences
        if key == "parser_receipt":
            return self._parser_receipt
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(("text", "sents", "parser_receipt"))

    def __len__(self) -> int:
        return 3

    def close(self) -> None:
        """Release an internally-created checkpoint directory, if any."""

        if self._temporary_checkpoint_dir is not None:
            self._temporary_checkpoint_dir.cleanup()
            self._temporary_checkpoint_dir = None

    def __del__(self) -> None:
        self.close()

    def _iter_sentences(self) -> Iterator[Mapping[str, Any]]:
        token_cursor = 0
        for fibre in self._carrier.fibres:
            parsed = _load_checkpoint(self._checkpoint_dir, fibre)
            if parsed is None:
                raise ValueError(f"missing parser checkpoint for {fibre.fibre_ref}")
            selected = list(_owned_sentence_rows(fibre=fibre, parsed_document=parsed))
            local_to_global: dict[int, int] = {}
            for row in selected:
                for token in row["tokens"]:
                    local_to_global[int(token.get("index", 0))] = token_cursor
                    token_cursor += 1
            for row in selected:
                merged_tokens: list[dict[str, Any]] = []
                for token in row["tokens"]:
                    local_index = int(token.get("index", 0))
                    local_head = int(token.get("head_index", local_index))
                    global_start = fibre.context_start + int(token.get("start", 0))
                    global_end = fibre.context_start + int(
                        token.get("end", token.get("start", 0))
                    )
                    global_index = local_to_global[local_index]
                    merged_tokens.append(
                        {
                            **token,
                            "index": global_index,
                            "head_index": local_to_global.get(local_head, global_index),
                            "start": global_start,
                            "end": global_end,
                        }
                    )
                yield {
                    "text": self._canonical_text[row["start"]:row["end"]],
                    "start": row["start"],
                    "end": row["end"],
                    "tokens": merged_tokens,
                    "fibre_ref": fibre.fibre_ref,
                }
            del selected
            del parsed


def _safe_owner_end(text: str, *, start: int, desired: int, target: int) -> int:
    """Choose a stable structural boundary without invoking a second parser."""

    if desired >= len(text):
        return len(text)
    search_floor = max(start + 1, desired - max(1_024, target // 10))
    search_ceiling = min(len(text), desired + max(1_024, target // 10))
    window = text[search_floor:search_ceiling]
    for separator in ("\n\n", "\n", ". ", "; ", " "):
        offset = window.rfind(separator, 0, desired - search_floor + 1)
        if offset >= 0:
            return search_floor + offset + len(separator)
    return desired


def build_document_structural_carrier(
    *,
    document_ref: str,
    canonical_text: str,
    policy: DocumentFibrePolicy,
) -> DocumentStructuralCarrier:
    """Build disjoint ownership fibres with bounded bilateral context."""

    if not canonical_text:
        raise ValueError("document structural carrier requires canonical text")
    digest = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
    owner_intervals: list[tuple[int, int]] = []
    owner_start = 0
    while owner_start < len(canonical_text):
        desired = min(len(canonical_text), owner_start + policy.target_chars)
        owner_end = _safe_owner_end(
            canonical_text,
            start=owner_start,
            desired=desired,
            target=policy.target_chars,
        )
        if owner_end <= owner_start:
            owner_end = desired
        owner_intervals.append((owner_start, owner_end))
        owner_start = owner_end

    fibres: list[DocumentFibre] = []
    for sequence_no, (start, end) in enumerate(owner_intervals):
        context_start = max(0, start - policy.overlap_chars)
        context_end = min(len(canonical_text), end + policy.overlap_chars)
        context = canonical_text[context_start:context_end]
        fibre_ref = "document-fibre:" + canonical_sha256(
            {
                "contract_ref": DOCUMENT_FIBRE_CONTRACT,
                "document_ref": document_ref,
                "canonical_text_sha256": digest,
                "sequence_no": sequence_no,
                "owner_start": start,
                "owner_end": end,
                "context_start": context_start,
                "context_end": context_end,
                "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
                "policy": policy.to_dict(),
            }
        )
        fibres.append(
            DocumentFibre(
                document_ref=document_ref,
                fibre_ref=fibre_ref,
                sequence_no=sequence_no,
                owner_start=start,
                owner_end=end,
                context_start=context_start,
                context_end=context_end,
                text_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
            )
        )
    return DocumentStructuralCarrier(
        document_ref=document_ref,
        canonical_text_sha256=digest,
        canonical_length=len(canonical_text),
        policy=policy,
        fibres=tuple(fibres),
    )


def _checkpoint_path(checkpoint_dir: Path, fibre: DocumentFibre) -> Path:
    digest = fibre.fibre_ref.removeprefix("document-fibre:")
    return checkpoint_dir / f"{digest}.json"


def _summary_path(checkpoint_dir: Path, fibre: DocumentFibre) -> Path:
    """Return the compact accounting sidecar for a fibre checkpoint."""

    digest = fibre.fibre_ref.removeprefix("document-fibre:")
    return checkpoint_dir / f"{digest}.summary.json"


def _load_checkpoint(
    checkpoint_dir: Path | None,
    fibre: DocumentFibre,
) -> dict[str, Any] | None:
    if checkpoint_dir is None:
        return None
    path = _checkpoint_path(checkpoint_dir, fibre)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("contract_ref") != DOCUMENT_FIBRE_CONTRACT
        or payload.get("fibre") != fibre.to_dict()
        or not isinstance(payload.get("parsed_document"), dict)
    ):
        return None
    return dict(payload["parsed_document"])


def _save_checkpoint(
    checkpoint_dir: Path | None,
    fibre: DocumentFibre,
    parsed_document: Mapping[str, Any],
) -> None:
    if checkpoint_dir is None:
        return
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(checkpoint_dir, fibre)
    payload = {
        "contract_ref": DOCUMENT_FIBRE_CONTRACT,
        "fibre": fibre.to_dict(),
        "parsed_document": dict(parsed_document),
    }
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=checkpoint_dir,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _build_fibre_summary(
    *, fibre: DocumentFibre, parsed_document: Mapping[str, Any]
) -> dict[str, Any]:
    """Extract receipt-only state while the worker still owns its parse.

    The parent must never reopen every parser payload just to create a document
    receipt.  This sidecar intentionally contains only counts, parser receipt
    metadata, and unresolved head endpoints needed by the document receipt.
    """

    selected = tuple(_owned_sentence_rows(fibre=fibre, parsed_document=parsed_document))
    counts = _parsed_document_measure_counts(parsed_document)
    token_cursor = 0
    cross_fibre_demands: list[dict[str, Any]] = []
    for row in selected:
        local_indexes = {int(token.get("index", 0)) for token in row["tokens"]}
        for token in row["tokens"]:
            local_index = int(token.get("index", 0))
            local_head = int(token.get("head_index", local_index))
            if local_head not in local_indexes:
                token_start = fibre.context_start + int(token.get("start", 0))
                cross_fibre_demands.append(
                    {
                        "demand_ref": "cross-fibre-demand:"
                        + canonical_sha256(
                            {
                                "document_ref": fibre.document_ref,
                                "token": (token_start, str(token.get("text") or "")),
                                "head": local_head,
                            }
                        ),
                        "demand_type": "dependency_endpoint",
                        "state": "unresolved",
                        "token_global_index": token_cursor,
                        "head_global_index": token_cursor,
                        "source_fibre_ref": fibre.fibre_ref,
                    }
                )
            token_cursor += 1
    return {
        "contract_ref": DOCUMENT_FIBRE_CONTRACT,
        "fibre": fibre.to_dict(),
        "counts": counts,
        "owned_sentence_count": len(selected),
        "owned_token_count": token_cursor,
        "parser_receipt": dict(parsed_document.get("parser_receipt") or {}),
        "cross_fibre_demands": cross_fibre_demands,
    }


def _save_fibre_summary(
    checkpoint_dir: Path | None,
    fibre: DocumentFibre,
    parsed_document: Mapping[str, Any],
) -> dict[str, Any]:
    summary = _build_fibre_summary(fibre=fibre, parsed_document=parsed_document)
    if checkpoint_dir is None:
        return summary
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = _summary_path(checkpoint_dir, fibre)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=checkpoint_dir, prefix=f".{path.name}.",
        suffix=".tmp", delete=False,
    ) as handle:
        json.dump(summary, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)
    return summary


def _load_fibre_summary(
    checkpoint_dir: Path, fibre: DocumentFibre
) -> dict[str, Any] | None:
    path = _summary_path(checkpoint_dir, fibre)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("contract_ref") != DOCUMENT_FIBRE_CONTRACT
        or payload.get("fibre") != fibre.to_dict()
    ):
        return None
    return payload


def _parsed_document_measure_counts(parsed_document: Mapping[str, Any]) -> dict[str, int]:
    sentences = tuple(parsed_document.get("sents") or ())
    token_count = sum(len(sentence.get("tokens") or ()) for sentence in sentences)
    dependency_count = sum(
        1
        for sentence in sentences
        for token in tuple(sentence.get("tokens") or ())
        if str(token.get("dep") or "")
    )
    return {
        "fibres": 1,
        "sentences": len(sentences),
        "tokens": token_count,
        "dependencies": dependency_count,
    }


def _parse_fibre(
    *,
    fibre: DocumentFibre,
    canonical_text: str,
    parser: Callable[[str], Mapping[str, Any]],
    checkpoint_dir: Path | None,
) -> tuple[DocumentFibre, dict[str, Any], bool]:
    checkpoint = _load_checkpoint(checkpoint_dir, fibre)
    if checkpoint is not None:
        return fibre, checkpoint, True
    context = canonical_text[fibre.context_start:fibre.context_end]
    if len(context) >= 1_000_000:
        raise ValueError("document fibre exceeds parser safety limit")
    parsed = dict(parser(context))
    if str(parsed.get("text") or "") != context:
        raise ValueError("parser fibre output disagrees with canonical context")
    _save_checkpoint(checkpoint_dir, fibre, parsed)
    return fibre, parsed, False


def _parse_fibre_process(
    *,
    fibre: DocumentFibre,
    canonical_text: str,
    checkpoint_dir: Path | None,
) -> tuple[DocumentFibre, dict[str, Any], bool]:
    """Process-isolated canonical parser worker for CPU-bound oversized fibres."""
    return _parse_fibre(
        fibre=fibre,
        canonical_text=canonical_text,
        parser=parse_canonical_text,
        checkpoint_dir=checkpoint_dir,
    )


def _parse_fibre_summary(
    *,
    fibre: DocumentFibre,
    canonical_text: str,
    checkpoint_dir: Path | None,
    parser: Callable[[str], Mapping[str, Any]] | None = None,
) -> tuple[DocumentFibre, dict[str, Any], bool]:
    """Persist one physical parse and return only bounded accounting metadata."""

    selected_parser = parse_canonical_text if parser is None else parser
    parsed_fibre, parsed, reused = _parse_fibre(
        fibre=fibre,
        canonical_text=canonical_text,
        parser=selected_parser,
        checkpoint_dir=checkpoint_dir,
    )
    summary = _load_fibre_summary(checkpoint_dir, parsed_fibre) if checkpoint_dir else None
    if summary is None:
        summary = _save_fibre_summary(checkpoint_dir, parsed_fibre, parsed)
    del parsed
    return parsed_fibre, summary, reused


def _owner_for_position(
    fibres: Sequence[DocumentFibre],
    position: int,
) -> DocumentFibre:
    for fibre in fibres:
        if fibre.owner_start <= position < fibre.owner_end:
            return fibre
    return fibres[-1]


def _parser_execution_checkpoint(
    guard: ActiveDocumentResourceGuard,
    *,
    fibre: DocumentFibre,
    active_batch_size: int,
    reusable_partition_refs: tuple[str, ...],
    checkpoint_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Sample the parser worker boundary and enrich every terminal receipt."""

    try:
        payload = guard.checkpoint(
            stage="parser_annotation",
            current_kernel="parser_fibre_execution",
            active_batch_size=active_batch_size,
            reusable_partition_refs=reusable_partition_refs,
        )
    except DocumentResourceLimitError as error:
        payload = dict(error.checkpoint)
        payload.update(
            {
                "fibre_ref": fibre.fibre_ref,
                "checkpoint_refs": list(checkpoint_refs),
            }
        )
        guard._write_receipt(payload)
        raise DocumentResourceLimitError(payload) from error
    return payload


def _owned_sentence_rows(
    *,
    fibre: DocumentFibre,
    parsed_document: Mapping[str, Any],
) -> Iterator[dict[str, Any]]:
    """Yield this fibre's owned sentences with global character coordinates."""

    for sentence_no, sentence in enumerate(parsed_document.get("sents") or ()):
        if not isinstance(sentence, Mapping):
            continue
        start = fibre.context_start + int(sentence.get("start", 0))
        end = fibre.context_start + int(sentence.get("end", sentence.get("start", 0)))
        if fibre.owner_start <= start < fibre.owner_end:
            yield {
                "sentence_no": sentence_no,
                "start": start,
                "end": end,
                "tokens": tuple(
                    dict(token)
                    for token in sentence.get("tokens") or ()
                    if isinstance(token, Mapping)
                ),
            }


def _build_streaming_parser_receipt(
    *,
    carrier: DocumentStructuralCarrier,
    checkpoint_dir: Path,
    reused_fibre_count: int,
    workload_estimate: Mapping[str, int],
    parser_limit_chars: int,
) -> tuple[dict[str, Any], int]:
    """Derive document receipt metadata without recreating document sentences."""

    receipts: list[Mapping[str, Any]] = []
    capabilities: list[Mapping[str, Any]] = []
    demands: list[dict[str, Any]] = []
    sentence_count = 0
    token_cursor = 0
    for fibre in carrier.fibres:
        summary = _load_fibre_summary(checkpoint_dir, fibre)
        if summary is None:
            raise ValueError(f"missing parser summary for {fibre.fibre_ref}")
        receipt = summary.get("parser_receipt") or {}
        if isinstance(receipt, Mapping):
            receipts.append(receipt)
            capability = receipt.get("capabilities") or {}
            if isinstance(capability, Mapping):
                capabilities.append(capability)
        sentence_count += int(summary.get("owned_sentence_count") or 0)
        for demand in summary.get("cross_fibre_demands") or ():
            if isinstance(demand, Mapping):
                row = dict(demand)
                row["token_global_index"] = token_cursor + int(row["token_global_index"])
                row["head_global_index"] = token_cursor + int(row["head_global_index"])
                demands.append(row)
        token_cursor += int(summary.get("owned_token_count") or 0)

    capability_keys = sorted({str(key) for row in capabilities for key in row})
    merged_capabilities = {
        key: all(bool(row.get(key, False)) for row in capabilities)
        for key in capability_keys
    }
    parser_contracts = sorted(
        {
            str(row.get("contract_ref") or row.get("backend_ref") or "")
            for row in receipts
        }
    )
    unresolved_count = len(demands)
    return (
        {
            "contract_ref": DOCUMENT_FIBRE_CONTRACT,
            "backend_ref": "parser:document-fibres",
            "upstream_parser_contract_refs": parser_contracts,
            "capabilities": merged_capabilities,
            "authority": "parser_observation_only",
            "document_structural_carrier": carrier.to_dict(),
            "fibre_count": len(carrier.fibres),
            "execution_mode": "adaptive_fibres",
            "worker_count": carrier.policy.workers,
            "partition_count": len(carrier.fibres),
            "parallelism_reason": (
                "workload_threshold"
                if len(carrier.fibres) > 1 and carrier.canonical_length < parser_limit_chars
                else "parser_safety_ceiling"
            ),
            "workload_estimate": dict(workload_estimate),
            "reused_fibre_count": reused_fibre_count,
            "cross_fibre_demands": sorted(demands, key=lambda row: str(row["demand_ref"])),
            "cross_fibre_fixed_point": {
                "state": "closed" if unresolved_count == 0 else "bounded_with_residuals",
                "iterations": 1,
                "layer": "parser_observation",
                "unresolved_demand_count": unresolved_count,
                "semantic_object": "document",
                "fibre_semantic_authority": False,
            },
        },
        sentence_count,
    )


def _merge_fibre_parses(
    *,
    carrier: DocumentStructuralCarrier,
    canonical_text: str,
    parsed_by_ref: MutableMapping[str, Mapping[str, Any]],
    reused_fibre_count: int,
    workload_estimate: Mapping[str, int] | None = None,
    parser_limit_chars: int | None = None,
) -> dict[str, Any]:
    selected_sentences: list[dict[str, Any]] = []
    receipts: list[Mapping[str, Any]] = []
    capabilities: list[Mapping[str, Any]] = []
    for fibre in carrier.fibres:
        # The merged document is the only retained parser carrier. Release each
        # physical fibre as soon as its owned observations have been copied.
        parsed = parsed_by_ref.pop(fibre.fibre_ref)
        receipt = parsed.get("parser_receipt") or {}
        if isinstance(receipt, Mapping):
            receipts.append(receipt)
            capability = receipt.get("capabilities") or {}
            if isinstance(capability, Mapping):
                capabilities.append(capability)
        for sentence_no, sentence in enumerate(parsed.get("sents") or ()):
            if not isinstance(sentence, Mapping):
                continue
            global_start = fibre.context_start + int(sentence.get("start", 0))
            global_end = fibre.context_start + int(
                sentence.get("end", sentence.get("start", 0))
            )
            if not fibre.owner_start <= global_start < fibre.owner_end:
                continue
            selected_sentences.append(
                {
                    "fibre": fibre,
                    "sentence_no": sentence_no,
                    "start": global_start,
                    "end": global_end,
                    "tokens": [
                        dict(token)
                        for token in sentence.get("tokens") or ()
                        if isinstance(token, Mapping)
                    ],
                }
            )
    selected_sentences.sort(
        key=lambda row: (
            int(row["start"]),
            int(row["end"]),
            row["fibre"].sequence_no,
            int(row["sentence_no"]),
        )
    )

    token_rows: list[
        tuple[tuple[str, int], tuple[int, int, str], dict[str, Any]]
    ] = []
    for sentence in selected_sentences:
        fibre = sentence["fibre"]
        for token in sentence["tokens"]:
            local_index = int(token.get("index", 0))
            global_start = fibre.context_start + int(token.get("start", 0))
            global_end = fibre.context_start + int(
                token.get("end", token.get("start", 0))
            )
            key = (global_start, global_end, str(token.get("text") or ""))
            token_rows.append(((fibre.fibre_ref, local_index), key, token))
    ordered_keys = sorted({row[1] for row in token_rows})
    global_index_by_key = {key: index for index, key in enumerate(ordered_keys)}
    key_by_local = {local: key for local, key, _token in token_rows}
    del token_rows
    del ordered_keys

    demands: list[dict[str, Any]] = []
    merged_sentences: list[dict[str, Any]] = []
    for sentence in selected_sentences:
        fibre = sentence["fibre"]
        merged_tokens: list[dict[str, Any]] = []
        for token in sentence["tokens"]:
            local_index = int(token.get("index", 0))
            local_head = int(token.get("head_index", local_index))
            token_key = key_by_local[(fibre.fibre_ref, local_index)]
            head_key = key_by_local.get((fibre.fibre_ref, local_head))
            global_index = global_index_by_key[token_key]
            if head_key is None:
                head_index = global_index
                demand_state = "unresolved"
            else:
                head_index = global_index_by_key[head_key]
                token_owner = _owner_for_position(carrier.fibres, token_key[0])
                head_owner = _owner_for_position(carrier.fibres, head_key[0])
                demand_state = (
                    "resolved"
                    if token_owner.fibre_ref != head_owner.fibre_ref
                    else ""
                )
            if demand_state:
                demands.append(
                    {
                        "demand_ref": "cross-fibre-demand:"
                        + canonical_sha256(
                            {
                                "document_ref": carrier.document_ref,
                                "token": token_key,
                                "head": head_key,
                            }
                        ),
                        "demand_type": "dependency_endpoint",
                        "state": demand_state,
                        "token_global_index": global_index,
                        "head_global_index": head_index,
                        "source_fibre_ref": fibre.fibre_ref,
                    }
                )
            merged_tokens.append(
                {
                    **token,
                    "index": global_index,
                    "head_index": head_index,
                    "start": token_key[0],
                    "end": token_key[1],
                }
            )
        merged_sentences.append(
            {
                "text": canonical_text[int(sentence["start"]):int(sentence["end"])],
                "start": int(sentence["start"]),
                "end": int(sentence["end"]),
                "tokens": merged_tokens,
                "fibre_ref": fibre.fibre_ref,
            }
        )
        sentence["tokens"] = []

    capability_keys = sorted(
        {str(key) for row in capabilities for key in row}
    )
    merged_capabilities = {
        key: all(bool(row.get(key, False)) for row in capabilities)
        for key in capability_keys
    }
    unresolved_count = sum(row["state"] == "unresolved" for row in demands)
    parser_contracts = sorted(
        {
            str(row.get("contract_ref") or row.get("backend_ref") or "")
            for row in receipts
        }
    )
    return {
        "text": canonical_text,
        "sents": merged_sentences,
        "parser_receipt": {
            "contract_ref": DOCUMENT_FIBRE_CONTRACT,
            "backend_ref": "parser:document-fibres",
            "upstream_parser_contract_refs": parser_contracts,
            "capabilities": merged_capabilities,
            "authority": "parser_observation_only",
            "document_structural_carrier": carrier.to_dict(),
            "fibre_count": len(carrier.fibres),
            "execution_mode": "adaptive_fibres",
            "worker_count": carrier.policy.workers,
            "partition_count": len(carrier.fibres),
            "parallelism_reason": (
                "workload_threshold"
                if parser_limit_chars is None
                or len(canonical_text) < parser_limit_chars
                else "parser_safety_ceiling"
            ),
            "workload_estimate": dict(workload_estimate or {}),
            "reused_fibre_count": reused_fibre_count,
            "cross_fibre_demands": sorted(
                demands,
                key=lambda row: str(row["demand_ref"]),
            ),
            "cross_fibre_fixed_point": {
                "state": (
                    "closed"
                    if unresolved_count == 0
                    else "bounded_with_residuals"
                ),
                "iterations": 1,
                "layer": "parser_observation",
                "unresolved_demand_count": unresolved_count,
                "semantic_object": "document",
                "fibre_semantic_authority": False,
            },
        },
    }


def parse_document_fibres(
    *,
    document_ref: str,
    canonical_text: str,
    parser: Callable[[str], Mapping[str, Any]],
    policy: DocumentFibrePolicy | None = None,
    checkpoint_dir: str | Path | None = None,
    progress: Any | None = None,
) -> dict[str, Any]:
    """Parse a document monolithically or as fibres under one output contract."""

    selected_policy = policy or DocumentFibrePolicy()
    resource_guard = ActiveDocumentResourceGuard(document_ref=document_ref)
    workload = selected_policy.estimate_workload(canonical_text)
    process_parser = (
        getattr(parser, "__module__", "")
        == "src.sensiblaw.interfaces.parser_adapter"
    )
    if not selected_policy.should_partition(canonical_text):
        # The public parser owns a sizeable optional NLP runtime.  Keep it in
        # the same disposable worker boundary used by partitioned documents so
        # a short document does not retain that runtime through graph identity,
        # closure, and persistence merely because it did not need splitting.
        if process_parser:
            whole_fibre = DocumentFibre(
                document_ref=document_ref,
                fibre_ref="document-fibre:whole_document",
                sequence_no=0,
                owner_start=0,
                owner_end=len(canonical_text),
                context_start=0,
                context_end=len(canonical_text),
                text_sha256=hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
            )
            try:
                with ProcessPoolExecutor(max_workers=1) as pool:
                    _fibre, parsed, _reused = pool.submit(
                        _parse_fibre_process,
                        fibre=whole_fibre,
                        canonical_text=canonical_text,
                        checkpoint_dir=None,
                    ).result()
                    _parser_execution_checkpoint(
                        resource_guard,
                        fibre=whole_fibre,
                        active_batch_size=1,
                        reusable_partition_refs=(whole_fibre.fibre_ref,),
                    )
            except BrokenProcessPool as error:
                payload = _parser_execution_checkpoint(
                    resource_guard,
                    fibre=whole_fibre,
                    active_batch_size=1,
                    reusable_partition_refs=(whole_fibre.fibre_ref,),
                )
                payload.update(
                    {
                        "resource_limit_reached": True,
                        "worker_lost": True,
                        "fibre_ref": whole_fibre.fibre_ref,
                        "checkpoint_refs": [],
                        "worker_error": str(error),
                    }
                )
                resource_guard._write_receipt(payload)
                raise DocumentResourceLimitError(payload) from error
            parsed = dict(parsed)
        else:
            parsed = dict(parser(canonical_text))
        receipt = dict(parsed.get("parser_receipt") or {})
        receipt.update(
            {
                "document_fibre_contract": DOCUMENT_FIBRE_CONTRACT,
                "execution_mode": "whole_document",
                "worker_count": 1,
                "partition_count": 1,
                "parallelism_reason": "below_adaptive_workload_threshold",
                "workload_estimate": workload,
                "fibre_count": 1,
                "reused_fibre_count": 0,
                "cross_fibre_demands": [],
                "cross_fibre_fixed_point": {
                    "state": "closed",
                    "iterations": 0,
                    "layer": "parser_observation",
                    "unresolved_demand_count": 0,
                    "semantic_object": "document",
                    "fibre_semantic_authority": False,
                },
            }
        )
        parsed["parser_receipt"] = receipt
        if (
            progress is not None
            and hasattr(progress, "observe")
            and getattr(progress, "active_stage", "parser_annotation")
            == "parser_annotation"
        ):
            counts = _parsed_document_measure_counts(parsed)
            progress.observe(
                measures={
                    name: {
                        "completed": count,
                        "unit": name,
                    }
                    for name, count in counts.items()
                },
                message="parser_fibre",
                details={
                    "document_stage": "parser_annotation",
                    "fibre_ref": "document-fibre:whole_document",
                    "fibre_sequence_no": 0,
                    "fibre_count": 1,
                    "owner_start": 0,
                    "owner_end": len(canonical_text),
                    "reused": False,
                    "execution_mode": "whole_document",
                },
            )
        return parsed

    carrier = build_document_structural_carrier(
        document_ref=document_ref,
        canonical_text=canonical_text,
        policy=selected_policy,
    )
    temporary_checkpoint_dir: tempfile.TemporaryDirectory[str] | None = None
    if checkpoint_dir is None:
        temporary_checkpoint_dir = tempfile.TemporaryDirectory(
            prefix="sensiblaw-document-fibres-"
        )
        resolved_checkpoint_dir = Path(temporary_checkpoint_dir.name)
    else:
        resolved_checkpoint_dir = Path(checkpoint_dir).resolve()
    reused_count = 0
    completed_fibres = 0
    completed_counts = {
        "sentences": 0,
        "tokens": 0,
        "dependencies": 0,
    }
    # The canonical parser releases too little GIL for thread pools to scale on
    # large fibres.  Use isolated processes for the public parser spine; retain
    # a thread fallback for injected test/adaptor parsers that may not be
    # importable in a child process.
    pool_type = ProcessPoolExecutor if process_parser else ThreadPoolExecutor
    with pool_type(max_workers=selected_policy.workers) as pool:
        futures = {
            pool.submit(
                _parse_fibre_summary,
                fibre=fibre,
                canonical_text=canonical_text,
                checkpoint_dir=resolved_checkpoint_dir,
                **({} if process_parser else {"parser": parser}),
            ): fibre
            for fibre in carrier.fibres
        }
        for future in as_completed(futures):
            expected_fibre = futures[future]
            try:
                fibre, summary, reused = future.result()
            except BrokenProcessPool as error:
                checkpoint_refs = tuple(
                    str(_checkpoint_path(resolved_checkpoint_dir, row))
                    for row in carrier.fibres
                    if _load_checkpoint(resolved_checkpoint_dir, row) is not None
                )
                payload = _parser_execution_checkpoint(
                    resource_guard,
                    fibre=expected_fibre,
                    active_batch_size=len(futures) - completed_fibres,
                    reusable_partition_refs=tuple(
                        row.fibre_ref for row in carrier.fibres
                        if _load_checkpoint(resolved_checkpoint_dir, row) is not None
                    ),
                    checkpoint_refs=checkpoint_refs,
                )
                payload.update(
                    {
                        "resource_limit_reached": True,
                        "worker_lost": True,
                        "fibre_ref": expected_fibre.fibre_ref,
                        "checkpoint_refs": list(checkpoint_refs),
                        "worker_error": str(error),
                    }
                )
                resource_guard._write_receipt(payload)
                raise DocumentResourceLimitError(payload) from error
            reused_count += int(reused)
            completed_fibres += 1
            for key in completed_counts:
                completed_counts[key] += int(summary["counts"][key])
            _parser_execution_checkpoint(
                resource_guard,
                fibre=fibre,
                active_batch_size=len(futures) - completed_fibres,
                reusable_partition_refs=tuple(
                    row.fibre_ref for row in carrier.fibres[:completed_fibres]
                ),
                checkpoint_refs=tuple(
                    str(_checkpoint_path(resolved_checkpoint_dir, row))
                    for row in carrier.fibres[:completed_fibres]
                ),
            )
            if progress is not None:
                if (
                    hasattr(progress, "observe")
                    and getattr(progress, "active_stage", "parser_annotation")
                    == "parser_annotation"
                ):
                    progress.observe(
                        measures={
                            "fibres": {
                                "completed": completed_fibres,
                                "total": len(carrier.fibres),
                                "unit": "fibres",
                            },
                            "sentences": {
                                "completed": completed_counts["sentences"],
                                "unit": "sentences",
                            },
                            "tokens": {
                                "completed": completed_counts["tokens"],
                                "unit": "tokens",
                            },
                            "dependencies": {
                                "completed": completed_counts["dependencies"],
                                "unit": "dependencies",
                            },
                        },
                        message="parser_fibre",
                        details={
                            "document_stage": "parser_annotation",
                            "fibre_ref": fibre.fibre_ref,
                            "fibre_sequence_no": fibre.sequence_no,
                            "fibre_count": len(carrier.fibres),
                            "owner_start": fibre.owner_start,
                            "owner_end": fibre.owner_end,
                            "reused": reused,
                        },
                    )
    parser_receipt, sentence_count = _build_streaming_parser_receipt(
        carrier=carrier,
        checkpoint_dir=resolved_checkpoint_dir,
        reused_fibre_count=reused_count,
        workload_estimate=workload,
        parser_limit_chars=selected_policy.parser_limit_chars,
    )
    return DocumentSentenceCarrier(
        carrier=carrier,
        canonical_text=canonical_text,
        checkpoint_dir=resolved_checkpoint_dir,
        parser_receipt=parser_receipt,
        sentence_count=sentence_count,
        temporary_checkpoint_dir=temporary_checkpoint_dir,
    )


__all__ = [
    "DOCUMENT_FIBRE_CONTRACT",
    "DocumentFibre",
    "DocumentFibrePolicy",
    "DocumentSentenceCarrier",
    "DocumentStructuralCarrier",
    "build_document_structural_carrier",
    "parse_document_fibres",
]
