from src.repro.ledger import CorrectionLedger


def test_append_and_list(tmp_path):
    ledger_file = tmp_path / "corrections.csv"
    ledger = CorrectionLedger(ledger_file)
    ledger.append("First", "alice", date="2024-01-01")
    ledger.append("Second", "bob", date="2024-01-02")
    entries = ledger.list_entries()
    assert len(entries) == 2
    assert entries[0].description == "First"
    assert entries[0].author == "alice"
    assert entries[1].author == "bob"
