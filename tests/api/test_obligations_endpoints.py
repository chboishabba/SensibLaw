import pytest

from sensiblaw.api import routes
from src.obligation_alignment import ALIGNMENT_SCHEMA_VERSION
from src.obligation_projections import PROJECTION_SCHEMA_VERSION
from src.obligation_views import EXPLANATION_SCHEMA_VERSION, QUERY_SCHEMA_VERSION


TEXT = (
    "The operator must keep records within 7 days.\n"
    "A person must not enter the area on the premises.\n"
    "The licence holder must notify on commencement and ceases upon revocation."
)


def test_query_endpoint_filters_actor():
    payload = routes.ObligationRequest(
        text=TEXT,
        source_id="doc",
        filters=routes.ObligationFilters(actor="the operator"),
    )
    data = routes.obligations_query(payload)
    assert data["version"] == QUERY_SCHEMA_VERSION
    actors = [item["actor"]["normalized"] for item in data["results"] if item.get("actor")]
    assert actors == ["the operator"]


def test_explain_endpoint_returns_clause_local_atoms():
    request = routes.ObligationRequest(text=TEXT, source_id="doc")
    data = routes.obligations_explain(request)
    assert data["version"] == EXPLANATION_SCHEMA_VERSION
    first = data["explanations"][0]
    assert first["atoms"]["actor"]["normalized"] == "the operator"
    assert first["clause_id"].startswith("doc-clause-0")


def test_alignment_endpoint_reports_added():
    old_text = TEXT.split("\n")[0]
    request = routes.AlignmentRequest(old_text=old_text, new_text=TEXT, source_id="doc")
    data = routes.obligations_alignment(request)
    assert data["version"] == ALIGNMENT_SCHEMA_VERSION
    assert len(data["added"]) == 2  # two extra clauses in new text


def test_projections_endpoint_actor_view_is_sorted():
    request = routes.ObligationRequest(text=TEXT)
    data = routes.obligations_projections("actor", request)
    assert data["version"] == PROJECTION_SCHEMA_VERSION
    actors = [entry["actor"] for entry in data["results"]]
    assert actors == ["person", "the licence holder", "the operator"]


def test_projections_invalid_view_returns_400():
    request = routes.ObligationRequest(text=TEXT)
    with pytest.raises(routes.HTTPException):
        routes.obligations_projections("unknown", request)
