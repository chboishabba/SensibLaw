from src.ontology.typing_deficit_schema import collect_typing_deficit_signals


def test_collect_typing_deficit_signals_combines_sources() -> None:
    au_payload = {
        "artifact_id": "au.fact_review_bundle:run-1",
        "canonical_identity": {"identity_class": "au_fact_review"},
        "typing_deficit_signals": [
            {"linked_qid": "Q111", "details": "missing P31"},
        ],
    }
    gwb_payload = {
        "artifact_id": "gwb.public_review:1",
        "typing_deficit_signals": [
            {
                "signal_id": "gwb:source:1",
                "linked_seed_id": "seed-1",
                "details": "missing institution type",
            }
        ],
    }
    chat_payload = {
        "source_system": "tircorder-JOBBIE",
        "typing_deficit_signals": [
            {"signal_id": "chat:follow-1", "details": "chat mention of missing instance-of"},
        ],
    }
    signals = collect_typing_deficit_signals([au_payload, gwb_payload, chat_payload])
    assert len(signals) == 3
    assert {"au", "gwb", "chat_history"} <= {signal["source"] for signal in signals}
    assert any(signal.get("linked_qid") == "Q111" for signal in signals)
