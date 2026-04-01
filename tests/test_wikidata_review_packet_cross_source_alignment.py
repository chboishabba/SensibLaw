from __future__ import annotations

from src.ontology import wikidata_review_packet_cross_source_alignment as alignment


def _build_surface(
    *,
    label: str,
    identity: str | None = None,
    fields: list[str] | None = None,
    source: str | None = None,
    summary: str | None = None,
) -> dict[str, object]:
    data: dict[str, object] = {"source": source or f"surface-{label}"}
    if identity:
        data["qid"] = identity
    if fields:
        data["fields"] = fields
    if summary:
        data["summary"] = summary
    return data


def test_summary_reports_full_alignment_agreement() -> None:
    result = alignment.summarize_cross_source_alignment(
        packet_id="packet-1",
        wiki_surface=_build_surface(
            label="wiki",
            identity="Q123",
            fields=["P2738", "P31"],
            summary="Disjointness case from the wiki surface.",
        ),
        query_slice=_build_surface(
            label="query",
            identity="Q123",
            fields=["P2738", "P11260"],
            summary="Query slice that mirrors the same entity.",
        ),
        split_bundle=_build_surface(
            label="split",
            identity="Q123",
            fields=["P2738"],
            summary="Held split bundle for the disjoint set.",
        ),
    )

    assert result["schema_version"] == alignment.CROSS_SOURCE_ALIGNMENT_SCHEMA_VERSION
    assert result["packet_id"] == "packet-1"
    assert result["consensus_level"] == "full_consensus"
    assert result["consensus_identity"] == "Q123"
    assert result["common_fields"] == ["P2738"]
    assert any("Shared entity id" in note for note in result["agreements"])
    assert "fields documented" not in " ".join(result["disagreements"])
    for signature in result["pairwise_signatures"]:
        assert signature["field_overlap"]


def test_summary_notes_identity_disagreement() -> None:
    result = alignment.summarize_cross_source_alignment(
        packet_id="packet-2",
        wiki_surface=_build_surface(label="wiki", identity="Q123", fields=["P31"]),
        query_slice=_build_surface(label="query", identity="Q456", fields=["P31"]),
        split_bundle=_build_surface(label="split", fields=["P31"]),
    )

    assert result["consensus_level"] == "no_consensus"
    assert result["consensus_identity"] == ""
    assert any("No consistent entity identifier" in note for note in result["disagreements"])
