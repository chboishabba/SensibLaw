"""Bounded parser execution fibres over one document-level semantic carrier.

Chunks in this module are physical parser work units only. They have disjoint
ownership intervals, overlapping context intervals, and global source
coordinates. Their observations are reconstructed into one parser document
before mention licensing, PNF construction, constraint closure, or persistence.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


DOCUMENT_FIBRE_CONTRACT = "parser-document-fibres:v0_1"
DOCUMENT_FIBRE_SCHEMA_VERSION = "sl.pnf.document_fibre.v0_1"
DOCUMENT_CARRIER_SCHEMA_VERSION = "sl.pnf.document_structural_carrier.v0_1"


@dataclass(frozen=True)
class DocumentFibrePolicy:
    """Physical chunk policy; none of these values changes semantic authority."""

    parser_limit_chars: int = 1_000_000
    target_chars: int = 400_000
    overlap_chars: int = 8_192
    workers: int = 2

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


def _owner_for_position(
    fibres: Sequence[DocumentFibre],
    position: int,
) -> DocumentFibre:
    for fibre in fibres:
        if fibre.owner_start <= position < fibre.owner_end:
            return fibre
    return fibres[-1]


def _merge_fibre_parses(
    *,
    carrier: DocumentStructuralCarrier,
    canonical_text: str,
    parsed_by_ref: Mapping[str, Mapping[str, Any]],
    reused_fibre_count: int,
) -> dict[str, Any]:
    selected_sentences: list[dict[str, Any]] = []
    receipts: list[Mapping[str, Any]] = []
    capabilities: list[Mapping[str, Any]] = []
    for fibre in carrier.fibres:
        parsed = parsed_by_ref[fibre.fibre_ref]
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
    if len(canonical_text) < selected_policy.parser_limit_chars:
        parsed = dict(parser(canonical_text))
        receipt = dict(parsed.get("parser_receipt") or {})
        receipt.update(
            {
                "document_fibre_contract": DOCUMENT_FIBRE_CONTRACT,
                "execution_mode": "whole_document",
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
        return parsed

    carrier = build_document_structural_carrier(
        document_ref=document_ref,
        canonical_text=canonical_text,
        policy=selected_policy,
    )
    resolved_checkpoint_dir = (
        Path(checkpoint_dir).resolve() if checkpoint_dir is not None else None
    )
    results: dict[str, Mapping[str, Any]] = {}
    reused_count = 0
    with ThreadPoolExecutor(max_workers=selected_policy.workers) as pool:
        futures = {
            pool.submit(
                _parse_fibre,
                fibre=fibre,
                canonical_text=canonical_text,
                parser=parser,
                checkpoint_dir=resolved_checkpoint_dir,
            ): fibre
            for fibre in carrier.fibres
        }
        for future in as_completed(futures):
            fibre, parsed, reused = future.result()
            results[fibre.fibre_ref] = parsed
            reused_count += int(reused)
            if progress is not None:
                progress.advance(
                    amount=0,
                    message="parser_fibre",
                    reused=reused,
                    details={
                        "document_stage": "parser_annotation",
                        "fibre_ref": fibre.fibre_ref,
                        "fibre_sequence_no": fibre.sequence_no,
                        "fibre_count": len(carrier.fibres),
                        "owner_start": fibre.owner_start,
                        "owner_end": fibre.owner_end,
                    },
                )
    return _merge_fibre_parses(
        carrier=carrier,
        canonical_text=canonical_text,
        parsed_by_ref=results,
        reused_fibre_count=reused_count,
    )


__all__ = [
    "DOCUMENT_FIBRE_CONTRACT",
    "DocumentFibre",
    "DocumentFibrePolicy",
    "DocumentStructuralCarrier",
    "build_document_structural_carrier",
    "parse_document_fibres",
]
