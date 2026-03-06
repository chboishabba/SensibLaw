#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
SENSIBLAW_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gwb_timeline_texts() -> list[str]:
    payload = _load_json(ROOT / "SensibLaw" / ".cache_local" / "wiki_timeline_gwb.json")
    return [str(ev.get("text") or "").strip() for ev in payload.get("events", []) if str(ev.get("text") or "").strip()]


def _legal_fixture_texts() -> list[str]:
    files = [
        ROOT / "data" / "pdfs" / "Mabo [No 2] - [1992] HCA 23.json",
        ROOT / "data" / "pdfs" / "Plaintiff S157_2002 v Commonwealth - [2003] HCA 2.json",
    ]
    out: list[str] = []
    for path in files:
        if not path.exists():
            continue
        payload = _load_json(path)
        body = str(payload.get("body") or "").strip()
        if body:
            out.append(body)
    return out


def _legal_principles_texts() -> list[str]:
    files = [
        ROOT / "SensibLaw" / "demo" / "ingest" / "legal_principles_au_v1" / "wiki_timeline_legal_principles_au_v1.json",
        ROOT / "SensibLaw" / "demo" / "ingest" / "legal_principles_au_v1" / "follow" / "wiki_timeline_legal_principles_au_v1_follow.json",
    ]
    out: list[str] = []
    for path in files:
        if not path.exists():
            continue
        payload = _load_json(path)
        out.extend(str(ev.get("text") or "").strip() for ev in payload.get("events", []) if str(ev.get("text") or "").strip())
    return out


def _mixed_texts() -> list[str]:
    return [
        "George W. Bush was considered really great; did you know that?",
        "Civil Liability Act 2002 (NSW) s 5B(2)(a) applies if a person ought to have foreseen the risk.",
        "Plaintiff S157/2002 v Commonwealth [2003] HCA 2 concerns judicial review under s 75(v) of the Constitution.",
        "Sch 1 cl 4 and r 7.32 were discussed at the hearing on February 4, 2003.",
    ]


def _deterministic_tokenizer() -> Callable[[str], list[str]]:
    from src.text.lexeme_index import collect_lexeme_occurrences

    def inner(text: str) -> list[str]:
        return [occ.norm_text for occ in collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")]

    return inner


def _legacy_tokenizer() -> Callable[[str], list[str]]:
    from src.text.lexeme_index import collect_lexeme_occurrences

    def inner(text: str) -> list[str]:
        return [occ.norm_text for occ in collect_lexeme_occurrences(text, canonical_mode="legacy_regex")]

    return inner


def _spacy_tokenizer() -> Callable[[str], list[str]] | None:
    try:
        from src.text.lexeme_index import collect_lexeme_occurrences
    except Exception:
        return None

    def inner(text: str) -> list[str]:
        return [occ.norm_text for occ in collect_lexeme_occurrences(text, canonical_mode="spacy")]

    return inner


def _tiktoken_tokenizer() -> Callable[[str], list[str]] | None:
    try:
        import tiktoken  # type: ignore
    except Exception:
        return None

    enc = tiktoken.get_encoding("cl100k_base")

    def inner(text: str) -> list[str]:
        return [str(tok) for tok in enc.encode(text)]

    return inner


def _summarize(texts: list[str], tokenize: Callable[[str], list[str]]) -> dict:
    total_chars = sum(len(t) for t in texts)
    total_tokens = 0
    unique_tokens: set[str] = set()
    corpus_token_presence: Counter[str] = Counter()
    legal_atom_hits = 0
    legal_atom_total = 0

    atom_needles = [
        "sec:5b",
        "subsec:2",
        "para:a",
        "act:civil_liability_act_2002_nsw",
        "pt:4",
        "div:2",
        "rule:7.32",
        "sch:1",
        "cl:4",
    ]

    for text in texts:
        toks = tokenize(text)
        total_tokens += len(toks)
        token_set = set(toks)
        unique_tokens.update(token_set)
        corpus_token_presence.update(token_set)
        low_text = text.lower()
        if "s 5b(2)(a)" in low_text or "sch 1 cl 4" in low_text:
            legal_atom_total += len(atom_needles)
            legal_atom_hits += sum(1 for needle in atom_needles if needle in token_set)

    overlap = sum(1 for _, seen in corpus_token_presence.items() if seen > 1)
    return {
        "documents": len(texts),
        "total_chars": total_chars,
        "total_tokens": total_tokens,
        "avg_chars_per_token": (total_chars / total_tokens) if total_tokens else 0.0,
        "unique_tokens": len(unique_tokens),
        "unique_ratio": (len(unique_tokens) / total_tokens) if total_tokens else 0.0,
        "reuse_ratio": (1.0 - (len(unique_tokens) / total_tokens)) if total_tokens else 0.0,
        "cross_document_overlap_tokens": overlap,
        "legal_atom_capture_rate": (legal_atom_hits / legal_atom_total) if legal_atom_total else None,
    }


def main() -> None:
    import sys

    if str(SENSIBLAW_ROOT) not in sys.path:
        sys.path.insert(0, str(SENSIBLAW_ROOT))

    corpora = {
        "1_gwb_timeline_prose": _gwb_timeline_texts(),
        "2_legal_fixture_bodies": _legal_fixture_texts(),
        "3_legal_principles_timelines": _legal_principles_texts(),
        "4_mixed_general_and_legal_refs": _mixed_texts(),
    }

    tokenizers: dict[str, Callable[[str], list[str]]] = {
        "deterministic_legal": _deterministic_tokenizer(),
        "legacy_regex": _legacy_tokenizer(),
    }
    spacy_tok = _spacy_tokenizer()
    if spacy_tok is not None:
        tokenizers["spacy"] = spacy_tok
    try:
        tiktoken_tok = _tiktoken_tokenizer()
    except Exception:
        tiktoken_tok = None
    if tiktoken_tok is not None:
        tokenizers["tiktoken_cl100k"] = tiktoken_tok

    out: dict[str, dict] = {}
    for corpus_name, texts in corpora.items():
        out[corpus_name] = {}
        for tok_name, tok_fn in tokenizers.items():
            out[corpus_name][tok_name] = _summarize(texts, tok_fn)

    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
