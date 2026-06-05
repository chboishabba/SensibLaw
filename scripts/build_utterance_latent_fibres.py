#!/usr/bin/env python3
from __future__ import annotations

"""Build a pinned utterance latent fibre index from local corpus inputs."""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from itertools import chain

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sensiblaw.interfaces.shared_reducer import collect_canonical_predicate_atoms  # noqa: E402
from text.utterance_latent_fibres import LATENT_FIBRE_INDEX_SCHEMA  # noqa: E402


TEXT_KEYS = {"text", "body", "content", "statement", "utterance", "claim"}
CANDIDATE_KEYS = {
    "derived_fibre_candidates",
    "latent_fibre_candidates",
    "utterance_latent_fibre_candidates",
    "fibre_candidates",
}
DEFAULT_MIN_EVIDENCE_COUNT = 2
DEFAULT_MIN_SIGNAL_COUNT = 2
DEFAULT_MIN_CONFIDENCE = 0.80
DEFAULT_HIGH_PRECISION_EVIDENCE = 4
_COORDINATED_CLAUSE_RE = re.compile(r"\b(?:and|or)\b", re.IGNORECASE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", type=Path, default=[], help="Local JSON manifest with corpus metadata and optional candidate seeds.")
    parser.add_argument("--corpus", action="append", type=Path, default=[], help="Local JSON/text corpus source to scan for predicate counts.")
    parser.add_argument("--output", required=True, type=Path, help="Artifact path to write.")
    parser.add_argument("--artifact-id", default="", help="Stable artifact id. Defaults to a hash-derived local id.")
    parser.add_argument("--profile-name", default="local-pnf-candidate-manifest", help="Extraction profile name.")
    parser.add_argument("--profile-version", default="v0_1", help="Extraction profile version.")
    parser.add_argument("--min-evidence", type=int, default=DEFAULT_MIN_EVIDENCE_COUNT, help="Minimum co-occurrence support required for generated candidates.")
    parser.add_argument("--min-signal", type=int, default=DEFAULT_MIN_SIGNAL_COUNT, help="Minimum signal count required for generated candidates.")
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE, help="Minimum confidence required for generated candidates.")
    args = parser.parse_args(argv)

    payload = build_artifact(
        manifests=args.manifest,
        corpora=args.corpus,
        artifact_id=args.artifact_id,
        profile_name=args.profile_name,
        profile_version=args.profile_version,
        min_evidence_count=args.min_evidence,
        min_signal_count=args.min_signal,
        min_confidence=args.min_confidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(args.output), "candidate_count": len(payload["derived_fibre_candidates"])}, sort_keys=True))
    return 0


def build_artifact(
    *,
    manifests: Iterable[Path],
    corpora: Iterable[Path],
    artifact_id: str = "",
    profile_name: str = "local-pnf-candidate-manifest",
    profile_version: str = "v0_1",
    min_evidence_count: int = DEFAULT_MIN_EVIDENCE_COUNT,
    min_signal_count: int = DEFAULT_MIN_SIGNAL_COUNT,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> dict[str, Any]:
    manifest_payloads = [_load_path(path) for path in manifests]
    corpus_payloads = [_load_path(path) for path in corpora]
    corpus_texts = tuple(_iter_texts((*manifest_payloads, *corpus_payloads)))
    predicate_counts = Counter[str]()
    cooccurrence_info = _collect_predicate_cooccurrence(corpus_texts, predicate_counts)
    generated_candidates = _iter_generated_candidates(
        cooccurrence_info,
        min_evidence_count=min_evidence_count,
        min_signal_count=min_signal_count,
        min_confidence=min_confidence,
    )
    candidate_payloads = _normalize_candidates(
        chain(
            generated_candidates,
            _iter_candidate_seeds(manifest_payloads),
        )
    )
    candidates = tuple(candidate_payloads)
    for candidate in candidates:
        predicate_counts.setdefault(candidate["source_predicate"], 0)
        predicate_counts.setdefault(candidate["target_predicate"], 0)

    source_seed = {
        "manifests": [_path_record(path) for path in manifests],
        "corpora": [_path_record(path) for path in corpora],
        "text_count": len(corpus_texts),
        "candidate_count": len(candidates),
    }
    manifest_hash = "sha256:" + _sha256_json(source_seed)
    stable_artifact_id = artifact_id.strip() or f"utterance-latent-fibres:{manifest_hash.removeprefix('sha256:')[:16]}"

    return {
        "artifact_id": stable_artifact_id,
        "schema_version": LATENT_FIBRE_INDEX_SCHEMA,
        "source_corpus": {
            "manifest_id": "local-utterance-latent-fibre-corpus",
            "manifest_hash": manifest_hash,
            "source_count": len(source_seed["manifests"]) + len(source_seed["corpora"]),
            "text_count": len(corpus_texts),
        },
        "extraction_profile": {
            "name": profile_name,
            "version": profile_version,
            "builder": "SensibLaw/scripts/build_utterance_latent_fibres.py",
        },
        "model_assets": [],
        "predicate_nodes": {
            predicate: {"observation_count": count}
            for predicate, count in sorted(predicate_counts.items())
        },
        "role_context_signatures": _role_context_signatures(manifest_payloads),
        "derived_fibre_candidates": list(candidates),
        "build_stats": {
            "corpus_text_count": len(corpus_texts),
            "manifest_count": len(source_seed["manifests"]),
            "corpus_file_count": len(source_seed["corpora"]),
            "candidate_count": len(candidates),
            "source_seed_sha256": manifest_hash,
        },
    }


def _load_path(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".json", ".jsonl"}:
        if path.suffix.lower() == ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return json.loads(text)
    return {"text": text, "source_path": str(path)}


def _path_record(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _iter_texts(values: Iterable[Any]) -> Iterable[str]:
    for value in values:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key) in TEXT_KEYS and isinstance(item, str) and item.strip():
                    yield item.strip()
                else:
                    yield from _iter_texts((item,))
        elif isinstance(value, list | tuple):
            yield from _iter_texts(value)


def _collect_predicate_cooccurrence(
    texts: tuple[str, ...],
    predicate_counts: Counter[str],
) -> dict[str, dict[str, Any]]:
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    pair_context_signatures: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_refs: dict[tuple[str, str], list[str]] = defaultdict(list)

    for text_index, text in enumerate(texts):
        if not str(text).strip():
            continue
        atoms = _collect_cooccurrence_atoms(text)
        context_predicates: list[tuple[str, tuple[str, ...]]] = []
        for atom in atoms:
            predicate = atom.predicate.strip().casefold()
            if not predicate:
                continue
            predicate_counts[predicate] += 1
            signature = _atom_signature(atom)
            context_predicates.append((predicate, signature))

        normalized_predicates: list[tuple[str, tuple[str, ...]]] = []
        seen: set[str] = set()
        for predicate, signature in context_predicates:
            if predicate not in seen:
                seen.add(predicate)
                normalized_predicates.append((predicate, signature))

        for i, (left_predicate, left_sig) in enumerate(normalized_predicates):
            for right_predicate, right_sig in normalized_predicates[i + 1 :]:
                left, right = sorted((left_predicate, right_predicate))
                key = (left, right)
                pair_counts[key] += 1
                pair_refs[key].append(f"ctx:{text_index}:{left}:{right}")
                for signature in (left_sig, right_sig):
                    if signature:
                        pair_context_signatures[key].add(signature)
                        pair_context_signatures[(right, left)].add(signature)

    return {
        f"{left}:{right}": {
            "left": left,
            "right": right,
            "count": pair_counts[(left, right)],
            "refs": sorted(set(pair_refs[(left, right)])),
            "signatures": sorted(pair_context_signatures[(left, right)]),
        }
        for (left, right), count in pair_counts.items()
        if count > 0
    }


def _collect_cooccurrence_atoms(text: str) -> tuple[Any, ...]:
    atoms = list(collect_canonical_predicate_atoms(text, enable_utterance_latent_fibres=False))
    for clause in _coordinated_clauses(text):
        atoms.extend(collect_canonical_predicate_atoms(clause, enable_utterance_latent_fibres=False))

    deduped: dict[tuple[str, tuple[tuple[str, str], ...]], Any] = {}
    for atom in atoms:
        role_signature = tuple(
            sorted(
                (str(role), str(getattr(arg, "value", "")))
                for role, arg in getattr(atom, "roles", {}).items()
                if role != "action"
            )
        )
        deduped[(str(getattr(atom, "predicate", "")).casefold(), role_signature)] = atom
    return tuple(deduped.values())


def _coordinated_clauses(text: str) -> tuple[str, ...]:
    parts = [part.strip(" .!?;:\n\t") for part in _COORDINATED_CLAUSE_RE.split(text) if part.strip(" .!?;:\n\t")]
    if len(parts) < 2:
        return ()
    return tuple(f"{part}." for part in parts)


def _atom_signature(atom: Any) -> tuple[str, ...]:
    typed_items: list[str] = []
    valued_items: list[str] = []
    roles = getattr(atom, "roles", {})
    for role, value in sorted(roles.items()):
        if role == "action":
            continue
        entity_type = getattr(value, "entity_type", None) or "*"
        text = getattr(value, "value", None)
        if entity_type is not None:
            typed_items.append(f"{role}:{entity_type}")
        if text not in (None, ""):
            valued_items.append(f"{role}:{entity_type}={text}")
    if not typed_items and not valued_items:
        return ()
    return ("|".join(typed_items), "|".join(valued_items))


def _iter_generated_candidates(
    cooccurrence_info: dict[str, dict[str, Any]],
    *,
    min_evidence_count: int,
    min_signal_count: int,
    min_confidence: float,
) -> Iterable[dict[str, Any]]:
    for key, info in cooccurrence_info.items():
        left = str(info["left"])
        right = str(info["right"])
        count = int(info["count"])
        if count < min_evidence_count:
            continue
        signal_count = len(info["refs"])
        if signal_count < min_signal_count:
            continue

        # Symmetric pair evidence: generate both directions so residual checks are
        # stable regardless of which predicate is treated as the query side.
        confidence = _cooccurrence_confidence(count, signal_count=signal_count)
        if confidence < min_confidence:
            continue

        evidence_refs = sorted(set(str(item) for item in info["refs"]))
        signatures = sorted(set(str(item) for item in info["signatures"]))
        high_precision = count >= DEFAULT_HIGH_PRECISION_EVIDENCE and confidence >= 0.90

        for source, target in ((left, right), (right, left)):
            direction = "forward" if source == left else "reverse"
            yield {
                "candidate_id": f"fibre:{source}-{target}:cooccurrence:{direction}",
                "source_predicate": source,
                "target_predicate": target,
                "relation": "same_family_candidate",
                "confidence": confidence,
                "evidence_count": count,
                "signal_count": signal_count,
                "evidence_refs": evidence_refs,
                "role_context_signatures": signatures,
                "provenance_refs": evidence_refs,
                "high_precision": high_precision,
                "canonical": True,
                "diagnostics_only": False,
                "model_refs": ["cooccurrence_generator:v1"],
            }


def _cooccurrence_confidence(
    evidence_count: int,
    *,
    signal_count: int = 0,
) -> float:
    evidence_support = min(1.0, evidence_count / 4)
    signal_support = min(1.0, signal_count / 4)
    return round(0.35 + (0.55 * evidence_support) + (0.10 * signal_support), 3)


def _iter_candidate_seeds(values: Iterable[Any]) -> Iterable[Mapping[str, Any]]:
    for value in values:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key) in CANDIDATE_KEYS and isinstance(item, list):
                    for candidate in item:
                        if isinstance(candidate, Mapping):
                            yield candidate
                else:
                    yield from _iter_candidate_seeds((item,))
        elif isinstance(value, list | tuple):
            yield from _iter_candidate_seeds(value)


def _normalize_candidates(values: Iterable[Mapping[str, Any]]) -> Iterable[dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for raw in values:
        source = _required_text(raw, "source_predicate")
        target = _required_text(raw, "target_predicate")
        candidate_id = str(raw.get("candidate_id") or f"fibre:{source}-{target}:canonical")
        candidate = {
            "candidate_id": candidate_id,
            "source_predicate": source,
            "target_predicate": target,
            "relation": str(raw.get("relation") or "same_family_candidate"),
            "confidence": float(raw.get("confidence") or 0.0),
            "evidence_count": int(raw.get("evidence_count") or len(_text_list(raw.get("evidence_refs")))),
            "signal_count": int(raw.get("signal_count") or 0),
            "evidence_refs": _text_list(raw.get("evidence_refs")),
            "role_context_signatures": _text_list(raw.get("role_context_signatures")),
            "provenance_refs": _text_list(raw.get("provenance_refs")),
            "high_precision": bool(raw.get("high_precision")),
            "canonical": bool(raw.get("canonical", True)),
            "diagnostics_only": bool(raw.get("diagnostics_only")),
            "model_refs": _text_list(raw.get("model_refs")),
        }
        normalized[candidate_id] = candidate
    return (
        normalized[key]
        for key in sorted(
            normalized,
            key=lambda item: (
                normalized[item]["source_predicate"],
                normalized[item]["target_predicate"],
                item,
            ),
        )
    )


def _role_context_signatures(values: Iterable[Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        if not isinstance(value, Mapping):
            continue
        raw = value.get("role_context_signatures")
        if isinstance(raw, Mapping):
            for key, item in raw.items():
                if isinstance(item, Mapping):
                    merged[str(key)] = dict(item)
    return dict(sorted(merged.items()))


def _required_text(raw: Mapping[str, Any], key: str) -> str:
    value = str(raw.get(key) or "").strip().casefold()
    if not value:
        raise ValueError(f"candidate requires {key}")
    return value


def _text_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, Iterable):
        return [str(item) for item in raw if str(item or "").strip()]
    return [str(raw)]


def _sha256_json(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
