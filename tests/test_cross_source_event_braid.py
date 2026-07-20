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
        "anchor": {"year": 2006, "text": "2006-01-01"},
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


def test_frontmatter_and_index_snippets_are_not_event_promotable() -> None:
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [
            _row(
                source_family="family_a",
                doc_id="doc_a",
                event_id="C1",
                local_order_index=0,
                text="Table of Contents: Bush signed the education act",
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

    assert payload["source_event_rows"][0]["is_frontmatter_or_index"] is True
    assert payload["source_event_rows"][1]["is_frontmatter_or_index"] is False

    assert payload["merged_events"] == []
    assert len(payload["candidate_links"]) == 1
    link = payload["candidate_links"][0]
    assert link["link_type"] == "overlaps_event"
    assert link["promotion_status"] == "candidate"
    assert link["confidence_band"] == "low"


def test_events_with_only_ingest_date_are_marked_unanchored() -> None:
    row_a = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="C1",
        local_order_index=0,
        text="In 2006, Bush signed the education act",
        predicate_key="signed",
        participants=[("agent", "actor:george_w_bush")],
        legal_refs=["legal_ref:education_act"],
    )
    row_a["anchor"] = {"year": 2026, "text": "2026-07-06"}

    family_a = {
        "source_family": "family_a",
        "source_event_rows": [row_a],
    }
    family_b = {
        "source_family": "family_b",
        "source_event_rows": [
            _row(
                source_family="family_b",
                doc_id="doc_b",
                event_id="C2",
                local_order_index=0,
                text="George W. Bush signed the education act in 2006",
                predicate_key="signed",
                participants=[("agent", "actor:george_w_bush")],
                legal_refs=["legal_ref:education_act"],
            ),
        ],
    }
    payload = build_cross_source_event_braid([family_a, family_b])

    assert payload["source_event_rows"][0]["has_ingest_date_only"] is True
    assert payload["merged_events"] == []


def test_fallback_action_events_remain_candidate_or_low_confidence() -> None:
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [
            _row(
                source_family="family_a",
                doc_id="doc_a",
                event_id="C1",
                local_order_index=0,
                text="It was reported that Bush signed the education act",
                predicate_key="reported",
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

    assert payload["source_event_rows"][0]["is_fallback_action"] is True
    assert payload["merged_events"] == []
    assert len(payload["candidate_links"]) == 1
    link = payload["candidate_links"][0]
    assert link["promotion_status"] == "candidate"
    assert link["confidence_band"] == "low"


def test_event_requires_actor_action_or_object_for_promotion() -> None:
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
                participants=[],
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

    assert payload["source_event_rows"][0]["has_actors_and_objects"] is False
    assert payload["merged_events"] == []


def test_historical_year_in_span_creates_candidate_time_anchor_not_ingest_anchor() -> None:
    row_a = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="Bush signed the bill in 2006.",
    )
    row_a["anchor"] = {"year": 2026, "text": "2026-07-06"}

    family_a = {
        "source_family": "family_a",
        "source_event_rows": [row_a],
    }
    payload = build_cross_source_event_braid([family_a])

    event = payload["source_event_rows"][0]
    assert event["has_ingest_date_only"] is True
    assert event["candidate_time_anchor_in_span"] == 2006


def test_event_quality_scoring_preservation_and_aggregates() -> None:
    row_promotable = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="Bush signed the education act",
        predicate_key="signed",
        participants=[("agent", "actor:george_w_bush")],
        legal_refs=["legal_ref:education_act"],
    )
    
    row_noise = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="B",
        local_order_index=1,
        text="Table of Contents: Bush traveled to Texas",
        participants=[("agent", "actor:george_w_bush")],
    )

    row_weak = _row(
        source_family="family_b",
        doc_id="doc_b",
        event_id="C",
        local_order_index=0,
        text="It was reported that Bush met a senator",
        predicate_key="reported",
        participants=[("agent", "actor:george_w_bush")],
    )

    family_a = {
        "source_family": "family_a",
        "source_event_rows": [row_promotable, row_noise],
    }
    family_b = {
        "source_family": "family_b",
        "source_event_rows": [row_weak],
    }

    payload = build_cross_source_event_braid([family_a, family_b])

    events = {e["event_id"]: e for e in payload["source_event_rows"]}
    
    assert events["A"]["event_quality_status"] == "promotable_event"
    assert events["A"]["event_quality_score"] == 1.0
    assert "actor_object_complete" in events["A"]["event_quality_reasons"]

    assert events["B"]["event_quality_status"] == "rejected_noise"
    assert events["B"]["event_quality_score"] == 0.0
    assert "frontmatter_or_index" in events["B"]["event_quality_reasons"]

    assert events["C"]["event_quality_status"] == "weak_candidate"
    assert events["C"]["event_quality_score"] == 0.7
    assert "fallback_action" in events["C"]["event_quality_reasons"]

    audit = payload["summary"]["event_quality_audit_by_family"]
    assert audit["family_a"]["promotable_event"] == 1
    assert audit["family_a"]["rejected_noise"] == 1
    assert audit["family_b"]["weak_candidate"] == 1


def test_ingest_date_never_promotes_historical_order() -> None:
    row_a = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="Bush signed the bill",
    )
    row_a["anchor"] = {"year": 2026, "text": "2026-07-06"}
    
    row_b = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="B",
        local_order_index=1,
        text="Bush signed another bill",
    )
    row_b["anchor"] = {"year": 2026, "text": "2026-07-06"}
    
    family = {
        "source_family": "family_a",
        "source_event_rows": [row_a, row_b],
    }
    payload = build_cross_source_event_braid([family])
    
    events = {e["event_id"]: e for e in payload["source_event_rows"]}
    assert events["A"]["event_time_anchor_status"] == "ingest_only"
    assert events["B"]["event_time_anchor_status"] == "ingest_only"
    
    edge = payload["ordering_edges"][0]
    assert edge["time_basis"] == "ingest_order_only"
    assert edge["ordering_basis"] == "document_order"


def test_span_year_creates_low_or_medium_confidence_time_candidate() -> None:
    row = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="In 2006, Bush signed the education act.",
    )
    family = {
        "source_family": "family_a",
        "source_event_rows": [row],
    }
    payload = build_cross_source_event_braid([family])
    event = payload["source_event_rows"][0]
    assert event["event_time_anchor_status"] == "candidate_span_year"
    assert event["event_time_anchor_precision"] == "year"
    assert event["event_time_anchor_confidence"] == "medium"
    assert event["event_time_anchor_source"] == "span_text"
    assert event["resolved_historical_date"] == "2006"


def test_explicit_full_date_creates_high_confidence_time_anchor() -> None:
    row = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="On October 17, 2006, Bush signed the act.",
    )
    family = {
        "source_family": "family_a",
        "source_event_rows": [row],
    }
    payload = build_cross_source_event_braid([family])
    event = payload["source_event_rows"][0]
    assert event["event_time_anchor_status"] == "explicit_span_date"
    assert event["event_time_anchor_precision"] == "day"
    assert event["event_time_anchor_confidence"] == "high"
    assert event["resolved_historical_date"] == "2006-october-17"


def test_conflicting_span_years_mark_temporal_residual() -> None:
    row = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="In 2006, Bush recalled the 2001 agreement.",
        predicate_key="recalled",
        participants=[("agent", "actor:george_w_bush")],
        legal_refs=["legal_ref:agreement"],
    )
    family = {
        "source_family": "family_a",
        "source_event_rows": [row],
    }
    payload = build_cross_source_event_braid([family])
    event = payload["source_event_rows"][0]
    assert event["event_time_anchor_status"] == "candidate_span_year"
    assert event["has_conflicting_span_years"] is True
    assert event["event_time_anchor_confidence"] == "low"
    assert event["event_quality_score"] == 0.5
    assert "conflicting_span_years" in event["event_quality_reasons"]
    assert "unresolved_compound" in event["event_quality_reasons"]
    assert event["event_quality_status"] == "weak_candidate"


def test_ordering_edge_records_time_basis_separately_from_document_order_basis() -> None:
    row_left = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="In 2006, Bush signed the act.",
    )
    row_right = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="B",
        local_order_index=1,
        text="In 2008, Bush signed the next act.",
    )
    family = {
        "source_family": "family_a",
        "source_event_rows": [row_left, row_right],
    }
    payload = build_cross_source_event_braid([family])
    edge = payload["ordering_edges"][0]
    assert edge["support_basis"] == ["local_document_order"]
    assert edge["ordering_basis"] == "historical_time_order"
    assert edge["time_basis"] == "historical_time_comparison"

    row_left2 = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="C",
        local_order_index=0,
        text="In 2009, Bush signed the act.",
    )
    row_right2 = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="D",
        local_order_index=1,
        text="In 2006, Bush signed the next act.",
    )
    family2 = {
        "source_family": "family_a",
        "source_event_rows": [row_left2, row_right2],
    }
    payload2 = build_cross_source_event_braid([family2])
    edge2 = payload2["ordering_edges"][0]
    assert edge2["ordering_basis"] == "document_order"
    assert edge2["time_basis"] == "historical_conflict_residual"


def test_spot_audit_rows_include_source_span_and_temporal_basis() -> None:
    from src.policy.gwb_spot_audit import load_spot_audit_registry
    registry = load_spot_audit_registry()
    
    assert "family_a:A" in registry["events"]
    record = registry["events"]["family_a:A"]
    assert record["source_span"] == "Bush signed the education act"
    assert record["human_event_like"] == "yes"
    assert record["recommended_status"] == "promote"


def test_human_blocked_event_cannot_promote_in_future_checkpoint() -> None:
    from src.policy.gwb_spot_audit import apply_spot_audit_blocks
    from scripts.build_gwb_broader_corpus_checkpoint import _merge_families
    
    row_a = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="Bush signed the education act",
        predicate_key="signed",
        participants=[("agent", "actor:george_w_bush")],
        legal_refs=["legal_ref:education_act"],
    )
    row_b = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="B",
        local_order_index=1,
        text="Table of Contents: Bush traveled to Texas",
        predicate_key="traveled",
        participants=[("agent", "actor:george_w_bush")],
    )
    
    registry = {
        "events": {
            "family_a:B": {
                "recommended_status": "block"
            }
        },
        "edges": {}
    }
    
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [row_a, row_b],
        "selected_promoted_relations": [
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "signed",
                "object": {"canonical_label": "education act"},
                "event_id": "A",
            },
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "traveled",
                "object": {"canonical_label": "Texas"},
                "event_id": "B",
            }
        ],
        "selected_seed_lanes": [],
    }
    
    payload = build_cross_source_event_braid([family_a])
    audited = apply_spot_audit_blocks(payload, registry)
    
    assert any(e["event_id"] == "A" for e in audited["source_event_rows"])
    assert not any(e["event_id"] == "B" for e in audited["source_event_rows"])
    
    merged = _merge_families([family_a], braid_payload=audited, audit_registry=registry)
    
    assert len(merged["merged_promoted_relations"]) == 1
    assert merged["merged_promoted_relations"][0]["predicate_key"] == "signed"


def test_historical_conflict_residual_survives_to_review_row() -> None:
    from scripts.build_gwb_broader_corpus_checkpoint import _merge_families
    
    row_left = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="C",
        local_order_index=0,
        text="In 2009, Bush signed the act.",
        predicate_key="signed",
        participants=[("agent", "actor:george_w_bush")],
        legal_refs=["legal_ref:act"],
    )
    row_right = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="D",
        local_order_index=1,
        text="In 2006, Bush signed the next act.",
        predicate_key="signed",
        participants=[("agent", "actor:george_w_bush")],
        legal_refs=["legal_ref:next_act"],
    )
    
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [row_left, row_right],
        "selected_promoted_relations": [
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "signed",
                "object": {"canonical_label": "act"},
                "event_id": "C",
            },
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "signed",
                "object": {"canonical_label": "next_act"},
                "event_id": "D",
            }
        ],
        "selected_seed_lanes": [],
    }
    
    payload = build_cross_source_event_braid([family_a])
    edge = payload["ordering_edges"][0]
    assert edge["time_basis"] == "historical_conflict_residual"
    
    merged = _merge_families([family_a], braid_payload=payload)
    rel = next(r for r in merged["merged_promoted_relations"] if r["object"]["canonical_label"] == "act")
    assert "historical_conflict_residual" in rel["time_basis_types"]


def test_ingest_order_only_edges_are_excluded_from_historical_timeline_export() -> None:
    from src.policy.gwb_spot_audit import export_historical_timeline
    
    row_a = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="Bush signed the bill",
    )
    row_a["anchor"] = {"year": 2026, "text": "2026-07-06"}
    
    row_b = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="B",
        local_order_index=1,
        text="Bush signed another bill",
    )
    row_b["anchor"] = {"year": 2026, "text": "2026-07-06"}
    
    family = {
        "source_family": "family_a",
        "source_event_rows": [row_a, row_b],
    }
    payload = build_cross_source_event_braid([family])
    
    historical = export_historical_timeline(payload, {})
    assert len(historical["ordering_edges"]) == 0


def test_historical_timeline_export_contains_only_historical_time_order_edges() -> None:
    from src.policy.gwb_spot_audit import export_historical_timeline
    
    row_a = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="A",
        local_order_index=0,
        text="In 2006, Bush signed the act.",
    )
    row_b = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="B",
        local_order_index=1,
        text="In 2008, Bush signed the next act.",
    )
    row_c = _row(
        source_family="family_a",
        doc_id="doc_a",
        event_id="C",
        local_order_index=2,
        text="Bush signed the final act.",
    )
    
    family = {
        "source_family": "family_a",
        "source_event_rows": [row_a, row_b, row_c],
    }
    payload = build_cross_source_event_braid([family])
    
    historical = export_historical_timeline(payload, {})
    
    assert len(historical["ordering_edges"]) == 1
    edge = historical["ordering_edges"][0]
    assert edge["source_event_id"] == "family_a:A"
    assert edge["target_event_id"] == "family_a:B"
    assert edge["ordering_basis"] == "historical_time_order"


def test_multi_family_same_actor_predicate_object_scores_strong_corroboration() -> None:
    from src.policy.gwb_timeline_content_review import classify_corroboration
    
    rel = {
        "subject": {"canonical_key": "actor:george_w_bush"},
        "predicate_key": "signed",
        "object": {"canonical_key": "legal_ref:nclba"},
        "source_families": ["public_bios_timeline", "corpus_book_timeline"],
        "event_quality_status": "promotable_event",
        "event_time_anchor_status": "resolved_historical_date",
        "time_basis_types": ["historical_time_comparison"],
        "lineage_records": [
            {"source_family": "public_bios_timeline", "event_id": "A"},
            {"source_family": "corpus_book_timeline", "event_id": "B"}
        ]
    }
    
    assert classify_corroboration(rel, {}) == "strong"


def test_single_source_relation_scores_single_source_not_strong() -> None:
    from src.policy.gwb_timeline_content_review import classify_corroboration
    
    rel = {
        "subject": {"canonical_key": "actor:george_w_bush"},
        "predicate_key": "signed",
        "object": {"canonical_key": "legal_ref:nclba"},
        "source_families": ["public_bios_timeline"],
        "event_quality_status": "promotable_event",
        "event_time_anchor_status": "resolved_historical_date",
        "time_basis_types": ["historical_time_comparison"],
        "lineage_records": [
            {"source_family": "public_bios_timeline", "event_id": "A"}
        ]
    }
    
    assert classify_corroboration(rel, {}) == "single_source"


def test_candidate_only_braid_scores_weak_corroboration() -> None:
    from src.policy.gwb_timeline_content_review import classify_corroboration
    
    rel = {
        "subject": {"canonical_key": "actor:george_w_bush"},
        "predicate_key": "signed",
        "object": {"canonical_key": "legal_ref:nclba"},
        "source_families": ["public_bios_timeline"],
        "event_quality_status": "usable_candidate",
        "event_time_anchor_status": "none",
        "lineage_records": [
            {"source_family": "public_bios_timeline", "event_id": "A"}
        ]
    }
    
    assert classify_corroboration(rel, {}) == "weak"


def test_historical_conflict_residual_scores_conflicted() -> None:
    from src.policy.gwb_timeline_content_review import classify_corroboration
    
    rel = {
        "subject": {"canonical_key": "actor:george_w_bush"},
        "predicate_key": "signed",
        "object": {"canonical_key": "legal_ref:nclba"},
        "source_families": ["public_bios_timeline", "corpus_book_timeline"],
        "event_quality_status": "promotable_event",
        "event_time_anchor_status": "resolved_historical_date",
        "time_basis_types": ["historical_conflict_residual"],
        "lineage_records": [
            {"source_family": "public_bios_timeline", "event_id": "A"},
            {"source_family": "corpus_book_timeline", "event_id": "B"}
        ]
    }
    
    assert classify_corroboration(rel, {}) == "conflicted"


def test_blocked_or_rejected_noise_never_enters_corroboration_promote_bucket() -> None:
    from src.policy.gwb_timeline_content_review import classify_corroboration
    
    rel_noise = {
        "subject": {"canonical_key": "actor:george_w_bush"},
        "predicate_key": "signed",
        "object": {"canonical_key": "legal_ref:nclba"},
        "source_families": ["public_bios_timeline", "corpus_book_timeline"],
        "event_quality_status": "rejected_noise",
        "lineage_records": [
            {"source_family": "public_bios_timeline", "event_id": "A"},
            {"source_family": "corpus_book_timeline", "event_id": "B"}
        ]
    }
    assert classify_corroboration(rel_noise, {}) == "blocked"

    rel_empty = {
        "subject": {"canonical_key": "actor:george_w_bush"},
        "predicate_key": "signed",
        "object": {"canonical_key": "legal_ref:nclba"},
        "source_families": ["public_bios_timeline", "corpus_book_timeline"],
        "event_quality_status": "promotable_event",
        "lineage_records": []
    }
    assert classify_corroboration(rel_empty, {}) == "blocked"


def test_review_markdown_lists_gaps_and_top_corroborated_items() -> None:
    from scripts.build_gwb_timeline_content_review import build_review_summary_markdown
    
    payload = {
        "summary": {
            "total_reviewed_relations": 2,
            "degree_counts": {"strong": 1, "single_source": 1},
            "risky_merged_event_count": 0,
            "conflict_packet_count": 0
        },
        "reviewed_relations": [
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "signed",
                "object": {"canonical_label": "NCLBA"},
                "corroboration_degree": "strong",
                "resolved_historical_date": "2001",
                "event_quality_score": 0.95,
                "gaps": ["no_primary_source"]
            },
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "nominated",
                "object": {"canonical_label": "Roberts"},
                "corroboration_degree": "single_source",
                "source_families": ["public_bios_timeline"],
                "gaps": ["no_independent_corroboration"]
            }
        ],
        "merge_risky_events": [],
        "conflict_packets": []
    }
    
    md = build_review_summary_markdown(payload)
    assert "# GWB Timeline Content Corroboration Review Summary" in md
    assert "**strong**: 1" in md
    assert "NCLBA" in md
    assert "no_primary_source" in md
    assert "no_independent_corroboration" in md


def test_human_review_timeline_includes_metrics() -> None:
    from scripts.build_gwb_human_review_timeline import compile_human_review_timeline
    
    checkpoint = {
        "qc_report": {
            "source_event_count": 10,
            "active_event_count": 8,
            "blocked_event_count": 2,
            "relations_dropped_by_audit_block": 1
        },
        "cross_source_event_braid": {"source_event_rows": [], "ordering_edges": []}
    }
    review = {"reviewed_relations": [], "merge_risky_events": [], "conflict_packets": []}
    timeline = {"source_event_rows": [{}], "ordering_edges": [{}, {}]}
    
    packet = compile_human_review_timeline(checkpoint, review, timeline)
    assert packet["metrics"]["source_event_count"] == 10
    assert packet["metrics"]["active_event_count"] == 8
    assert packet["metrics"]["blocked_event_count"] == 2
    assert packet["metrics"]["historical_timeline_event_count"] == 1
    assert packet["metrics"]["historical_timeline_edge_count"] == 2
    assert packet["metrics"]["relations_dropped_by_audit_block"] == 1


def test_human_review_timeline_lists_excluded_ingest_and_document_order_edges() -> None:
    from scripts.build_gwb_human_review_timeline import compile_human_review_timeline
    
    checkpoint = {
        "cross_source_event_braid": {
            "source_event_rows": [],
            "ordering_edges": [
                {"ordering_edge_id": "edge:1", "ordering_basis": "document_order"},
                {"ordering_edge_id": "edge:2", "ordering_basis": "historical_time_order"}
            ]
        }
    }
    review = {"reviewed_relations": [], "merge_risky_events": [], "conflict_packets": []}
    
    packet = compile_human_review_timeline(checkpoint, review, {})
    excluded = packet["excluded_items"]
    assert any(item["item"] == "edge:1" and item["type"] == "Edge" and item["reason"] == "document_order" for item in excluded)
    assert not any(item["item"] == "edge:2" for item in excluded)


def test_human_review_timeline_rows_include_corroboration_and_date_confidence() -> None:
    from scripts.build_gwb_human_review_timeline import compile_human_review_timeline
    
    checkpoint = {
        "cross_source_event_braid": {
            "source_event_rows": []
        }
    }
    review = {
        "reviewed_relations": [
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "signed",
                "object": {"canonical_label": "NCLBA"},
                "corroboration_degree": "strong",
                "date_confidence": "year_only",
                "gaps": ["no_primary_source"]
            }
        ]
    }
    timeline = {
        "source_event_rows": [
            {
                "event_id": "ev:1",
                "text": "Bush signed NCLBA",
                "anchor": {"text": "2001"},
                "relation_candidates": [
                    {
                        "subject": {"canonical_label": "Bush"},
                        "predicate_key": "signed",
                        "object": {"canonical_label": "NCLBA"}
                    }
                ]
            }
        ]
    }
    
    packet = compile_human_review_timeline(checkpoint, review, timeline)
    rows = packet["timeline_rows"]
    assert len(rows) == 1
    assert rows[0]["date"] == "2001"
    assert rows[0]["event"] == "Bush signed NCLBA"
    assert rows[0]["corroboration"] == "strong"
    assert rows[0]["confidence"] == "year_only"
    assert rows[0]["gaps"] == "no_primary_source"
    assert rows[0]["action"] == "verify_span"


def test_blocked_events_appear_in_excluded_items_not_timeline_rows() -> None:
    from scripts.build_gwb_human_review_timeline import compile_human_review_timeline
    
    checkpoint = {
        "cross_source_event_braid": {"source_event_rows": []}
    }
    review = {"reviewed_relations": [], "merge_risky_events": [], "conflict_packets": []}
    packet = compile_human_review_timeline(checkpoint, review, {}, audit_registry={"ev_foo": {"status": "block"}})
    assert any(item["reason"] == "blocked_by_spot_audit" and item["item"] == "ev_foo" for item in packet["excluded_items"])


def test_review_queue_prioritizes_strong_items_with_gaps() -> None:
    from scripts.build_gwb_human_review_timeline import compile_human_review_timeline
    
    checkpoint = {
        "cross_source_event_braid": {"source_event_rows": []}
    }
    review = {
        "reviewed_relations": [
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "nominated",
                "object": {"canonical_label": "Roberts"},
                "corroboration_degree": "single_source",
                "gaps": ["no_independent_corroboration"]
            },
            {
                "subject": {"canonical_label": "Bush"},
                "predicate_key": "signed",
                "object": {"canonical_label": "NCLBA"},
                "corroboration_degree": "strong",
                "gaps": ["no_primary_source"]
            }
        ]
    }
    
    packet = compile_human_review_timeline(checkpoint, review, {})
    queue = packet["review_queue"]
    assert queue[0]["target"] == "Bush signed NCLBA"
    assert queue[0]["priority"] == "high"
    assert queue[1]["target"] == "Bush nominated Roberts"
    assert queue[1]["priority"] == "medium"


def test_markdown_contains_timeline_exclusions_conflicts_and_metrics() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 10,
            "active_event_count": 8,
            "blocked_event_count": 2,
            "historical_timeline_event_count": 1,
            "historical_timeline_edge_count": 2,
            "conflict_residual_count": 1,
            "relations_dropped_by_audit_block": 1
        },
        "timeline_rows": [
            {
                "date": "2001",
                "event": "Bush signed NCLBA",
                "corroboration": "strong",
                "sources": "2 families",
                "confidence": "year_only",
                "gaps": "no_primary_source",
                "action": "verify_span"
            }
        ],
        "excluded_items": [
            {
                "item": "edge:1",
                "type": "Edge",
                "reason": "document_order",
                "effect": "not_chronological"
            }
        ],
        "review_queue": [
            {
                "priority": "high",
                "target": "Bush signed NCLBA",
                "action": "verify_primary_source_span",
                "reason": "strong corroboration but has gaps"
            }
        ]
    }
    
    md = generate_triage_markdown(packet)
    assert "# GWB Human Review Timeline Packet" in md
    assert "Historical timeline rows" in md
    assert "Bush signed NCLBA" in md
    assert "document order" in md
    assert "verify primary source span" in md


def test_main_timeline_excludes_no_relation_rows() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 1,
            "active_event_count": 1,
            "blocked_event_count": 0,
            "historical_timeline_event_count": 1,
            "historical_timeline_edge_count": 0,
            "conflict_residual_count": 0,
            "relations_dropped_by_audit_block": 0
        },
        "timeline_rows": [
            {
                "date": "2001",
                "event": "Some raw prose text snippet",
                "corroboration": "weak",
                "sources": "1 family",
                "confidence": "year_only",
                "gaps": "no_relation",
                "action": "review"
            }
        ],
        "excluded_items": [],
        "review_queue": []
    }
    
    md = generate_triage_markdown(packet)
    parts = md.split("## ")
    timeline_part = [p for p in parts if p.startswith("Historical Timeline Candidate")][0]
    triage_part = [p for p in parts if p.startswith("Needs Triage / Weak Extracted Rows")][0]
    
    assert "Some raw prose text snippet" not in timeline_part
    assert "Some raw prose text snippet" in triage_part


def test_main_timeline_excludes_unknown_date_rows() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 1,
            "active_event_count": 1,
            "blocked_event_count": 0,
            "historical_timeline_event_count": 1,
            "historical_timeline_edge_count": 0,
            "conflict_residual_count": 0,
            "relations_dropped_by_audit_block": 0
        },
        "timeline_rows": [
            {
                "date": "unknown",
                "event": "Bush signed NCLBA",
                "corroboration": "strong",
                "sources": "2 families",
                "confidence": "unknown",
                "gaps": "none",
                "action": "verify_span"
            }
        ],
        "excluded_items": [],
        "review_queue": []
    }
    
    md = generate_triage_markdown(packet)
    parts = md.split("## ")
    timeline_part = [p for p in parts if p.startswith("Historical Timeline Candidate")][0]
    triage_part = [p for p in parts if p.startswith("Needs Triage / Weak Extracted Rows")][0]
    
    assert "Bush signed NCLBA" not in timeline_part
    assert "Bush signed NCLBA" in triage_part


def test_main_timeline_excludes_ingest_date_rows() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 1,
            "active_event_count": 1,
            "blocked_event_count": 0,
            "historical_timeline_event_count": 1,
            "historical_timeline_edge_count": 0,
            "conflict_residual_count": 0,
            "relations_dropped_by_audit_block": 0
        },
        "timeline_rows": [
            {
                "date": "2026-07-07",
                "event": "Bush signed NCLBA",
                "corroboration": "strong",
                "sources": "2 families",
                "confidence": "ingest_order_only",
                "gaps": "none",
                "action": "verify_span"
            }
        ],
        "excluded_items": [],
        "review_queue": []
    }
    
    md = generate_triage_markdown(packet)
    parts = md.split("## ")
    timeline_part = [p for p in parts if p.startswith("Historical Timeline Candidate")][0]
    triage_part = [p for p in parts if p.startswith("Needs Triage / Weak Extracted Rows")][0]
    
    assert "Bush signed NCLBA" not in timeline_part
    assert "Bush signed NCLBA" in triage_part


def test_weak_rows_move_to_triage_table() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 1,
            "active_event_count": 1,
            "blocked_event_count": 0,
            "historical_timeline_event_count": 1,
            "historical_timeline_edge_count": 0,
            "conflict_residual_count": 0,
            "relations_dropped_by_audit_block": 0
        },
        "timeline_rows": [
            {
                "date": "2001",
                "event": "Bush reported education",
                "corroboration": "weak",
                "sources": "1 family",
                "confidence": "year_only",
                "gaps": "none",
                "action": "review"
            }
        ],
        "excluded_items": [],
        "review_queue": []
    }
    
    md = generate_triage_markdown(packet)
    parts = md.split("## ")
    timeline_part = [p for p in parts if p.startswith("Historical Timeline Candidate")][0]
    triage_part = [p for p in parts if p.startswith("Needs Triage / Weak Extracted Rows")][0]
    
    assert "Bush reported education" not in timeline_part
    assert "Bush reported education" in triage_part


def test_conflicted_relation_rows_remain_visible_in_conflict_table() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 1,
            "active_event_count": 1,
            "blocked_event_count": 0,
            "historical_timeline_event_count": 1,
            "historical_timeline_edge_count": 0,
            "conflict_residual_count": 1,
            "relations_dropped_by_audit_block": 0
        },
        "timeline_rows": [
            {
                "date": "2001",
                "event": "Bush subject of review by Supreme Court",
                "corroboration": "conflicted",
                "sources": "3 families",
                "confidence": "ingest_order_only",
                "gaps": "historical_conflict_residual",
                "action": "resolve_conflict"
            }
        ],
        "excluded_items": [],
        "review_queue": []
    }
    
    md = generate_triage_markdown(packet)
    parts = md.split("## ")
    timeline_part = [p for p in parts if p.startswith("Historical Timeline Candidate")][0]
    conflict_part = [p for p in parts if p.startswith("Conflict Residuals")][0]
    triage_part = [p for p in parts if p.startswith("Needs Triage / Weak Extracted Rows")][0]
    
    assert "Bush subject of review by Supreme Court" not in timeline_part
    assert "Bush subject of review by Supreme Court" not in triage_part
    assert "Bush subject of review by Supreme Court" in conflict_part


def test_markdown_has_separate_timeline_and_triage_sections() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 10,
            "active_event_count": 8,
            "blocked_event_count": 2,
            "historical_timeline_event_count": 1,
            "historical_timeline_edge_count": 2,
            "conflict_residual_count": 1,
            "relations_dropped_by_audit_block": 1
        },
        "timeline_rows": [],
        "excluded_items": [],
        "review_queue": []
    }
    
    md = generate_triage_markdown(packet)
    assert "## Historical Timeline Candidate" in md
    assert "## Needs Triage / Weak Extracted Rows" in md
    assert "## Conflict Residuals" in md


def test_fragment_with_multiple_years_recurses_until_one_year_per_atom() -> None:
    from src.policy.cross_source_event_braid import atomize_source_events
    
    row = {
        "event_id": "ev:001",
        "text": "In 1993, Bush challenged Ann Richards. He won reelection in 1998.",
        "anchor": {"year": 1993, "text": "1993"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    
    atoms = atomize_source_events([row])
    assert len(atoms) == 2
    assert atoms[0]["event_id"] == "ev:001:atom:0000"
    assert atoms[0]["anchor"]["year"] == 1993
    assert atoms[1]["event_id"] == "ev:001:atom:0001"
    assert atoms[1]["anchor"]["year"] == 1998


def test_dash_cv_cell_emits_role_atoms_with_date_ranges() -> None:
    from src.policy.cross_source_event_braid import atomize_source_events
    
    row = {
        "event_id": "ev:002",
        "text": "Co-owned Texas Rangers 1989–1998 - 46th Governor of Texas 1995–2000 - Proclaimed June 10, 2000 to be Jesus Day",
        "anchor": {"year": 2000, "text": "2000"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    
    atoms = atomize_source_events([row])
    assert len(atoms) >= 3
    assert any("Texas Rangers" in a["text"] for a in atoms)
    assert any("Governor of Texas" in a["text"] for a in atoms)
    assert any("Jesus Day" in a["text"] for a in atoms)


def test_compound_atomizer_uses_public_sensiblaw_interfaces() -> None:
    import inspect
    from src.policy import cross_source_event_braid
    
    source = inspect.getsource(cross_source_event_braid._recursive_atomize)
    assert "import spacy" not in source
    assert "from src.text" not in source
    assert "from sensiblaw.interfaces import" in source


def test_event_atom_has_canonical_spans_and_parent_cell_id() -> None:
    from src.policy.cross_source_event_braid import atomize_source_events
    
    row = {
        "event_id": "ev:004",
        "text": "In 1993, Bush challenged Ann Richards. He won reelection in 1998.",
        "anchor": {"year": 1993, "text": "1993"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    
    atoms = atomize_source_events([row])
    for atom in atoms:
        assert atom["parent_event_id"] == "ev:004"
        assert atom["parent_text"] == "In 1993, Bush challenged Ann Richards. He won reelection in 1998."


def test_unresolved_multi_predicate_fragment_marked_unresolved_compound() -> None:
    from src.policy.cross_source_event_braid import atomize_source_events
    
    row = {
        "event_id": "ev:005",
        "text": "In 1993 1998 Bush challenged Ann Richards.",
        "anchor": {"year": 1993, "text": "1993"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    
    atoms = atomize_source_events([row])
    assert any(a.get("unresolved_compound") for a in atoms)
    assert any(a["event_quality_status"] == "weak_candidate" for a in atoms)


def test_timeline_export_uses_reviewable_atoms_not_parent_cells() -> None:
    from scripts.build_gwb_broader_corpus_checkpoint import build_broader_checkpoint
    import tempfile
    from pathlib import Path
    import json
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        payload = build_broader_checkpoint(Path(tmp_dir))
        slice_path = Path(payload["slice_path"])
        slice_payload = json.loads(slice_path.read_text(encoding="utf-8"))
        
        braid = slice_payload["cross_source_event_braid"]
        rows = braid["source_event_rows"]
        
        parent_ids = {r["parent_event_id"] for r in rows if r.get("parent_event_id")}
        assert len(parent_ids) > 0
        
        for r in rows:
            years = [w for w in "".join(c if c.isdigit() else " " for c in r.get("text", "")).split() if len(w) == 4 and (w.startswith("19") or w.startswith("20"))]
            assert len(set(years)) <= 1 or r.get("unresolved_compound")


def test_parent_weak_cell_can_emit_usable_candidate_atoms() -> None:
    from src.policy.cross_source_event_braid import atomize_source_events
    
    row = {
        "event_id": "ev:003",
        "text": "In 1993, Bush challenged Ann Richards. He won reelection in 1998.",
        "anchor": {"year": 1993, "text": "1993"},
        "relation_candidates": [
            {
                "subject": {"canonical_key": "actor:George W. Bush", "canonical_label": "George W. Bush"},
                "predicate_key": "challenged",
                "object": {"canonical_key": "actor:Ann Richards", "canonical_label": "Ann Richards"}
            }
        ],
        "event_quality_status": "weak",
        "event_roles": [{"entity": {"canonical_key": "actor:George W. Bush"}}]
    }
    
    atoms = atomize_source_events([row])
    assert len(atoms) == 2
    assert atoms[0]["event_quality_status"] == "promotable_event"
    assert atoms[1]["event_quality_status"] == "promotable_event"


def test_main_timeline_can_use_atom_rows_not_parent_rows() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 2,
            "active_event_count": 2,
            "blocked_event_count": 0,
            "historical_timeline_event_count": 2,
            "historical_timeline_edge_count": 0,
            "conflict_residual_count": 0,
            "relations_dropped_by_audit_block": 0
        },
        "timeline_rows": [
            {
                "date": "1993",
                "event": "George W. Bush challenged Ann Richards",
                "corroboration": "strong",
                "sources": "1 family",
                "confidence": "year_only",
                "gaps": "none",
                "action": "promote",
                "parent_event_id": "ev:001"
            }
        ],
        "recovered_atoms": [
            {
                "date": "1993",
                "event": "George W. Bush challenged Ann Richards",
                "parent_cell_id": "ev:001",
                "confidence": "year_only",
                "action": "promote"
            }
        ],
        "expanded_cells": [
            {
                "parent_cell_id": "ev:001",
                "atom_count": 1,
                "parent_status": "weak",
                "action": "Review atoms"
            }
        ],
        "excluded_items": [],
        "review_queue": []
    }
    
    md = generate_triage_markdown(packet)
    assert "## Historical Timeline Candidate" in md
    assert "George W. Bush challenged Ann Richards" in md
    assert "## Recovered Event Atoms" in md
    assert "ev:001" in md


def test_compound_cells_expanded_table_lists_atom_counts() -> None:
    from scripts.build_gwb_human_review_timeline import generate_triage_markdown
    
    packet = {
        "metrics": {
            "source_event_count": 2,
            "active_event_count": 2,
            "blocked_event_count": 0,
            "historical_timeline_event_count": 2,
            "historical_timeline_edge_count": 0,
            "conflict_residual_count": 0,
            "relations_dropped_by_audit_block": 0
        },
        "timeline_rows": [],
        "recovered_atoms": [],
        "expanded_cells": [
            {
                "parent_cell_id": "ev:001",
                "atom_count": 3,
                "parent_status": "weak",
                "action": "Review atoms"
            }
        ],
        "excluded_items": [],
        "review_queue": []
    }
    
    md = generate_triage_markdown(packet)
    assert "## Compound Cells Expanded" in md
    assert "ev:001" in md
    assert "3" in md
    assert "weak" in md


def test_pnf_atom_does_not_assign_relevance_from_predicate_identity() -> None:
    from src.policy.cross_source_event_braid import atomize_source_events, build_cross_source_event_braid
    
    row = {
        "event_id": "ev:birth_001",
        "text": "Born July 6, 1946",
        "source_family": "family_a",
        "anchor": {"year": 1946, "text": "1946"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    family = {
        "source_family": "family_a",
        "source_event_rows": [row]
    }
    payload = build_cross_source_event_braid([family])
    event = payload["source_event_rows"][0]
    
    assert event["braid_metrics"]["connectedness"] == 0.0
    assert event["relevance"]["status"] == "background"


def test_relevance_score_uses_braid_connectedness_not_literal_predicate() -> None:
    from src.policy.cross_source_event_braid import build_cross_source_event_braid
    
    row_left = {
        "event_id": "ev:left",
        "text": "Served as Governor of Texas 1995–2000",
        "source_family": "family_a",
        "anchor": {"year": 1995, "text": "1995"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    row_right = {
        "event_id": "ev:right",
        "text": "Served as Governor of Texas 1995–2000",
        "source_family": "family_b",
        "anchor": {"year": 1995, "text": "1995"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [row_left]
    }
    family_b = {
        "source_family": "family_b",
        "source_event_rows": [row_right]
    }
    payload = build_cross_source_event_braid([family_a, family_b])
    
    left_out = next(r for r in payload["source_event_rows"] if r["event_id"] == "ev:left")
    
    assert left_out["braid_metrics"]["connectedness"] > 0.0
    assert left_out["relevance"]["score"] >= 0.5


def test_high_connected_birth_atom_can_remain_timeline_candidate() -> None:
    from src.policy.cross_source_event_braid import build_cross_source_event_braid
    
    row_left = {
        "event_id": "ev:birth_l",
        "text": "Born July 6, 1946",
        "source_family": "family_a",
        "anchor": {"year": 1946, "text": "1946"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    row_right = {
        "event_id": "ev:birth_r",
        "text": "Born July 6, 1946",
        "source_family": "family_b",
        "anchor": {"year": 1946, "text": "1946"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    family_a = {
        "source_family": "family_a",
        "source_event_rows": [row_left]
    }
    family_b = {
        "source_family": "family_b",
        "source_event_rows": [row_right]
    }
    payload = build_cross_source_event_braid([family_a, family_b])
    
    left_out = next(r for r in payload["source_event_rows"] if r["event_id"] == "ev:birth_l")
    
    assert left_out["relevance"]["status"] == "timeline_candidate"


def test_low_connected_birth_atom_moves_to_background_or_triage() -> None:
    from src.policy.cross_source_event_braid import build_cross_source_event_braid
    
    row = {
        "event_id": "ev:birth_lone",
        "text": "Born July 6, 1946",
        "source_family": "family_a",
        "anchor": {"year": 1946, "text": "1946"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    family = {
        "source_family": "family_a",
        "source_event_rows": [row]
    }
    payload = build_cross_source_event_braid([family])
    event = payload["source_event_rows"][0]
    
    assert event["relevance"]["status"] in {"background", "triage"}


def test_office_atom_without_braid_support_does_not_auto_promote() -> None:
    from src.policy.cross_source_event_braid import build_cross_source_event_braid
    
    row = {
        "event_id": "ev:office_lone",
        "text": "Governor of Texas 1995–2000",
        "source_family": "family_a",
        "anchor": {"year": 1995, "text": "1995"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    family = {
        "source_family": "family_a",
        "source_event_rows": [row]
    }
    payload = build_cross_source_event_braid([family])
    event = payload["source_event_rows"][0]
    
    assert event["relevance"]["status"] != "timeline_candidate"


def test_export_gate_consumes_relevance_score_not_predicate_key() -> None:
    from src.policy.cross_source_event_braid import build_cross_source_event_braid
    from src.policy.gwb_spot_audit import export_historical_timeline
    
    row = {
        "event_id": "ev:export_test",
        "text": "Born July 6, 1946",
        "source_family": "family_a",
        "anchor": {"year": 1946, "text": "1946"},
        "relation_candidates": [],
        "event_quality_status": "weak"
    }
    family = {
        "source_family": "family_a",
        "source_event_rows": [row]
    }
    payload = build_cross_source_event_braid([family])
    
    res = export_historical_timeline(payload, {})
    
    assert not any(r["event_id"] == "ev:export_test" for r in res["source_event_rows"])







