from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from src.statibaker_kanban import (
    build_project_context_pnf_index,
    build_runsheet_bridge,
    build_task_memory_index,
    build_task_timeline_probe,
    project_kanban,
)


def _grounding_catalog() -> dict:
    return {
        "groundings": {
            "signup flow": [
                {
                    "grounded_node": "local:signup_flow",
                    "grounded_label": "signup flow",
                    "grounding_residual": "exact_grounding",
                    "topic_closure": [
                        {
                            "topic_id": "local:onboarding",
                            "topic_label": "onboarding",
                            "ontology_path": ["signup flow", "onboarding"],
                            "relation_path": ["local project ontology"],
                            "topic_depth": 1,
                        }
                    ],
                }
            ],
            "pricing wording": [
                {
                    "grounded_node": "local:pricing_copy",
                    "grounded_label": "pricing wording",
                    "grounding_residual": "exact_grounding",
                    "topic_closure": [
                        {
                            "topic_id": "local:pricing",
                            "topic_label": "pricing",
                            "ontology_path": ["pricing wording", "pricing"],
                            "relation_path": ["local project ontology"],
                            "topic_depth": 1,
                        }
                    ],
                }
            ],
        }
    }


def _project_context() -> dict:
    return {
        "context_id": "gamma:test",
        "source_refs": ["project_context_fixture"],
        "context_pnfs": [
            {
                "atom_id": "ctx:schema:todo",
                "predicate_family": "task_schema",
                "structural_signature": "TaskSchemaPNF",
                "lifecycle_effect": "promote_todo",
                "roles": {"lifecycle_effect": "promote_todo"},
            },
            {
                "atom_id": "ctx:schema:progress",
                "predicate_family": "task_schema",
                "structural_signature": "TaskSchemaPNF",
                "lifecycle_effect": "mark_in_progress",
                "roles": {"lifecycle_effect": "mark_in_progress"},
            },
            {
                "atom_id": "ctx:schema:candidate",
                "predicate_family": "task_schema",
                "structural_signature": "TaskSchemaPNF",
                "lifecycle_effect": "create_candidate",
                "roles": {"lifecycle_effect": "create_candidate"},
            },
            {
                "atom_id": "ctx:entity:signup",
                "predicate_family": "project_ontology",
                "structural_signature": "ProjectOntologyPNF",
                "label": "signup flow",
                "roles": {"object": "signup flow", "feature": "signup flow"},
            },
            {
                "atom_id": "ctx:entity:pricing",
                "predicate_family": "project_ontology",
                "structural_signature": "ProjectOntologyPNF",
                "label": "pricing wording",
                "roles": {"object": "pricing wording", "feature": "pricing wording"},
            },
            {
                "atom_id": "ctx:board:signup",
                "predicate_family": "board_state",
                "structural_signature": "TaskCardPNF",
                "task_id": "task_existing_signup",
                "roles": {
                    "task_id": "task_existing_signup",
                    "object": "signup flow",
                    "status": "todo",
                },
            },
        ],
    }


def test_statibaker_kanban_projects_supplied_task_atoms_with_receipts() -> None:
    documents = [
        {
            "doc_id": "dev_chat_2026_05_06",
            "source_type": "transcript",
            "segments": [
                {
                    "segment_id": "dev_chat:s1",
                    "speaker": "SatoshiSpark",
                    "text": "New user can't proceed to confirm email.",
                    "atoms": [
                        {
                            "atom_id": "a1",
                            "predicate": "defect",
                            "task_pnf": {
                                "predicate_family": "state",
                                "action_type": "fix",
                                "lifecycle_effect": "promote_todo",
                                "project_relevant": True,
                                "qualifiers": {"modality": "unresolved"},
                            },
                            "roles": {"object": "signup flow"},
                            "wrapper_state": "asserted_defect",
                            "priority": "high",
                            "acceptance_criteria": "new user reaches confirm-email stage",
                        }
                    ],
                },
                {
                    "segment_id": "dev_chat:s2",
                    "speaker": "Kaus",
                    "text": "Kaus is doing RCA on signup flow.",
                    "atoms": [
                        {
                            "atom_id": "a2",
                            "predicate": "doing",
                            "task_key": "fix:local:signup_flow",
                            "task_pnf": {
                                "predicate_family": "action",
                                "action_type": "fix",
                                "lifecycle_effect": "mark_in_progress",
                                "project_relevant": True,
                            },
                            "roles": {"owner": "Kaus", "object": "signup flow"},
                            "wrapper_state": "committed_in_progress",
                        }
                    ],
                },
            ],
            "provenance": {"source": "dev_chat"},
        }
    ]

    task_index = build_task_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="project_ontology_test",
        project_context=_project_context(),
    )
    board = project_kanban(task_index)

    assert task_index["schema_version"] == "sl.statibaker_task_memory.v0_1"
    assert task_index["authority_boundary"]["raw_keyword_tasking"] is False
    assert task_index["authority_boundary"]["stati_baker_live_mutation"] is False
    assert task_index["authority_boundary"]["local_json_is_canonical"] is True
    assert task_index["authority_boundary"]["kanboard_apply_requires_opt_in"] is True
    assert task_index["authority_boundary"]["kanboard_inbound_sync_enabled"] is False
    assert task_index["authority_boundary"]["two_way_sync_without_conflict_policy"] is False
    assert task_index["authority_boundary"]["secrets_logged"] is False
    assert task_index["task_count"] == 1
    task = task_index["tasks"][0]
    assert task["owner"] == "Kaus"
    assert task["status"] == "in_progress"
    assert task["column"] == "Doing"
    assert task["acceptance_criteria"] == "new user reaches confirm-email stage"
    assert task["evidence_refs"] == ["task_receipt:1", "task_receipt:2"]
    assert task["grounding_refs"][0]["grounded_node"] == "local:signup_flow"
    assert task["context_meet"]["residual"] == "exact"
    assert task_index["project_context"]["schema_version"] == "sl.project_context_pnf_index.v0_1"
    assert board["schema_version"] == "sl.statibaker_kanban_projection.v0_1"
    assert board["authority_boundary"]["kanban_projection_only"] is True
    assert board["authority_boundary"]["local_json_is_canonical"] is True
    assert board["authority_boundary"]["kanboard_apply_requires_opt_in"] is True
    assert board["authority_boundary"]["kanboard_inbound_sync_enabled"] is False
    assert board["authority_boundary"]["two_way_sync_without_conflict_policy"] is False
    assert board["authority_boundary"]["secrets_logged"] is False
    assert len(board["columns"]["Doing"]) == 1
    assert board["columns"]["Doing"][0]["latest_status_event"]["atom_id"] == "a2"


def test_statibaker_kanban_ignores_raw_text_without_task_atoms() -> None:
    documents = [
        {
            "doc_id": "chat_noise",
            "text": "Fucking GitHub. Thanks, good catch.",
            "provenance": {"source": "dev_chat"},
        }
    ]

    task_index = build_task_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="project_ontology_test",
        project_context=_project_context(),
    )
    board = project_kanban(task_index)

    assert task_index["task_count"] == 0
    assert task_index["ignored_segments"] == [
        {
            "doc_id": "chat_noise",
            "segment_id": "chat_noise:s1",
            "reason": "no_supplied_atoms",
        }
    ]
    assert board["card_count"] == 0


def test_statibaker_kanban_holds_candidates_missing_acceptance_or_grounding() -> None:
    documents = [
        {
            "doc_id": "dev_chat_held",
            "segments": [
                {
                    "segment_id": "dev_chat_held:s1",
                    "text": "Need to update pricing wording after signups are fixed.",
                    "atoms": [
                        {
                            "atom_id": "a1",
                            "predicate": "obligation",
                            "task_pnf": {
                                "predicate_family": "action",
                                "action_type": "update",
                                "lifecycle_effect": "promote_todo",
                                "project_relevant": True,
                            },
                            "roles": {
                                "object": "pricing wording",
                                "dependency": "signup flow fixed",
                            },
                            "wrapper_state": "requested",
                            "qualifiers": {"after": "signup flow fixed"},
                        }
                    ],
                },
                {
                    "segment_id": "dev_chat_held:s2",
                    "text": "Maybe investigate the mystery integration later.",
                    "atoms": [
                        {
                            "atom_id": "a2",
                            "predicate": "investigation",
                            "task_pnf": {
                                "predicate_family": "followup",
                                "action_type": "investigate",
                                "lifecycle_effect": "create_candidate",
                                "project_relevant": True,
                            },
                            "roles": {"object": "mystery integration"},
                            "wrapper_state": "speculative",
                        }
                    ],
                },
            ],
        }
    ]

    task_index = build_task_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="project_ontology_test",
        project_context=_project_context(),
    )
    board = project_kanban(task_index)

    assert task_index["task_count"] == 2
    pricing = next(task for task in task_index["tasks"] if task["object"] == "pricing wording")
    assert pricing["status"] == "held"
    assert pricing["hold_reasons"] == ["missing_acceptance_criteria"]
    assert pricing["dependencies"] == ["signup flow fixed"]
    mystery = next(task for task in task_index["tasks"] if task["object"] == "mystery integration")
    assert mystery["promotion_status"] == "held_for_review"
    assert mystery["hold_reasons"] == [
        "context:no_context_entity_meet",
        "missing_grounding",
        "wrapper:speculative",
    ]
    assert len(board["columns"]["Held"]) == 2


def test_statibaker_kanban_rejects_keyword_like_atoms_without_structural_transition() -> None:
    documents = [
        {
            "doc_id": "anti_list",
            "segments": [
                {
                    "segment_id": "anti_list:s1",
                    "text": "not a TODO; that was a good fix",
                    "atoms": [
                        {
                            "atom_id": "a1",
                            "predicate": "todo",
                            "task_like": True,
                            "roles": {"object": "signup flow"},
                            "wrapper_state": "requested",
                            "qualifiers": {"polarity": "negated"},
                        },
                        {
                            "atom_id": "a2",
                            "predicate": "fix",
                            "task_pnf": {
                                "predicate_family": "evidence_only",
                                "action_type": "fix",
                                "lifecycle_effect": "no_task_transition",
                                "project_relevant": True,
                                "qualifiers": {"tense": "past"},
                            },
                            "roles": {"object": "signup flow"},
                            "wrapper_state": "historical",
                        },
                    ],
                }
            ],
        }
    ]

    task_index = build_task_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="project_ontology_test",
        project_context=_project_context(),
    )

    assert task_index["task_count"] == 0
    reasons = {
        row["atom_id"]: row["tasklike_rejection_reasons"]
        for row in task_index["ignored_segments"]
        if row.get("atom_id")
    }
    assert reasons["a1"] == [
        "closed_or_negated",
        "missing_lifecycle_transition",
        "missing_task_pnf",
    ]
    assert reasons["a2"] == [
        "closed_or_negated",
        "missing_lifecycle_transition",
        "non_promotable_wrapper",
    ]
    assert task_index["authority_boundary"]["tasklike_is_structural"] is True
    assert task_index["authority_boundary"]["project_context_is_pnf_indexed"] is True
    assert task_index["authority_boundary"]["keyword_presence_neither_necessary_nor_sufficient"] is True


def test_project_context_pnf_index_is_explicit_gamma_surface() -> None:
    gamma = build_project_context_pnf_index(_project_context())

    assert gamma["schema_version"] == "sl.project_context_pnf_index.v0_1"
    assert gamma["context_id"] == "gamma:test"
    assert gamma["receipt_policy"] == "no_fabricated_PNFEmissionReceipt"
    assert gamma["authority_policy"] == "review_only"
    assert gamma["structural_signature_index"]["TaskSchemaPNF"] == [
        "ctx:schema:todo",
        "ctx:schema:progress",
        "ctx:schema:candidate",
    ]
    assert "object:signup flow" in gamma["role_arg_index"]
    assert gamma["authority_boundary"]["context_is_not_hand_blob"] is True


def test_tasklike_requires_gamma_meet_not_project_relevant_blob() -> None:
    documents = [
        {
            "doc_id": "gamma_meet",
            "segments": [
                {
                    "segment_id": "gamma_meet:s1",
                    "text": "Can someone check the signup flow?",
                    "atoms": [
                        {
                            "atom_id": "a1",
                            "predicate": "check",
                            "task_pnf": {
                                "predicate_family": "action",
                                "action_type": "verify",
                                "lifecycle_effect": "create_candidate",
                            },
                            "roles": {"object": "signup flow"},
                            "wrapper_state": "requested",
                        }
                    ],
                }
            ],
        }
    ]

    task_index = build_task_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="project_ontology_test",
        project_context=_project_context(),
    )

    assert task_index["task_count"] == 1
    task = task_index["tasks"][0]
    assert task["context_meet"]["residual"] == "exact"
    assert task["status"] == "candidate"
    assert task["promotion_status"] == "promoted_candidate_card"
    assert task["hold_reasons"] == []


def test_statibaker_kanban_runs_archive_query_freetext_probe_fixture() -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "statibaker_kanban"
        / "archive_freetext_probe_v0_1.json"
    )
    fixture = json.loads(fixture_path.read_text())

    task_index = build_task_memory_index(
        documents=fixture["documents"],
        grounding_catalog=fixture["grounding_catalog"],
        ontology_snapshot_id=fixture["ontology_snapshot_id"],
        project_context=fixture["project_context"],
    )
    board = project_kanban(task_index)

    expected = fixture["expected"]
    assert task_index["task_count"] == expected["task_count"]
    task = task_index["tasks"][0]
    assert fixture["documents"][0]["segments"][0]["text"] == "What are our blockers?\nHow can we move forwards?"
    assert task["object"] == expected["object"]
    assert task["status"] == expected["status"]
    assert task["column"] == expected["column"]
    assert task["priority"] == "high"
    assert task["context_meet"]["residual"] == expected["context_residual"]
    assert task["promotion_status"] == "promoted_candidate_card"
    assert board["columns"]["Inbox"][0]["card_id"] == task["task_id"]


def test_statibaker_kanban_archive_thread_timeline_probe_is_bidirectional() -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "statibaker_kanban"
        / "archive_thread_timeline_probe_v0_1.json"
    )
    fixture = json.loads(fixture_path.read_text())

    probe = build_task_timeline_probe(
        timeline_cases=fixture["timeline_cases"],
        source=fixture["source"],
    )

    expected = fixture["expected"]
    assert probe["schema_version"] == "sl.statibaker_task_timeline_probe.v0_1"
    assert probe["timeline_count"] == expected["timeline_count"]
    assert probe["summary"]["with_prior_evidence"] == expected["with_prior_evidence"]
    assert probe["summary"]["with_later_evidence"] == expected["with_later_evidence"]
    assert probe["summary"]["with_successors"] == expected["with_successors"]
    assert probe["authority_boundary"]["task_timeline_is_bidirectional"] is True
    assert probe["authority_boundary"]["seed_is_not_assumed_origin"] is True
    assert probe["authority_boundary"]["live_archive_query"] is False

    timelines_by_title = {timeline["task_title"]: timeline for timeline in probe["timelines"]}
    phase4 = timelines_by_title["Resolve Phase-4 readiness blockers"]
    assert phase4["prior_event_receipts"][0]["event_type"] == "prior_context"
    assert phase4["seed_role"] == "blocker_diagnosis_request"
    assert phase4["later_event_receipts"][-1]["event_type"] == "blocked"
    assert phase4["final_task_status"] == "progressed_to_blocker_diagnosis"
    assert phase4["task_identity_residual"] == "exact"
    assert phase4["lifecycle_residual"] == "exact"

    d0 = timelines_by_title["Write D0 execution model"]
    assert d0["final_task_status"] == "closed_with_successors"
    assert {task["title"] for task in d0["successor_tasks"]} == {
        "Create D1 checklist",
        "Write Day 1/2/3 plan",
        "Add JS pass/fail tests",
    }
    assert "spawned_successor" in d0["task_graph_effects"]

    learnable = timelines_by_title["Review learnable weight diff"]
    assert learnable["final_task_status"] == "completed_then_spawned_blocked_successor"
    assert learnable["successor_tasks"] == [
        {
            "title": "Unlock option tenor/moneyness",
            "status": "blocked",
            "blocker": "option-empty tape",
        }
    ]
    assert "blocked" in learnable["task_graph_effects"]
    assert learnable["missing_expected_slots"] == ["option_tape_available"]

    market = timelines_by_title["Fact check market sentiment claims"]
    assert market["final_task_status"] == "answered_once_no_same_thread_continuation"
    assert market["missing_expected_slots"] == ["same_thread_followup"]
    assert market["lifecycle_residual"] == "incomplete"


def test_runsheet_bridge_maps_task_and_timeline_into_dashboard_statuses() -> None:
    documents = [
        {
            "doc_id": "runsheet_doc",
            "segments": [
                {
                    "segment_id": "runsheet_doc:s1",
                    "speaker": "owner",
                    "text": "Fix signup flow now.",
                    "atoms": [
                        {
                            "atom_id": "rs:a1",
                            "task_key": "fix:local:signup_flow",
                            "predicate": "defect",
                            "task_pnf": {
                                "predicate_family": "action",
                                "action_type": "fix",
                                "lifecycle_effect": "mark_in_progress",
                                "project_relevant": True,
                            },
                            "roles": {"object": "signup flow", "owner": "Kaus"},
                            "wrapper_state": "committed_in_progress",
                            "acceptance_criteria": "signup flow restored",
                        }
                    ],
                }
            ],
        }
    ]
    task_index = build_task_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="project_ontology_test",
        project_context=_project_context(),
    )
    board = project_kanban(task_index)
    timeline_probe = build_task_timeline_probe(
        timeline_cases=[
            {
                "timeline_id": "timeline:signup",
                "task_id": "task:1",
                "task_title": "Fix signup flow",
                "seed_message_receipt": {
                    "lifecycle_event_type": "seed_candidate",
                    "residual": "exact",
                },
                "later_event_receipts": [
                    {
                        "lifecycle_event_type": "blocked",
                        "residual": "exact",
                        "status_after": "blocked_on_dependency",
                        "task_graph_effects": ["blocked"],
                    }
                ],
                "lifecycle_residual": "exact",
            }
        ]
    )
    bridge = build_runsheet_bridge(
        task_memory_index=task_index,
        kanban_projection=board,
        timeline_probe=timeline_probe,
        source={"fixture": "runsheet_bridge"},
    )

    assert bridge["schema_version"] == "sl.statibaker_runsheet_bridge.v0_1"
    assert bridge["status_counts"]["blocked"] == 1
    assert bridge["heartbeat"] == {"completed_items": 0, "total_items": 1}
    item = bridge["items"][0]
    assert item["id"] == "task:1"
    assert item["status"] == "blocked"
    assert item["timeline_ref"] == "timeline:signup"
    assert item["context_residual"] == "exact"
    assert item["evidence_refs"] == ["task_receipt:1"]
    assert bridge["boundary_gaps"]["unmatched_timeline_count"] == 0
    assert bridge["authority_boundary"]["no_keyword_only_promotion"] is True


def test_runsheet_bridge_reports_unmatched_timeline_boundary_gap() -> None:
    task_index = build_task_memory_index(
        documents=[],
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="project_ontology_test",
        project_context=_project_context(),
    )
    timeline_probe = build_task_timeline_probe(
        timeline_cases=[
            {
                "timeline_id": "timeline:orphan",
                "task_id": "task:orphan",
                "task_title": "Orphan timeline task",
                "seed_message_receipt": {"lifecycle_event_type": "seed_candidate"},
            }
        ]
    )

    bridge = build_runsheet_bridge(
        task_memory_index=task_index,
        timeline_probe=timeline_probe,
    )

    assert bridge["items"] == []
    assert bridge["boundary_gaps"]["missing_kanban_projection"] is True
    assert bridge["boundary_gaps"]["missing_timeline_probe"] is False
    assert bridge["boundary_gaps"]["unmatched_timeline_count"] == 1
    assert bridge["boundary_gaps"]["unmatched_timeline_receipts"][0]["timeline_id"] == "timeline:orphan"


def test_runsheet_bridge_feeds_statibaker_kanboard_dry_run_shape() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    statibaker_root = str(repo_root / "StatiBaker")
    if statibaker_root not in sys.path:
        sys.path.insert(0, statibaker_root)
    from sb.kanboard_runsheet import build_dry_run_plan, load_local_rows

    documents = [
        {
            "doc_id": "bridge_doc",
            "segments": [
                {
                    "segment_id": "bridge_doc:s1",
                    "speaker": "owner",
                    "text": "Fix signup flow now.",
                    "atoms": [
                        {
                            "atom_id": "rs:a1",
                            "task_key": "fix:local:signup_flow",
                            "predicate": "defect",
                            "task_pnf": {
                                "predicate_family": "action",
                                "action_type": "fix",
                                "lifecycle_effect": "mark_in_progress",
                                "project_relevant": True,
                            },
                            "roles": {"object": "signup flow", "owner": "Kaus"},
                            "wrapper_state": "committed_in_progress",
                            "acceptance_criteria": "signup flow restored",
                        }
                    ],
                }
            ],
        }
    ]
    task_index = build_task_memory_index(
        documents=documents,
        grounding_catalog=_grounding_catalog(),
        ontology_snapshot_id="project_ontology_test",
        project_context=_project_context(),
    )
    board = project_kanban(task_index)
    timeline_probe = build_task_timeline_probe(
        timeline_cases=[
            {
                "timeline_id": "timeline:signup",
                "task_id": "task:1",
                "task_title": "Fix signup flow",
                "canonical_thread_id": "thread:signup",
                "seed_message_receipt": {
                    "source_message_id": "msg:signup:seed",
                    "lifecycle_event_type": "seed_candidate",
                    "residual": "exact",
                },
                "later_event_receipts": [
                    {
                        "source_message_id": "msg:signup:later",
                        "lifecycle_event_type": "blocked",
                        "residual": "exact",
                        "status_after": "blocked_on_dependency",
                        "task_graph_effects": ["blocked"],
                    }
                ],
                "task_identity_residual": "exact",
                "lifecycle_residual": "exact",
            }
        ]
    )
    bridge = build_runsheet_bridge(
        task_memory_index=task_index,
        kanban_projection=board,
        timeline_probe=timeline_probe,
        source={"orchestrator_id": "runner-bridge", "lane": "lane-5", "fixture": "bridge_dry_run"},
    )

    assert bridge["runsheet"]["items"][0]["stable_id"] == "task:1"
    assert bridge["runsheet"]["items"][0]["lifecycle_residual"] == "exact"
    assert bridge["runsheet"]["items"][0]["task_identity_residual"] == "exact"

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
        json.dump(bridge, handle)
        handle.flush()
        loaded = load_local_rows(handle.name)

    rows = loaded["rows"]
    assert len(rows) == 1
    assert rows[0]["stable_id"] == "task:1"
    assert rows[0]["status"] == "blocked"
    assert rows[0]["runner_id"] == "runner-bridge"
    assert rows[0]["lane"] == "lane-5"
    assert rows[0]["source"] == "statibaker_task_memory"
    assert rows[0]["canonical_thread_id"] == "thread:signup"
    assert rows[0]["source_message_id"] == "msg:signup:seed"
    assert rows[0]["lifecycle_residual"] == "exact"
    assert rows[0]["task_identity_residual"] == "exact"

    column_map = {
        "todo": {"column_id": 1, "column_name": "Backlog"},
        "in_progress": {"column_id": 2, "column_name": "Doing"},
        "blocked": {"column_id": 3, "column_name": "Blocked"},
        "done": {"column_id": 4, "column_name": "Done"},
        "skipped": {"column_id": 5, "column_name": "Skipped"},
    }
    plan = build_dry_run_plan(
        rows,
        project_id=1,
        now_iso="2026-05-20T00:00:00Z",
        column_by_status=column_map,
    )

    assert plan["schema_version"] == "sb.kanboard_dry_run.v0_1"
    assert plan["task_count"] == 1
    assert plan["progress"] == {"completed": 0, "total": 1}
    metadata_ops = [op for op in plan["operations"] if op["op"] == "metadata"]
    assert len(metadata_ops) == 1
    metadata = metadata_ops[0]["rpc"]["params"]["values"]
    assert metadata["statibaker.lifecycle_residual"] == "exact"
    assert metadata["statibaker.task_identity_residual"] == "exact"
    assert metadata["statibaker.canonical_thread_id"] == "thread:signup"
    assert metadata["statibaker.source_message_id"] == "msg:signup:seed"
