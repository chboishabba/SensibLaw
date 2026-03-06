from SensibLaw.scripts.benchmark_tokenizer_corpora import _mixed_texts, _summarize
from src.ontology.entity_bridge import link_lexeme_occurrences
from src.text.lexeme_index import collect_lexeme_occurrences


def _deterministic_tokenizer(text: str) -> list[str]:
    return [occ.norm_text for occ in collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")]


def _legacy_tokenizer(text: str) -> list[str]:
    return [occ.norm_text for occ in collect_lexeme_occurrences(text, canonical_mode="legacy_regex")]


def _deterministic_linked_tokenizer(text: str) -> list[str]:
    occs = collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")
    return [link.curie for link in link_lexeme_occurrences(occs)]


def test_deterministic_benchmark_captures_more_legal_atoms_than_legacy():
    texts = _mixed_texts()
    deterministic = _summarize(texts, _deterministic_tokenizer, _deterministic_linked_tokenizer)
    legacy = _summarize(texts, _legacy_tokenizer)

    assert deterministic["legal_atom_capture_rate"] is not None
    assert legacy["legal_atom_capture_rate"] is not None
    assert deterministic["legal_atom_capture_rate"] > legacy["legal_atom_capture_rate"]
    assert deterministic["linked_entity_capture_rate"] is not None


def test_deterministic_benchmark_captures_gwb_reference_atoms():
    from SensibLaw.scripts.benchmark_tokenizer_corpora import _gwb_reference_texts

    deterministic = _summarize(_gwb_reference_texts(), _deterministic_tokenizer, _deterministic_linked_tokenizer)
    legacy = _summarize(_gwb_reference_texts(), _legacy_tokenizer)

    assert deterministic["legal_atom_capture_rate"] is not None
    assert deterministic["legal_atom_capture_rate"] > 0.0
    assert deterministic["legal_atom_capture_rate"] > legacy["legal_atom_capture_rate"]
    assert deterministic["linked_entity_capture_rate"] is not None
    assert deterministic["linked_entity_capture_rate"] > 0.0
