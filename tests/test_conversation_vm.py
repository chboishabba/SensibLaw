from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sensiblaw.conversation_vm import (  # type: ignore[import-not-found]
    CONTEXT_PAYLOAD_SCHEMA,
    PROOF_SURFACE_SCHEMA,
    STATE_SCHEMA,
    TURN_DELTA_SCHEMA,
    build_context_payload,
    build_proof_surface,
    compile_turn,
    empty_state,
    step_state,
)


def test_compile_turn_preserves_receipted_source_surfaces_and_is_deterministic() -> None:
    turn = {
        "turn_id": "fixture-turn-1",
        "text": "Alpha supports beta. No alpha supports beta.",
        "fact_candidates": [{"kind": "candidate-fact", "text": "Alpha supports beta."}],
    }

    left = compile_turn(turn)
    right = compile_turn(turn)

    assert left == right
    assert left["schema"] == TURN_DELTA_SCHEMA
    assert left["sources"][0]["text"] == turn["text"]
    assert left["excerpts"][0]["text"] == "Alpha supports beta."
    assert left["statements"][0]["receipt_ids"]
    assert left["observations"][0]["status"] == "supported"
    assert left["predicate_atoms"]
    assert left["predicate_pnfs"]
    assert all(
        atom["projection_method"]
        in {
            "sensiblaw.shared_reducer.collect_canonical_relational_bundle",
            "conversation_vm_structural_parser",
        }
        for atom in left["predicate_atoms"]
    )


def test_state_join_preserves_supported_receipts() -> None:
    delta = compile_turn(
        {
            "turn_id": "supported-turn",
            "text": "Alpha supports beta.",
            "fact_candidates": [{"kind": "candidate-fact", "text": "Alpha supports beta."}],
        }
    )

    state = step_state(empty_state(), delta)

    assert state["schema"] == STATE_SCHEMA
    assert state["observations"][0]["status"] == "supported"
    assert state["observations"][0]["receipt_ids"]
    assert state["status_history"]


def test_cross_turn_contradiction_adds_contested_without_deleting_support() -> None:
    positive = {
        "id": "delta-positive",
        "predicate_atoms": [
            {
                "id": "atom-positive",
                "predicate": "claim",
                "arguments": ["alpha"],
                "polarity": "positive",
                "status": "supported",
                "receipt_ids": ["receipt-positive"],
            }
        ],
    }
    negative = {
        "id": "delta-negative",
        "predicate_atoms": [
            {
                "id": "atom-negative",
                "predicate": "claim",
                "arguments": ["alpha"],
                "polarity": "negative",
                "status": "supported",
                "receipt_ids": ["receipt-negative"],
            }
        ],
    }

    state = step_state(step_state(empty_state(), positive), negative)

    assert len(state["predicate_atoms"]) == 2
    assert state["contested_items"]
    assert state["residual_comparisons"][0]["status"] == "contested"
    receipts = set(state["residual_comparisons"][0]["receipt_ids"])
    assert {"receipt-positive", "receipt-negative"} <= receipts


def test_abstained_no_typed_meet_remains_visible() -> None:
    delta = {
        "id": "delta-abstain",
        "abstentions": [
            {
                "id": "abstain-no-meet",
                "status": "abstained",
                "reason": "no-typed-meet",
                "receipt_ids": ["receipt-a"],
            }
        ],
    }

    state = step_state(empty_state(), delta)
    payload = build_context_payload(state)

    assert payload["schema"] == CONTEXT_PAYLOAD_SCHEMA
    assert payload["abstentions"][0]["reason"] == "no-typed-meet"


def test_promotion_without_required_receipts_is_blocked() -> None:
    delta = {
        "id": "delta-promoted-without-receipts",
        "predicate_atoms": [
            {
                "id": "atom-promoted",
                "predicate": "claim",
                "arguments": ["alpha"],
                "polarity": "positive",
                "status": "promoted",
                "receipt_ids": [],
            }
        ],
        "promotion_gates": [
            {
                "id": "gate-source",
                "name": "source_receipt",
                "status": "blocked",
                "receipt_ids": [],
            }
        ],
    }

    state = step_state(empty_state(), delta)

    assert state["blockers"]
    assert state["blockers"][0]["atom_id"] == "atom-promoted"
    assert "source_receipt" in state["blockers"][0]["missing_gates"]


def test_proof_and_context_payloads_preserve_provenance_not_opaque_summary() -> None:
    state = step_state(empty_state(), compile_turn({"turn_id": "query-turn", "text": "Alpha supports beta."}))

    surface = build_proof_surface(state, query="beta")
    context = build_context_payload(state, query="beta")

    assert surface["schema"] == PROOF_SURFACE_SCHEMA
    assert surface["sources"]
    assert surface["excerpts"]
    assert surface["statements"]
    assert context["metadata"]["opaque_summary"] is False
    assert context["items"][0]["atom"]["receipt_ids"]


def test_vm_modules_do_not_add_semantic_regex_policy() -> None:
    for path in (ROOT / "src" / "sensiblaw" / "conversation_vm").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import re" not in text
        assert "from re import" not in text
        assert "regex" not in text.lower()


def test_cli_compile_step_query_roundtrip(tmp_path: Path) -> None:
    turn_path = tmp_path / "turn.json"
    delta_path = tmp_path / "delta.json"
    state_path = tmp_path / "state.json"
    proof_path = tmp_path / "proof.json"
    turn_path.write_text(json.dumps({"turn_id": "cli-turn", "text": "Alpha supports beta."}), encoding="utf-8")

    subprocess.run(
        [sys.executable, "scripts/conversation_vm.py", "compile-turn", "-i", str(turn_path), "-o", str(delta_path)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/conversation_vm.py", "step", "--delta", str(delta_path), "-o", str(state_path)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/conversation_vm.py", "query-surface", "--state", str(state_path), "-q", "beta", "-o", str(proof_path)],
        cwd=ROOT,
        check=True,
    )

    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof["schema"] == PROOF_SURFACE_SCHEMA
    assert proof["predicate_atoms"]
