from src.runtime.candidate_transition_churn import assess_candidate_transition_churn


def _table(name: str, total: int, live: int = 0) -> dict[str, object]:
    return {
        "table_name": name,
        "total_mutations": total,
        "live_rows_after": live,
    }


def test_candidate_transition_receipt_preserves_authority_rows() -> None:
    receipt = assess_candidate_transition_churn(
        {
            "tables": [
                _table("semantic_pnf_demand_candidate", 40),
                _table("semantic_pnf_candidate_execution_event", 40),
                _table("semantic_pnf_demand_candidate_observation", 40),
                _table("semantic_pnf_candidate_current_execution", 40, 5),
            ]
        }
    )
    assert receipt.authority_transition_rows_preserved is True
    assert receipt.transition_to_retained_ratio == 8.0
    assert receipt.current_projection_write_ratio == 1.0


def test_candidate_transition_receipt_detects_missing_history_rows() -> None:
    receipt = assess_candidate_transition_churn(
        {
            "tables": [
                _table("semantic_pnf_demand_candidate", 40),
                _table("semantic_pnf_candidate_execution_event", 39),
                _table("semantic_pnf_demand_candidate_observation", 40),
                _table("semantic_pnf_candidate_current_execution", 20, 5),
            ]
        }
    )
    assert receipt.authority_transition_rows_preserved is False
    assert receipt.current_projection_write_ratio == 0.5
