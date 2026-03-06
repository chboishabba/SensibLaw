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


def _gwb_reference_texts() -> list[str]:
    payload = _load_json(ROOT / "SensibLaw" / ".cache_local" / "wiki_timeline_gwb.json")
    markers = (
        "Act",
        "Court of Appeals",
        "Supreme Court",
        "Agreement",
        "Framework",
        "UN ",
        "United Nations",
        "Security Council",
        "ICC",
        "ICJ",
    )
    out: list[str] = []
    for ev in payload.get("events", []):
        text = str(ev.get("text") or "").strip()
        if text and any(marker in text for marker in markers):
            out.append(text)
    return out


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
        "Bush signed the Military Commissions Act of 2006 into law.",
        "The ruling was vacated by the United States Court of Appeals for the Sixth Circuit.",
        "The outcome eventually reached the U.S. Supreme Court.",
        "Plaintiff S157/2002 v Commonwealth [2003] HCA 2 considered s 75(v) of the Constitution and Art 5 of a hypothetical instrument.",
        "The India–United States Civil Nuclear Agreement followed negotiations after the U.S.–DPRK Agreed Framework.",
        "UN inspectors briefed the United Nations Security Council while the ICC monitored public reporting.",
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


def _deterministic_linked_tokenizer() -> Callable[[str], list[str]]:
    from src.ontology.entity_bridge import link_lexeme_occurrences
    from src.text.lexeme_index import collect_lexeme_occurrences

    def inner(text: str) -> list[str]:
        occs = collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")
        return [link.curie for link in link_lexeme_occurrences(occs)]

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


def _atom_expectations() -> list[tuple[str, list[str], list[str]]]:
    return [
        (
            "s 5b(2)(a)",
            [
                "act:civil_liability_act_2002_nsw",
                "sec:5b",
                "subsec:2",
                "para:a",
            ],
            [],
        ),
        (
            "sch 1 cl 4",
            [
                "sch:1",
                "cl:4",
                "rule:7.32",
            ],
            [],
        ),
        (
            "military commissions act of 2006",
            [
                "act:military_commissions_act_of_2006",
            ],
            [],
        ),
        (
            "united states court of appeals for the sixth circuit",
            [
                "court:united_states_court_of_appeals_for_the_sixth_circuit",
            ],
            [],
        ),
        (
            "u.s. supreme court",
            [
                "court:u_s_supreme_court",
            ],
            [],
        ),
        (
            "s 75(v)",
            [
                "sec:75",
                "para:v",
            ],
            [],
        ),
        (
            "art 5",
            [
                "art:5",
            ],
            [],
        ),
        (
            "civil nuclear agreement",
            [
                "instrument:india_united_states_civil_nuclear_agreement",
            ],
            [],
        ),
        (
            "agreed framework",
            [
                "instrument:u_s_dprk_agreed_framework",
            ],
            [],
        ),
        (
            "un inspectors",
            [
                "institution:united_nations",
            ],
            [
                "wikidata:Q1065",
            ],
        ),
        (
            "security council",
            [
                "institution:united_nations_security_council",
            ],
            [
                "wikidata:Q37470",
            ],
        ),
        (
            "icc",
            [
                "court:international_criminal_court",
            ],
            [
                "wikidata:Q47488",
            ],
        ),
    ]


def _summarize(
    texts: list[str],
    tokenize: Callable[[str], list[str]],
    linked_tokenize: Callable[[str], list[str]] | None = None,
) -> dict:
    total_chars = sum(len(t) for t in texts)
    total_tokens = 0
    unique_tokens: set[str] = set()
    corpus_token_presence: Counter[str] = Counter()
    legal_atom_hits = 0
    legal_atom_total = 0
    linked_entity_hits = 0
    linked_entity_total = 0
    atom_expectations = _atom_expectations()

    for text in texts:
        toks = tokenize(text)
        total_tokens += len(toks)
        token_set = set(toks)
        linked_set = set(linked_tokenize(text)) if linked_tokenize is not None else set()
        unique_tokens.update(token_set)
        corpus_token_presence.update(token_set)
        low_text = text.lower()
        for marker, needles, linked_needles in atom_expectations:
            if marker in low_text:
                legal_atom_total += len(needles)
                legal_atom_hits += sum(1 for needle in needles if needle in token_set)
                linked_entity_total += len(linked_needles)
                linked_entity_hits += sum(1 for needle in linked_needles if needle in linked_set)

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
        "linked_entity_capture_rate": (linked_entity_hits / linked_entity_total) if linked_entity_total else None,
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
        "5_gwb_reference_texts": _gwb_reference_texts(),
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
    linked_det = _deterministic_linked_tokenizer()
    for corpus_name, texts in corpora.items():
        out[corpus_name] = {}
        for tok_name, tok_fn in tokenizers.items():
            linked_fn = linked_det if tok_name == "deterministic_legal" else None
            out[corpus_name][tok_name] = _summarize(texts, tok_fn, linked_fn)

    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
