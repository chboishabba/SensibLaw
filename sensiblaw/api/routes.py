"""API routes for story import, event checking, and rule extraction."""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rules.extractor import extract_rules

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
