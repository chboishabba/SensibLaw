from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sensiblaw.event_participants import (
    ActorSummary,
    EventParticipantCreate,
    EventParticipantService,
    EventParticipantUpdate,
)


def test_insert_derives_actor_class_and_requires_unique_triplet():
    service = EventParticipantService({1: ActorSummary(id=1, actor_class_id=7)})

    created = service.insert_participant(
        EventParticipantCreate(
            event_id=5,
            actor_id=1,
            actor_class_id=None,
            role_marker_id=None,
            role_label="plaintiff",
            participation_note=None,
        )
    )

    assert created.actor_id == 1
    assert created.actor_class_id == 7

    with pytest.raises(ValueError):
        service.insert_participant(
            EventParticipantCreate(
                event_id=5,
                actor_id=1,
                actor_class_id=None,
                role_marker_id=None,
                role_label="plaintiff",
                participation_note=None,
            )
        )


def test_update_requires_actor_and_checks_uniqueness():
    service = EventParticipantService({1: ActorSummary(id=1, actor_class_id=7)})
    created = service.insert_participant(
        EventParticipantCreate(
            event_id=8,
            actor_id=1,
            actor_class_id=None,
            role_marker_id=2,
            role_label="respondent",
            participation_note="Initial",
        )
    )

    updated = service.update_participant(
        created.id,
        EventParticipantUpdate(
            actor_id=1,
            actor_class_id=None,
            role_marker_id=3,
            role_label="appellant",
            participation_note="Changed role",
        ),
    )

    assert updated.role_marker_id == 3
    assert updated.role_label == "appellant"

    with pytest.raises(ValueError):
        service.insert_participant(
            EventParticipantCreate(
                event_id=8,
                actor_id=1,
                actor_class_id=None,
                role_marker_id=3,
                role_label="appellant",
                participation_note=None,
            )
        )


