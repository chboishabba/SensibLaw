from pathlib import Path

from scripts.validate_integrity import (
    validate_cultural_flag_references,
    validate_legal_source_citations,
)


def test_legal_source_citations_are_unique() -> None:
    assert not validate_legal_source_citations(Path("data/corpus"))


def test_cultural_flags_have_rules() -> None:
    assert not validate_cultural_flag_references(
        corpus_dir=Path("data/corpus"),
        flags_path=Path("data/cultural_flags.yaml"),
        rules_path=Path("data/cultural_rules.yaml"),
    )
