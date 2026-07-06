from __future__ import annotations

from src.policy.cross_source_event_braid import build_cross_source_event_braid


def _row(
    *,
    source_family: str,
    doc_id: str,
    event_id: str,
    local_order_index: int,
    text: str,
    predicate_key: str = "",
    participants: list[tuple[str, str]] | None = None,
    legal_refs: list[str] | None = None,
) -> dict:
    event_roles = []
    relation_candidates = []
    participants = participants or []
    legal_refs = legal_refs or []
    for role_kind, canonical_key in participants:
        event_roles.append(
            {
                "role_kind": role_kind,
                "entity": {
                    "entity_kind": "actor" if canonical_key.startswith("actor:") else "legal_ref",
                    "canonical_key": canonical_key,
                    "canonical_label": canonical_key,
                },
            }
        )
    for legal_ref in legal_refs:
        event_roles.append(
            {
                "role_kind": "theme",
                "entity": {
                    "entity_kind": "legal_ref",
                    "canonical_key": legal_ref,
                    "canonical_label": legal_ref,
                },
            }
        )
    if predicate_key:
        subject_key = next((key for _, key in participants if key.startswith("actor:")), "actor:george_w_bush")
        object_key = legal_refs[0] if legal_refs else next((key for _, key in participants if key != subject_key), subject_key)
        relation_candidates.append(
            {
                "predicate_key": predicate_key,
                "subject": {
                    "entity_kind": "actor",
                    "canonical_key": subject_key,
                    "canonical_label": subject_key,
                },
                "object": {
                    "entity_kind": "legal_ref" if object_key.startswith("legal_ref:") else "actor",
                    "canonical_key": object_key,
                    "canonical_label": object_key,
                },
            }
        )
    return {
        "source_family": source_family,
        "doc_id": doc_id,
        "doc_title": doc_id,
        "event_id": event_id,
        "source_event_key": f"{source_family}:{event_id}",
        "local_order_index": local_order_index,
        "anchor": {"text": "2026-01-01"},
        "text": text,
        "source_path": f"/tmp/{doc_id}.txt",
        "source_url": "",
        "source_id": doc_id,
        "citation_refs": [],
        "event_roles": event_roles,
        "relation_candidates": relation_candidates,
        "promoted_relations": relation_candidates,
        "candidate_only_relations": [],
        "abstained_relation_candidates": [],
        "mentions": [],
    }


def test_cross_source_event_braid_promotes_overlap_and_cross_document_ordering() -> None:
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [
            _row(source_family="family_a", doc_id="doc_a", event_id="A", local_order_index=0, text="A meeting"),
            _row(source_family="family_a", doc_id="doc_a", event_id="B", local_order_index=1, text="B briefing"),
            _row(
                source_family="family_a",
                doc_id="doc_a",
                event_id="C1",
                local_order_index=2,
                text="Bush signed the education act",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
                legal_refs=["legal_ref:education_act"],
            ),
            _row(
                source_family="family_a",
                doc_id="doc_a",
                event_id="D1",
                local_order_index=3,
                text="Bush nominated a justice",
                predicate_key="nominated",
                participants=[("agent", "actor:george_w_bush"), ("theme", "actor:harriet_miers")],
            ),
        ],
    }
    family_b = {
        "source_family": "family_b",
        "source_event_rows": [
            _row(
                source_family="family_b",
                doc_id="doc_b",
                event_id="C2",
                local_order_index=0,
                text="George W. Bush signed the education act",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
                legal_refs=["legal_ref:education_act"],
            ),
            _row(
                source_family="family_b",
                doc_id="doc_b",
                event_id="D2",
                local_order_index=1,
                text="George W. Bush nominated Harriet Miers",
                predicate_key="nominated",
                participants=[("agent", "actor:george_w_bush"), ("theme", "actor:harriet_miers")],
            ),
            _row(source_family="family_b", doc_id="doc_b", event_id="E", local_order_index=2, text="E hearing"),
            _row(source_family="family_b", doc_id="doc_b", event_id="F", local_order_index=3, text="F vote"),
        ],
    }

    payload = build_cross_source_event_braid([family_a, family_b])

    merged_event_sets = {frozenset(row["source_event_ids"]) for row in payload["merged_events"]}
    assert frozenset({"family_a:C1", "family_b:C2"}) in merged_event_sets
    assert frozenset({"family_a:D1", "family_b:D2"}) in merged_event_sets
    assert any("local_document_order" in row["support_basis"] for row in payload["ordering_edges"])
    assert any(
        row["source_event_id"] == "family_a:D1"
        and row["target_event_id"] == "family_b:E"
        and "inferred_from_source_backed_overlap" in row["support_basis"]
        for row in payload["ordering_edges"]
    )


def test_cross_source_event_braid_keeps_text_only_similarity_candidate_only() -> None:
    payload = build_cross_source_event_braid(
        [
            {
                "source_family": "family_a",
                "source_event_rows": [
                    _row(
                        source_family="family_a",
                        doc_id="doc_a",
                        event_id="A",
                        local_order_index=0,
                        text="Bush discussed national security strategy in a speech",
                    )
                ],
            },
            {
                "source_family": "family_b",
                "source_event_rows": [
                    _row(
                        source_family="family_b",
                        doc_id="doc_b",
                        event_id="B",
                        local_order_index=0,
                        text="National security strategy speech remarks were described later",
                    )
                ],
            },
        ]
    )

    assert payload["merged_events"] == []
    assert any(row["promotion_status"] == "candidate" for row in payload["candidate_links"])


def test_cross_source_event_braid_does_not_merge_same_actor_without_structural_overlap() -> None:
    payload = build_cross_source_event_braid(
        [
            {
                "source_family": "family_a",
                "source_event_rows": [
                    _row(
                        source_family="family_a",
                        doc_id="doc_a",
                        event_id="A",
                        local_order_index=0,
                        text="Bush traveled to Texas",
                        participants=[("agent", "actor:george_w_bush")],
                    )
                ],
            },
            {
                "source_family": "family_b",
                "source_event_rows": [
                    _row(
                        source_family="family_b",
                        doc_id="doc_b",
                        event_id="B",
                        local_order_index=0,
                        text="Bush discussed judicial nominations",
                        predicate_key="nominated",
                        participants=[("agent", "actor:george_w_bush"), ("theme", "actor:john_roberts")],
                    )
                ],
            },
        ]
    )

    assert payload["merged_events"] == []
    assert not any(row["link_type"] == "same_event_as" and row["promotion_status"] == "promoted" for row in payload["candidate_links"])


def test_braid_edges_have_support_basis() -> None:
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [
            _row(source_family="family_a", doc_id="doc_a", event_id="A", local_order_index=0, text="A meeting"),
            _row(source_family="family_a", doc_id="doc_a", event_id="B", local_order_index=1, text="B briefing"),
        ],
    }
    payload = build_cross_source_event_braid([family_a])

    assert len(payload["ordering_edges"]) > 0
    for edge in payload["ordering_edges"]:
        assert "support_basis" in edge
        assert isinstance(edge["support_basis"], list)
        assert len(edge["support_basis"]) >= 1
        for basis in edge["support_basis"]:
            assert isinstance(basis, str)
            assert basis in {"local_document_order", "inferred_from_source_backed_overlap"}

    for link in payload["candidate_links"]:
        assert "support_basis" in link
        assert isinstance(link["support_basis"], list)
        assert len(link["support_basis"]) >= 1


def test_inferred_ordering_edges_are_marked_inferred_not_promoted_historical() -> None:
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [
            _row(source_family="family_a", doc_id="doc_a", event_id="A", local_order_index=0, text="A meeting"),
            _row(
                source_family="family_a",
                doc_id="doc_a",
                event_id="C1",
                local_order_index=1,
                text="Bush signed the education act",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
                legal_refs=["legal_ref:education_act"],
            ),
        ],
    }
    family_b = {
        "source_family": "family_b",
        "source_event_rows": [
            _row(
                source_family="family_b",
                doc_id="doc_b",
                event_id="C2",
                local_order_index=0,
                text="George W. Bush signed the education act",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
                legal_refs=["legal_ref:education_act"],
            ),
            _row(source_family="family_b", doc_id="doc_b", event_id="E", local_order_index=1, text="E hearing"),
        ],
    }
    payload = build_cross_source_event_braid([family_a, family_b])

    inferred_edges = [
        edge for edge in payload["ordering_edges"]
        if "inferred_from_source_backed_overlap" in edge["support_basis"]
    ]
    assert len(inferred_edges) > 0
    for edge in inferred_edges:
        assert "local_document_order" not in edge["support_basis"]
        assert edge["confidence_band"] == "medium"
        assert edge["promotion_status"] == "promoted"


def test_merged_events_preserve_multiple_source_event_refs() -> None:
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [
            _row(
                source_family="family_a",
                doc_id="doc_a",
                event_id="C1",
                local_order_index=0,
                text="Bush signed the education act",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
                legal_refs=["legal_ref:education_act"],
            ),
        ],
    }
    family_b = {
        "source_family": "family_b",
        "source_event_rows": [
            _row(
                source_family="family_b",
                doc_id="doc_b",
                event_id="C2",
                local_order_index=0,
                text="George W. Bush signed the education act",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
                legal_refs=["legal_ref:education_act"],
            ),
        ],
    }
    payload = build_cross_source_event_braid([family_a, family_b])

    assert len(payload["merged_events"]) == 1
    merged = payload["merged_events"][0]
    assert set(merged["source_event_ids"]) == {"family_a:C1", "family_b:C2"}
    assert set(merged["source_families"]) == {"family_a", "family_b"}


def test_event_without_historical_anchor_does_not_claim_historical_timeline_status() -> None:
    row_unanchored = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="Bush discussed strategy",
    )
    row_unanchored["anchor"] = {}  # Empty anchor

    family_a = {
        "source_family": "family_a",
        "source_event_rows": [row_unanchored],
    }
    payload = build_cross_source_event_braid([family_a])

    event = payload["source_event_rows"][0]
    assert event["anchor"] == {}

    for edge in payload["ordering_edges"]:
        if "family_a:A" in edge["source_event_ids"]:
            assert set(edge["support_basis"]).issubset({"local_document_order", "inferred_from_source_backed_overlap"})
            assert "historical_chronology" not in edge["support_basis"]


def test_candidate_braid_support_does_not_promote_relation_by_itself() -> None:
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [
            _row(
                source_family="family_a",
                doc_id="doc_a",
                event_id="A",
                local_order_index=0,
                text="Bush signed a document",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
            )
        ],
    }
    family_b = {
        "source_family": "family_b",
        "source_event_rows": [
            _row(
                source_family="family_b",
                doc_id="doc_b",
                event_id="B",
                local_order_index=0,
                text="Bush signed a paper",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
            )
        ],
    }
    payload = build_cross_source_event_braid([family_a, family_b])

    assert payload["merged_events"] == []
    assert len(payload["candidate_links"]) == 1
    link = payload["candidate_links"][0]
    assert link["link_type"] == "overlaps_event"
    assert link["promotion_status"] == "candidate"
    assert link["confidence_band"] == "medium"

