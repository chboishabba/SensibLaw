"""API routes for story import, event checking, and rule extraction."""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rules.extractor import extract_rules
from src.activation import (
    ACTIVATION_VERSION,
    FACT_ENVELOPE_VERSION,
    Fact,
    FactEnvelope,
    activation_to_payload,
    simulate_activation,
)
from src.obligation_alignment import ALIGNMENT_SCHEMA_VERSION, align_obligations, alignment_to_payload
from src.obligation_projections import (
    PROJECTION_SCHEMA_VERSION,
    action_view,
    actor_view,
    clause_view,
    timeline_view,
)
from src.obligation_views import (
    EXPLANATION_SCHEMA_VERSION,
    QUERY_SCHEMA_VERSION,
    build_explanations,
    explanations_to_payload,
    obligations_to_query_payload,
    query_obligations,
)
from src.obligations import extract_obligations_from_text

PROJECTION_HANDLERS = {
    "actor": actor_view,
    "action": action_view,
    "clause": clause_view,
    "timeline": timeline_view,
}

router = APIRouter()

# In-memory store for imported stories
_STORIES: Dict[str, "Story"] = {}


class Story(BaseModel):
    """Simple representation of a story with optional events."""

    id: str
    events: List[str] = []


@router.post("/import_stories")
def import_stories(stories: List[Story]) -> Dict[str, int]:
    """Import a list of stories.

    The stories are kept in-memory for demonstration purposes and keyed by
    their ``id``.  The endpoint returns the number of imported stories.
    """

    for story in stories:
        _STORIES[story.id] = story
    return {"imported": len(stories)}


class EventCheck(BaseModel):
    """Payload for checking whether a story contains a given event."""

    story_id: str
    event: str


@router.post("/check_event")
def check_event(payload: EventCheck) -> Dict[str, bool]:
    """Return ``True`` if ``event`` is present in the story's events."""

    story = _STORIES.get(payload.story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return {"event_present": payload.event in story.events}


class RuleRequest(BaseModel):
    """Request body for rule extraction."""

    text: str


@router.post("/rules")
def rules_endpoint(request: RuleRequest) -> Dict[str, List[Dict[str, str]]]:
    """Extract normative rules from ``text`` using heuristic regexes."""

    rules = [asdict(rule) for rule in extract_rules(request.text)]
    return {"rules": rules}


# Sprint 7: read-only obligation surfaces ------------------------------------


class ObligationFilters(BaseModel):
    """Optional filters for obligation query."""

    actor: Optional[str] = None
    action: Optional[str] = None
    object: Optional[str] = None
    scope_category: Optional[str] = None
    scope_text: Optional[str] = None
    lifecycle_kind: Optional[str] = None
    clause_id: Optional[str] = None
    modality: Optional[str] = None
    reference_id: Optional[str] = None


class ObligationRequest(BaseModel):
    """Base request for obligation extraction."""

    text: str
    source_id: str = "document"
    enable_actor_binding: Optional[bool] = None
    enable_action_binding: Optional[bool] = None
    filters: Optional[ObligationFilters] = None


class AlignmentRequest(BaseModel):
    """Request to align obligations between two texts."""

    old_text: str
    new_text: str
    source_id: str = "document"
    enable_actor_binding: Optional[bool] = None
    enable_action_binding: Optional[bool] = None


class FactModel(BaseModel):
    key: str
    value: object
    at: Optional[str] = None
    source: Optional[str] = None


class FactEnvelopeModel(BaseModel):
    version: str = FACT_ENVELOPE_VERSION
    issued_at: Optional[str] = None
    facts: List[FactModel] = []


def _extract(text: str, request: ObligationRequest | AlignmentRequest) -> list:
    """Helper: extract obligations using the provided feature flags."""

    return extract_obligations_from_text(
        text,
        source_id=request.source_id,
        enable_actor_binding=getattr(request, "enable_actor_binding", None),
        enable_action_binding=getattr(request, "enable_action_binding", None),
    )


@router.post("/obligations/query")
def obligations_query(request: ObligationRequest) -> Dict[str, object]:
    """Filter obligations using deterministic read-only criteria."""

    obligations = _extract(request.text, request)
    filters = request.filters or ObligationFilters()
    filtered = query_obligations(
        obligations,
        actor=filters.actor,
        action=filters.action,
        obj=filters.object,
        scope_category=filters.scope_category,
        scope_text=filters.scope_text,
        lifecycle_kind=filters.lifecycle_kind,
        clause_id=filters.clause_id,
        modality=filters.modality,
        reference_id=filters.reference_id,
    )
    return obligations_to_query_payload(filtered)


@router.post("/obligations/explain")
def obligations_explain(request: ObligationRequest) -> Dict[str, object]:
    """Return clause-local explanations for each obligation."""

    obligations = _extract(request.text, request)
    explanations = build_explanations(request.text, obligations, source_id=request.source_id)
    return explanations_to_payload(explanations)


@router.post("/obligations/alignment")
def obligations_alignment(request: AlignmentRequest) -> Dict[str, object]:
    """Compute metadata-only obligation alignment between two texts."""

    old_obs = _extract(request.old_text, request)
    new_obs = _extract(request.new_text, request)
    report = align_obligations(old_obs, new_obs)
    payload = alignment_to_payload(report)
    payload["version"] = ALIGNMENT_SCHEMA_VERSION
    return payload


@router.post("/obligations/projections/{view}")
def obligations_projections(view: str, request: ObligationRequest) -> Dict[str, object]:
    """Return deterministic projection views over extracted obligations."""

    handler = PROJECTION_HANDLERS.get(view)
    if handler is None:
        raise HTTPException(status_code=400, detail="Unknown projection view")
    obligations = _extract(request.text, request)
    return {
        "version": PROJECTION_SCHEMA_VERSION,
        "view": view,
        "results": handler(obligations),
    }


def _to_envelope(model: FactEnvelopeModel) -> FactEnvelope:
    if model.version != FACT_ENVELOPE_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported fact envelope version")
    return FactEnvelope(
        version=model.version,
        issued_at=model.issued_at,
        facts=[Fact(key=f.key, value=f.value, at=f.at, source=f.source) for f in model.facts],
    )


class ActivationRequest(BaseModel):
    """Request to simulate activation."""

    text: str
    source_id: str = "document"
    enable_actor_binding: Optional[bool] = None
    enable_action_binding: Optional[bool] = None
    facts: FactEnvelopeModel


@router.post("/obligations/activate")
def obligations_activate(request: ActivationRequest) -> Dict[str, object]:
    """Simulate activation state for obligations using declared facts."""

    obligations = _extract(request.text, request)
    envelope = _to_envelope(request.facts)
    result = simulate_activation(obligations, envelope)
    payload = activation_to_payload(result)
    return {
        "version": ACTIVATION_VERSION,
        "obligations": obligations_to_query_payload(obligations)["results"],
        "activation": payload,
    }
