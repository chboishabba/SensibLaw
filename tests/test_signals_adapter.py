from __future__ import annotations

import importlib

from sensiblaw.interfaces.parser_adapter import (
    collect_canonical_operational_structure_occurrences,
    parse_canonical_text,
)
from sensiblaw.interfaces.signals import (
    SIGNAL_STATE_VERSION,
    SignalAtom,
    SignalState,
    collect_signal_state,
    extract_interaction_signals,
    summarize_signal_state,
)


def test_public_package_import_exposes_signals_surface() -> None:
    imported = importlib.import_module("sensiblaw.interfaces")

    assert imported.SignalState is SignalState
    assert imported.SignalAtom is SignalAtom
    assert imported.extract_interaction_signals is extract_interaction_signals
    assert imported.collect_signal_state is collect_signal_state


def test_extract_interaction_signals_emits_interrogative_for_question() -> None:
    atoms = extract_interaction_signals("What is DeFi?")
    labels = {atom.label for atom in atoms}

    assert "interrogative" in labels
    assert "question_marker" in labels
    assert "wh_interrogative" in labels
    assert all(atom.family == "interaction" for atom in atoms)


def test_collect_signal_state_projects_directed_request_from_direct_address_plus_imperative() -> None:
    state = collect_signal_state(
        "Alice, explain the process.",
        include_families=("interaction", "directness", "audience", "uncertainty"),
    )
    summary = summarize_signal_state(state)

    assert summary["interaction"][-1] == "directed_request"
    assert "explicit_address" in summary["directness"]
    assert "single_recipient" in summary["audience"]
    assert state.version == SIGNAL_STATE_VERSION


def test_collect_signal_state_marks_group_addressable_ambient_greeting() -> None:
    state = collect_signal_state(
        "hello everyone",
        include_families=("interaction", "audience", "uncertainty"),
    )
    summary = summarize_signal_state(state)

    assert "ambient" in summary["interaction"]
    assert "group_addressable" in summary["audience"]
    assert "low_evidence" not in summary["uncertainty"]


def test_collect_signal_state_marks_targeted_other_without_route_claim() -> None:
    state = collect_signal_state(
        "say hi to avatar",
        include_families=("interaction", "directness", "audience", "uncertainty"),
    )
    summary = summarize_signal_state(state)

    assert "imperative" in summary["interaction"]
    assert "speech_act_request" in summary["directness"]
    assert "targeted_other" in summary["audience"]
    assert all("route" not in atom.label for atoms in state.families.values() for atom in atoms)


def test_collect_signal_state_accepts_reused_parsed_and_structural_inputs() -> None:
    text = "Q: Explain the steps.\nUser: please help.\n"
    parsed = parse_canonical_text(text)
    structural = collect_canonical_operational_structure_occurrences(text)

    state = collect_signal_state(
        text,
        include_families=("interaction", "directness", "audience", "uncertainty"),
        parsed=parsed,
        structural_occurrences=structural,
    )
    summary = summarize_signal_state(state)

    assert "qa_turn" in summary["interaction"]
    assert "imperative" in summary["interaction"] or "directed_request" in summary["interaction"]
    assert isinstance(state, SignalState)
    assert all(isinstance(atom, SignalAtom) for atoms in state.families.values() for atom in atoms)


def test_collect_signal_state_marks_low_evidence_for_plain_statement() -> None:
    state = collect_signal_state(
        "The market opened lower today.",
        include_families=("interaction", "directness", "audience", "uncertainty"),
    )
    summary = summarize_signal_state(state)

    assert "statement" in summary["interaction"]
    assert "low_evidence" in summary["uncertainty"]
