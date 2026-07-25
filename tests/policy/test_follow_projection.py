from __future__ import annotations

from src.policy.follow_projection import build_follow_projection, project_follow_view


def test_follow_projection_is_deterministic_and_derived_only() -> None:
    kwargs = {
        "document_ref": "document:one",
        "projection_kind": "legal_follow",
        "nodes": (
            {"id": "source", "kind": "source", "label": "Source"},
            {"id": "target", "kind": "candidate", "label": "Target"},
        ),
        "edges": (
            {
                "source": "source",
                "target": "target",
                "kind": "supports",
                "provenance_refs": ("source:one",),
                "admissibility_ground_refs": ("ground:one",),
            },
        ),
    }
    first = build_follow_projection(**kwargs)
    second = build_follow_projection(**kwargs)

    assert first["projection_ref"] == second["projection_ref"]
    assert first["authority"] == "derived_only_challengeable"
    assert first["promotion_allowed"] is False
    assert first["execution_allowed"] is False
    assert first["edges"][0]["provenance_refs"] == ["source:one"]

    view = project_follow_view(first)
    assert view["nodes"] == first["nodes"]
    assert view["edges"] == first["edges"]
