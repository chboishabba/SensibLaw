"""Framework-neutral semantic reading projection and interaction boundary.

This module does not own canonical legal identity or PNF semantics. It carries
references to those surfaces plus source spans, display metadata, and reading
navigation state. UI interpreters may render the projection and emit admitted
intents, but clicks do not acquire semantic-authority or identity-promotion
powers merely by crossing this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SemanticTarget:
    """A source-bound target exposed to a reading interpreter.

    `semantic_ref` is a reference coordinate, not a proof that identity has
    been promoted or verified. Overlapping spans are intentionally allowed.
    """

    target_id: str
    source_artifact_id: str
    char_start: int
    char_end: int
    display_text: str
    semantic_ref: str
    target_kind: str
    authority_kind: str = "projection"
    role_overlays: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("target_id must be non-empty")
        if not self.source_artifact_id:
            raise ValueError("source_artifact_id must be non-empty")
        if self.char_start < 0 or self.char_end <= self.char_start:
            raise ValueError("invalid target character span")
        if not self.semantic_ref:
            raise ValueError("semantic_ref must be non-empty")


@dataclass(frozen=True, slots=True)
class ReadingWorld:
    """The complete target bucket for the current bounded reading context."""

    source_text: str
    targets: Mapping[str, SemanticTarget]

    @classmethod
    def from_targets(
        cls,
        source_text: str,
        targets: tuple[SemanticTarget, ...],
    ) -> "ReadingWorld":
        by_id = {target.target_id: target for target in targets}
        if len(by_id) != len(targets):
            raise ValueError("duplicate target_id in reading world")
        for target in targets:
            if target.char_end > len(source_text):
                raise ValueError(f"target span outside source text: {target.target_id}")
        return cls(source_text=source_text, targets=MappingProxyType(by_id))


@dataclass(frozen=True, slots=True)
class ReadingProjection:
    """Visible subset of a ReadingWorld; omission does not delete a target."""

    visible_target_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReadingTrailState:
    """Navigation state over a stable world bucket."""

    world: ReadingWorld
    trail: tuple[str, ...] = ()
    active_target_id: str | None = None


@dataclass(frozen=True, slots=True)
class FollowTarget:
    target_id: str


class IntentAdmissionError(ValueError):
    """Structured interaction failed the reading-boundary admission contract."""


def parse_reading_intent(payload: Mapping[str, object]) -> FollowTarget:
    """Decode the small JCUI-shaped wire vocabulary into a domain intent."""

    if payload.get("kind") != "FollowTarget":
        raise IntentAdmissionError("unsupported reading intent kind")
    target_id = payload.get("targetId")
    if not isinstance(target_id, str) or not target_id.strip():
        raise IntentAdmissionError("FollowTarget requires a non-empty targetId")
    return FollowTarget(target_id=target_id)


def reduce_reading_intent(
    state: ReadingTrailState,
    intent: FollowTarget,
) -> ReadingTrailState:
    """Apply an admitted reading intent to navigation only.

    The world object is retained exactly; following a target cannot rewrite its
    semantic reference, authority kind, role overlays, source span, or peers.
    """

    if intent.target_id not in state.world.targets:
        raise IntentAdmissionError(f"unknown reading target: {intent.target_id}")
    return replace(
        state,
        trail=state.trail + (intent.target_id,),
        active_target_id=intent.target_id,
    )


def project_reading_view(
    state: ReadingTrailState,
    projection: ReadingProjection,
) -> dict[str, object]:
    """Project state into a JSON-compatible interpreter surface.

    Wire span keys follow the repository's producer-owned text-debug convention.
    The returned mapping is presentation data, not canonical semantic state.
    """

    targets: list[dict[str, object]] = []
    for target_id in projection.visible_target_ids:
        if target_id not in state.world.targets:
            raise ValueError(f"projection references unknown target: {target_id}")
        target = state.world.targets[target_id]
        targets.append(
            {
                "targetId": target.target_id,
                "sourceArtifactId": target.source_artifact_id,
                "charStart": target.char_start,
                "charEnd": target.char_end,
                "displayText": target.display_text,
                "semanticRef": target.semantic_ref,
                "targetKind": target.target_kind,
                "authorityKind": target.authority_kind,
                "roleOverlays": list(target.role_overlays),
            }
        )
    return {
        "sourceText": state.world.source_text,
        "targets": targets,
        "trail": list(state.trail),
        "activeTargetId": state.active_target_id,
    }


def _target_for_surface(
    *,
    target_id: str,
    source_artifact_id: str,
    source_text: str,
    surface: str,
    semantic_ref: str,
    target_kind: str,
    authority_kind: str = "projection",
    role_overlays: tuple[str, ...] = (),
    occurrence: int = 0,
) -> SemanticTarget:
    """Build a deterministic target for a named surface occurrence."""

    cursor = -1
    start = 0
    try:
        for _ in range(occurrence + 1):
            cursor = source_text.index(surface, start)
            start = cursor + len(surface)
    except ValueError as exc:
        raise ValueError(f"surface not found in reading fixture: {surface!r}") from exc
    return SemanticTarget(
        target_id=target_id,
        source_artifact_id=source_artifact_id,
        char_start=cursor,
        char_end=cursor + len(surface),
        display_text=surface,
        semantic_ref=semantic_ref,
        target_kind=target_kind,
        authority_kind=authority_kind,
        role_overlays=role_overlays,
    )


def build_mabo_reading_fixture() -> tuple[ReadingTrailState, ReadingProjection]:
    """Return the deterministic v0 Mabo reading interaction specimen.

    The sentence is intentionally synthetic and must not be represented as a
    quotation from the judgment. The Mabo target reuses the repository's
    canonical AU-semantic key; the remaining references are bounded reading
    coordinates for this fixture.
    """

    source_text = "Mabo recognised native title in Australian common law."
    source_artifact_id = "fixture:mabo_reading_v0"

    targets = (
        _target_for_surface(
            target_id="legal_ref:mabo_v_queensland_no_2",
            source_artifact_id=source_artifact_id,
            source_text=source_text,
            surface="Mabo",
            semantic_ref="legal_ref:mabo_v_queensland_no_2",
            target_kind="legal_ref",
            authority_kind="legal_authority_reference",
            role_overlays=("subject",),
        ),
        _target_for_surface(
            target_id="action:recognised",
            source_artifact_id=source_artifact_id,
            source_text=source_text,
            surface="recognised",
            semantic_ref="action:recognised",
            target_kind="action",
            role_overlays=("predicate",),
        ),
        _target_for_surface(
            target_id="concept:native_title",
            source_artifact_id=source_artifact_id,
            source_text=source_text,
            surface="native title",
            semantic_ref="concept:native_title",
            target_kind="composite_concept",
            role_overlays=("object",),
        ),
        _target_for_surface(
            target_id="lexeme:title",
            source_artifact_id=source_artifact_id,
            source_text=source_text,
            surface="title",
            semantic_ref="lexeme:title",
            target_kind="constituent",
        ),
        SemanticTarget(
            target_id="context:wikipedia_mabo",
            source_artifact_id=source_artifact_id,
            char_start=0,
            char_end=4,
            display_text="Mabo context",
            semantic_ref="context:wikipedia_mabo",
            target_kind="context_link",
            authority_kind="context",
        ),
    )

    world = ReadingWorld.from_targets(source_text, targets)
    projection = ReadingProjection(
        visible_target_ids=(
            "legal_ref:mabo_v_queensland_no_2",
            "action:recognised",
            "concept:native_title",
            "lexeme:title",
        )
    )
    return ReadingTrailState(world=world), projection
