from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "certify_c3b_minimal_fixture.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_c3b_fixture_harness_is_two_phase_and_minimal() -> None:
    source = _source()
    assert 'subparsers.add_parser("baseline")' in source
    assert 'subparsers.add_parser("certify")' in source
    assert "run_streaming_spacy_execution(" in source
    assert "worker_count=1" in source
    assert "FIXTURE_TEXT" in source
    assert "region.region_kind = 3" in source


def test_baseline_requires_transport_but_rejects_delta_fed_reducer() -> None:
    source = _source()
    assert "_boundary_transport_is_complete" in source
    assert "_reducer_is_delta_fed" in source
    assert "migrations 074 and 075" in source
    assert "before migration 076" in source


def test_certification_requires_076_and_uses_existing_rollback_probe() -> None:
    source = _source()
    assert "benchmark_delta_fed_canonical_parent_reducer(" in source
    assert "C3b certification requires migration 076" in source
    assert 'probe["authority"]["probe_transaction_rolled_back"]' in source
    assert 'probe["authority_parity"]["equal"]' in source


def test_certification_gates_zero_boundary_mismatch_and_rescan() -> None:
    source = _source()
    assert 'probe["boundary"]["missing_from_projection"]' in source
    assert 'probe["boundary"]["extra_in_projection"]' in source
    assert 'probe["work_shape"]["source_token_rescan_count"]' in source
    assert '"canonical_authority_promotion_claimed": False' in source


def test_harness_does_not_mutate_or_reconstruct_canonical_authority() -> None:
    source = _source().casefold()
    assert "rebuild_numeric_pnf_parent_frontier" in source  # only function-definition inspection
    assert "insert into execution.semantic_pnf_interface_export" not in source
    assert "delete from execution.semantic_pnf_interface_export" not in source
    assert "update execution.semantic_pnf_interface_export" not in source
    assert "seed_numeric_pnf_parent_delta_projection" not in source
