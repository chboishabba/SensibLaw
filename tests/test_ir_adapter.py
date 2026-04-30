from __future__ import annotations

import importlib

from sensiblaw.interfaces import InteractionMode, QueryTree, build_query_tree, project_interaction_mode
from sensiblaw.interfaces.ir_adapter import build_query_tree, project_interaction_mode
from sensiblaw.interfaces.ir_types import InteractionMode


def test_public_interfaces_import_succeeds_and_preserves_class_identity() -> None:
    imported = importlib.import_module("sensiblaw.interfaces")

    query_tree = imported.build_query_tree("Can you send the report today?")
    receipt = imported.project_interaction_mode(query_tree)

    assert isinstance(query_tree, QueryTree)
    assert isinstance(receipt.interaction_mode, InteractionMode)


def test_build_query_tree_emits_sentence_token_and_structure_nodes() -> None:
    text = "User: please run this.\n$ pytest SensibLaw/tests/test_ir_adapter.py -q\n"

    query_tree = build_query_tree(text)

    sentence_nodes = [node for node in query_tree.nodes if node.kind == "sentence"]
    token_nodes = [node for node in query_tree.nodes if node.kind == "token"]
    structure_nodes = [node for node in query_tree.nodes if node.kind == "structure_marker"]

    assert sentence_nodes
    assert token_nodes
    assert any(node.features.get("kind") == "role_ref" for node in structure_nodes)
    assert any(node.features.get("kind") == "command_ref" for node in structure_nodes)
    assert query_tree.receipts["tree_version"] == "query_tree_v1"
    assert any(edge.kind == "contains" for edge in query_tree.edges)


def test_project_interaction_mode_detects_interrogative() -> None:
    receipt = project_interaction_mode(build_query_tree("What happened here?"))

    assert receipt.interaction_mode == InteractionMode.INTERROGATIVE
    assert receipt.supporting_node_ids


def test_project_interaction_mode_detects_imperative() -> None:
    receipt = project_interaction_mode(build_query_tree("Please send the report today."))

    assert receipt.interaction_mode == InteractionMode.IMPERATIVE
    assert receipt.supporting_signal_ids


def test_project_interaction_mode_detects_directed_request() -> None:
    receipt = project_interaction_mode(build_query_tree("Can you send the report today?"))

    assert receipt.interaction_mode == InteractionMode.DIRECTED_REQUEST
    assert receipt.supporting_node_ids


def test_project_interaction_mode_detects_ambient_greeting() -> None:
    receipt = project_interaction_mode(build_query_tree("Hello there"))

    assert receipt.interaction_mode == InteractionMode.AMBIENT
