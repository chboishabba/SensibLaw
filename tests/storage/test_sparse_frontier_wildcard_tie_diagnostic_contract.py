from pathlib import Path


ROOT = Path(__file__).parents[2]
SOURCE = (ROOT / "scripts/diagnose_sparse_frontier_wildcard_ties.py").read_text()


def test_tie_probe_is_read_only_and_scoped():
    assert "SET TRANSACTION READ ONLY" in SOURCE
    assert "provider_io_performed" in SOURCE
    assert "semantic_mutation_performed" in SOURCE
    assert "CREATE TEMP" not in SOURCE
    assert "INSERT INTO execution." not in SOURCE
    assert "UPDATE execution." not in SOURCE
    assert "DELETE FROM execution." not in SOURCE


def test_tie_probe_preserves_legacy_tie_observability():
    assert "max(last_end_char)" in SOURCE
    assert "count(DISTINCT candidate_score)" in SOURCE
    assert "score_spread" in SOURCE
    assert "coordinate_values" in SOURCE


def test_tie_probe_does_not_choose_a_representative():
    assert "ORDER BY score_spread DESC" in SOURCE
    assert "DISTINCT ON" not in SOURCE
    assert "row_number" not in SOURCE


def test_tie_probe_has_durable_receipt_contract():
    assert "CONTRACT_REF" in SOURCE
    assert "--output" in SOURCE
    assert "write_text" in SOURCE
