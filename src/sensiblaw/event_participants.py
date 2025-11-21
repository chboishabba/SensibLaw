from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, MutableMapping, Tuple

from pydantic import BaseModel, ConfigDict, Field


@dataclass
class ActorSummary:
    """Lightweight actor view used for deriving classifications."""

    id: int
    actor_class_id: int | None = None


class EventParticipantBase(BaseModel):
    event_id: int = Field(..., gt=0)
    actor_id: int = Field(..., gt=0)
    actor_class_id: int | None = Field(None, gt=0)
    role_marker_id: int | None = Field(None, gt=0)
    role_label: str | None = None
    participation_note: str | None = None

    model_config = ConfigDict(extra="forbid")


class EventParticipantCreate(EventParticipantBase):
    """DTO used when inserting a new event participant."""


class EventParticipantUpdate(BaseModel):
    actor_id: int = Field(..., gt=0)
    actor_class_id: int | None = Field(None, gt=0)
    role_marker_id: int | None = Field(None, gt=0)
    role_label: str | None = None
    participation_note: str | None = None

    model_config = ConfigDict(extra="forbid")


class EventParticipantDTO(EventParticipantBase):
    id: int


class EventParticipantService:
    """In-memory service enforcing participant integrity constraints."""

    def __init__(
        self,
        actor_registry: Mapping[int, ActorSummary] | None = None,
        *,
        store: MutableMapping[int, EventParticipantDTO] | None = None,
    ) -> None:
        self._actors: Mapping[int, ActorSummary] = actor_registry or {}
        self._store: MutableMapping[int, EventParticipantDTO] = store or {}
        self._next_id = max(self._store.keys(), default=0) + 1
        self._unique_index: Dict[Tuple[int, int, int], int] = {}
        for participant in self._store.values():
            key = self._unique_key(
                participant.event_id, participant.actor_id, participant.role_marker_id
            )
            self._unique_index[key] = participant.id

    @staticmethod
    def _unique_key(event_id: int, actor_id: int, role_marker_id: int | None) -> Tuple[int, int, int]:
        return (event_id, actor_id, role_marker_id or -1)

    def _derive_actor_class_id(
        self, *, actor_id: int, explicit_actor_class_id: int | None
    ) -> int:
        if explicit_actor_class_id:
            return explicit_actor_class_id
        actor = self._actors.get(actor_id)
        if actor and actor.actor_class_id:
            return actor.actor_class_id
        msg = "actor_class_id is required when the actor registry lacks a classification"
        raise ValueError(msg)

    def _assert_unique(self, event_id: int, actor_id: int, role_marker_id: int | None) -> None:
        key = self._unique_key(event_id, actor_id, role_marker_id)
        if key in self._unique_index:
            msg = "Participant already exists for this event, actor, and role marker"
            raise ValueError(msg)

    def insert_participant(self, payload: EventParticipantCreate) -> EventParticipantDTO:
        actor_class_id = self._derive_actor_class_id(
            actor_id=payload.actor_id, explicit_actor_class_id=payload.actor_class_id
        )
        self._assert_unique(payload.event_id, payload.actor_id, payload.role_marker_id)
        participant = EventParticipantDTO(
            id=self._next_id,
            event_id=payload.event_id,
            actor_id=payload.actor_id,
            actor_class_id=actor_class_id,
            role_marker_id=payload.role_marker_id,
            role_label=payload.role_label,
            participation_note=payload.participation_note,
        )
        self._store[participant.id] = participant
        self._unique_index[
            self._unique_key(
                participant.event_id, participant.actor_id, participant.role_marker_id
            )
        ] = participant.id
        self._next_id += 1
        return participant

    def update_participant(
        self, participant_id: int, payload: EventParticipantUpdate
    ) -> EventParticipantDTO:
        if participant_id not in self._store:
            msg = f"Unknown participant id: {participant_id}"
            raise KeyError(msg)

        existing = self._store[participant_id]
        actor_class_id = self._derive_actor_class_id(
            actor_id=payload.actor_id, explicit_actor_class_id=payload.actor_class_id
        )
        new_role_marker_id = payload.role_marker_id
        new_key = self._unique_key(
            existing.event_id, payload.actor_id, new_role_marker_id
        )
        old_key = self._unique_key(
            existing.event_id, existing.actor_id, existing.role_marker_id
        )
        if new_key != old_key and new_key in self._unique_index:
            msg = "Participant already exists for this event, actor, and role marker"
            raise ValueError(msg)

        self._unique_index.pop(old_key, None)
        self._unique_index[new_key] = participant_id

        updated = EventParticipantDTO(
            id=participant_id,
            event_id=existing.event_id,
            actor_id=payload.actor_id,
            actor_class_id=actor_class_id,
            role_marker_id=new_role_marker_id,
            role_label=payload.role_label,
            participation_note=payload.participation_note,
        )
        self._store[participant_id] = updated
        return updated


__all__ = [
    "ActorSummary",
    "EventParticipantBase",
    "EventParticipantCreate",
    "EventParticipantDTO",
    "EventParticipantService",
    "EventParticipantUpdate",
]
