"""Typed evidence, reconciliation, PNF refinement, and readiness carriers.

Evidence acquisition never selects identity; reconciliation never promotes a
claim; refinement changes only a declared PNF factor; readiness remains
review-only and carries no editing authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

EVIDENCE_AUTHORITY = "evidence_only"
ASSESSMENT_AUTHORITY = "assessment_only"
REFINEMENT_AUTHORITY = "pnf_refinement_only"
READINESS_AUTHORITY = "review_only"


def _text(value: Any, field_name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    return value


def _refs(values: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(sorted({_text(value, "reference") for value in values or ()}))


def _json(value: Mapping[str, Any] | None) -> dict[str, Any]:
    encoded = json.dumps(dict(value or {}), sort_keys=True, separators=(",", ":"))
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise ValueError("payload must be a JSON object")
    return decoded


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class EvidenceRole(str, Enum):
    ENTITY = "entity"
    EVENT_TYPE = "event_type"
    OCCURRENCE = "occurrence"
    OBSERVATION = "observation"
    CLUSTER = "cluster"
    FORECAST = "forecast"
    REPORT = "report"
    ALERT = "alert"
    ROLLING_STATE = "rolling_state"
    PROPERTY_OR_RELATION = "property_or_relation"
    DOCUMENT_LOCAL_CLUSTER = "document_local_cluster"


class MeetState(str, Enum):
    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_REFINEMENT = "compatible_with_refinement"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"
    NO_TYPED_MEET = "no_typed_meet"
    CONTRADICTION = "contradiction"
    NOT_EVALUATED = "not_evaluated"


class ResolutionOutcome(str, Enum):
    RESOLVED = "resolved"
    POSSIBLE_SAME = "possible_same"
    RELATED_DISTINCT = "related_distinct"
    NO_TYPED_MEET = "no_typed_meet"
    CONTRADICTION = "contradiction"
    NOT_EVALUATED = "not_evaluated"
    BUDGET_EXHAUSTED = "budget_exhausted"


class ReadinessOutcome(str, Enum):
    PROMOTE = "promote"
    HOLD = "hold"
    ABSTAIN = "abstain"
    AUDIT = "audit"


@dataclass(frozen=True)
class ResolutionEvidenceSnapshot:
    snapshot_ref: str
    backend_ref: str
    subject_ref: str
    evidence_role: EvidenceRole | str
    external_ref: str | None = None
    labels: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    type_refs: tuple[str, ...] = ()
    temporal: Mapping[str, Any] = field(default_factory=dict)
    spatial: Mapping[str, Any] = field(default_factory=dict)
    participants: Mapping[str, Sequence[str]] = field(default_factory=dict)
    relations: Mapping[str, Sequence[str]] = field(default_factory=dict)
    lineage_refs: tuple[str, ...] = ()
    observation_refs: tuple[str, ...] = ()
    revision_ref: str | None = None
    fetched_at: str | None = None
    provenance_refs: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        provenance = _refs(self.provenance_refs)
        if not provenance:
            raise ValueError("evidence snapshots require provenance")
        row = {
            "schema_version": "sl.resolution_evidence.v0_1",
            "snapshot_ref": _text(self.snapshot_ref, "snapshot_ref"),
            "backend_ref": _text(self.backend_ref, "backend_ref"),
            "subject_ref": _text(self.subject_ref, "subject_ref"),
            "evidence_role": EvidenceRole(self.evidence_role).value,
            "labels": list(_refs(self.labels)),
            "aliases": list(_refs(self.aliases)),
            "type_refs": list(_refs(self.type_refs)),
            "temporal": _json(self.temporal),
            "spatial": _json(self.spatial),
            "participants": {
                _text(role, "participant role"): list(_refs(refs))
                for role, refs in sorted(self.participants.items())
            },
            "relations": {
                _text(kind, "relation kind"): list(_refs(refs))
                for kind, refs in sorted(self.relations.items())
            },
            "lineage_refs": list(_refs(self.lineage_refs)),
            "observation_refs": list(_refs(self.observation_refs)),
            "provenance_refs": list(provenance),
            "payload": _json(self.payload),
            "authority": EVIDENCE_AUTHORITY,
        }
        for key, value in (
            ("external_ref", self.external_ref),
            ("revision_ref", self.revision_ref),
            ("fetched_at", self.fetched_at),
        ):
            if value:
                row[key] = _text(value, key)
        row["snapshot_sha256"] = _digest(row)
        return row


def build_document_local_evidence(
    *,
    demand: Mapping[str, Any],
    mentions: Sequence[Mapping[str, Any]],
    form_relations: Sequence[Mapping[str, Any]] = (),
    coreference_clusters: Sequence[Mapping[str, Any]] = (),
    local_types: Sequence[Mapping[str, Any]] = (),
    discourse_relations: Sequence[Mapping[str, Any]] = (),
) -> tuple[ResolutionEvidenceSnapshot, ...]:
    """Project all matching local evidence without choosing an identity."""
    demand_ref = _text(demand.get("demand_ref"), "demand_ref")
    mention_ref = _text(demand.get("mention_ref"), "mention_ref")
    mention = next(
        (row for row in mentions if str(row.get("mention_ref")) == mention_ref), None
    )
    if not mention:
        return ()
    document_ref = _text(mention.get("document_ref"), "document_ref")
    subject_ref = str(demand.get("subject_ref") or mention_ref)
    snapshots: list[ResolutionEvidenceSnapshot] = []
    for cluster in sorted(
        coreference_clusters, key=lambda row: str(row.get("cluster_ref"))
    ):
        members = {str(ref) for ref in cluster.get("mention_refs") or ()}
        if mention_ref not in members:
            continue
        if str(cluster.get("document_ref") or document_ref) != document_ref:
            continue
        snapshots.append(
            ResolutionEvidenceSnapshot(
                snapshot_ref=f"local:{demand_ref}:cluster:{cluster['cluster_ref']}",
                backend_ref="document_local",
                subject_ref=subject_ref,
                evidence_role=EvidenceRole.DOCUMENT_LOCAL_CLUSTER,
                external_ref=str(cluster["cluster_ref"]),
                labels=(str(mention.get("canonical_surface") or ""),),
                relations={"corefers_with": tuple(sorted(members - {mention_ref}))},
                provenance_refs=(
                    f"document:{document_ref}",
                    f"cluster:{cluster['cluster_ref']}",
                ),
                payload={"member_mentions": sorted(members)},
            )
        )
    for local_type in sorted(
        local_types, key=lambda row: str(row.get("type_ref"))
    ):
        if str(local_type.get("mention_ref")) != mention_ref:
            continue
        types = local_type.get("type_refs") or (local_type.get("local_type"),)
        snapshots.append(
            ResolutionEvidenceSnapshot(
                snapshot_ref=f"local:{demand_ref}:type:{local_type.get('type_ref')}",
                backend_ref="document_local",
                subject_ref=subject_ref,
                evidence_role=EvidenceRole.ENTITY,
                labels=(str(mention.get("canonical_surface") or ""),),
                type_refs=tuple(str(value) for value in types if value),
                provenance_refs=tuple(
                    local_type.get("provenance_refs")
                    or (f"document:{document_ref}",)
                ),
                payload={"local_type": dict(local_type)},
            )
        )
    related_forms = [
        row
        for row in form_relations
        if mention_ref
        in {
            str(row.get("left_mention_ref")),
            str(row.get("right_mention_ref")),
            str(row.get("mention_ref")),
        }
    ]
    related_discourse = [
        row
        for row in discourse_relations
        if mention_ref
        in {
            str(row.get("left_ref")),
            str(row.get("right_ref")),
            str(row.get("mention_ref")),
        }
    ]
    if related_forms or related_discourse:
        snapshots.append(
            ResolutionEvidenceSnapshot(
                snapshot_ref=f"local:{demand_ref}:relations",
                backend_ref="document_local",
                subject_ref=subject_ref,
                evidence_role=EvidenceRole.ENTITY,
                labels=(str(mention.get("canonical_surface") or ""),),
                relations={
                    "form_relation": tuple(
                        str(row.get("relation_ref")) for row in related_forms
                    ),
                    "discourse_relation": tuple(
                        str(row.get("relation_ref")) for row in related_discourse
                    ),
                },
                provenance_refs=(f"document:{document_ref}",),
            )
        )
    return tuple(snapshots)


def adapt_wikidata_snapshot(
    *,
    subject_ref: str,
    entity: Mapping[str, Any],
    requested_revision: str,
    provenance_refs: Sequence[str],
) -> ResolutionEvidenceSnapshot:
    entity_id = _text(entity.get("id") or entity.get("entity_id"), "entity id")
    revision = _text(entity.get("revision") or entity.get("lastrevid"), "revision")
    if revision != _text(requested_revision, "requested revision"):
        raise ValueError("Wikidata snapshot revision does not match requested revision")
    labels = entity.get("labels") or ()
    if isinstance(labels, Mapping):
        labels = tuple(
            str(value.get("value") if isinstance(value, Mapping) else value)
            for value in labels.values()
        )
    aliases = entity.get("aliases") or ()
    if isinstance(aliases, Mapping):
        aliases = tuple(
            str(alias.get("value") if isinstance(alias, Mapping) else alias)
            for values in aliases.values()
            for alias in (
                values
                if isinstance(values, Sequence) and not isinstance(values, str)
                else (values,)
            )
        )
    properties = entity.get("properties") or entity.get("claims") or {}
    type_refs: list[str] = []
    relations: dict[str, tuple[str, ...]] = {}
    if isinstance(properties, Mapping):
        for prop, values in properties.items():
            refs: list[str] = []
            rows = (
                values
                if isinstance(values, Sequence) and not isinstance(values, (str, bytes))
                else (values,)
            )
            for value in rows:
                if not isinstance(value, Mapping):
                    continue
                ref = value.get("entity_ref") or value.get("value") or value.get("id")
                if isinstance(ref, Mapping):
                    ref = ref.get("id")
                if ref:
                    refs.append(str(ref))
            if refs:
                relations[str(prop)] = tuple(refs)
                if str(prop) in {"P31", "P279"}:
                    type_refs.extend(refs)
    return ResolutionEvidenceSnapshot(
        snapshot_ref=f"wikidata:{entity_id}@{revision}",
        backend_ref="wikidata",
        subject_ref=subject_ref,
        evidence_role=EvidenceRole.ENTITY,
        external_ref=entity_id,
        labels=tuple(labels),
        aliases=tuple(aliases),
        type_refs=tuple(type_refs),
        relations=relations,
        revision_ref=revision,
        provenance_refs=tuple(provenance_refs),
        payload={"requested_revision": requested_revision},
    )


def adapt_worldmonitor_snapshot(
    *,
    subject_ref: str,
    record: Mapping[str, Any],
    record_role: EvidenceRole | str,
    snapshot_version: str,
    provenance_refs: Sequence[str],
) -> ResolutionEvidenceSnapshot:
    role = EvidenceRole(record_role)
    if role not in {
        EvidenceRole.OCCURRENCE,
        EvidenceRole.OBSERVATION,
        EvidenceRole.CLUSTER,
        EvidenceRole.FORECAST,
        EvidenceRole.REPORT,
        EvidenceRole.ALERT,
        EvidenceRole.ROLLING_STATE,
    }:
        raise ValueError("WorldMonitor records require an event formal role")
    record_id = _text(
        record.get("id") or record.get("canonical_id"), "WorldMonitor record id"
    )
    temporal = {
        key: record[key]
        for key in (
            "date",
            "started_at",
            "ended_at",
            "observed_at",
            "reported_at",
            "updated_at",
            "forecast_for",
        )
        if record.get(key) is not None
    }
    spatial = {
        key: record[key]
        for key in ("lat", "lon", "location", "country", "region", "geometry")
        if record.get(key) is not None
    }
    participants = record.get("participants") or {}
    if not isinstance(participants, Mapping):
        participants = {"participant": tuple(str(value) for value in participants)}
    types = tuple(
        str(value)
        for value in (
            record.get("category"),
            record.get("category_title"),
            record.get("classification"),
            record.get("event_type"),
        )
        if value
    )
    observations = record.get("agency_observations") or record.get("observations") or ()
    observation_refs = tuple(
        str(row.get("id") or row.get("agency_id") or index)
        for index, row in enumerate(observations)
        if isinstance(row, Mapping)
    )
    lineage = tuple(
        str(value)
        for value in (
            record.get("source_name"),
            record.get("source_url"),
            *(record.get("lineage_refs") or ()),
        )
        if value
    )
    labels = tuple(
        str(value)
        for value in (record.get("title"), record.get("storm_name"), record.get("name"))
        if value
    )
    return ResolutionEvidenceSnapshot(
        snapshot_ref=f"worldmonitor:{record_id}@{_text(snapshot_version, 'snapshot version')}",
        backend_ref="worldmonitor",
        subject_ref=subject_ref,
        evidence_role=role,
        external_ref=record_id,
        labels=labels,
        aliases=tuple(str(value) for value in record.get("canonical_aliases") or ()),
        type_refs=types,
        temporal=temporal,
        spatial=spatial,
        participants=participants,
        lineage_refs=lineage,
        observation_refs=observation_refs,
        revision_ref=snapshot_version,
        provenance_refs=tuple(provenance_refs),
        payload={
            "closed": record.get("closed"),
            "magnitude": record.get("magnitude"),
            "magnitude_unit": record.get("magnitude_unit"),
            "matching_confidence": record.get("matching_confidence"),
        },
    )


@dataclass(frozen=True)
class CompatibilityCoordinate:
    coordinate: str
    state: MeetState | str
    relation: str | None = None
    evidence_refs: tuple[str, ...] = ()
    residual_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        row = {
            "coordinate": _text(self.coordinate, "coordinate"),
            "state": MeetState(self.state).value,
            "evidence_refs": list(_refs(self.evidence_refs)),
            "residual_refs": list(_refs(self.residual_refs)),
        }
        if self.relation:
            row["relation"] = _text(self.relation, "relation")
        return row


@dataclass(frozen=True)
class ResolutionAssessment:
    assessment_ref: str
    subject_ref: str
    left_ref: str
    right_ref: str
    subject_kind: str
    coordinates: tuple[CompatibilityCoordinate, ...]
    outcome: ResolutionOutcome | str
    selected_identity_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        rows = tuple(
            sorted(
                (coordinate.to_dict() for coordinate in self.coordinates),
                key=lambda row: row["coordinate"],
            )
        )
        states = {row["state"] for row in rows}
        outcome = ResolutionOutcome(self.outcome)
        if "contradiction" in states and outcome != ResolutionOutcome.CONTRADICTION:
            raise ValueError("contradictory coordinates require contradiction outcome")
        if "no_typed_meet" in states and outcome not in {
            ResolutionOutcome.NO_TYPED_MEET,
            ResolutionOutcome.CONTRADICTION,
        }:
            raise ValueError("no-typed-meet coordinates cannot resolve")
        if outcome == ResolutionOutcome.RESOLVED and not self.selected_identity_ref:
            raise ValueError("resolved assessments require selected_identity_ref")
        row = {
            "schema_version": "sl.resolution_assessment.v0_1",
            "assessment_ref": _text(self.assessment_ref, "assessment_ref"),
            "subject_ref": _text(self.subject_ref, "subject_ref"),
            "left_ref": _text(self.left_ref, "left_ref"),
            "right_ref": _text(self.right_ref, "right_ref"),
            "subject_kind": _text(self.subject_kind, "subject_kind"),
            "coordinates": list(rows),
            "outcome": outcome.value,
            "authority": ASSESSMENT_AUTHORITY,
        }
        if self.selected_identity_ref:
            row["selected_identity_ref"] = _text(
                self.selected_identity_ref, "selected_identity_ref"
            )
        row["assessment_sha256"] = _digest(row)
        return row


def _set_relation(left: Iterable[str], right: Iterable[str]) -> tuple[MeetState, str]:
    left_set, right_set = set(left), set(right)
    if not left_set or not right_set:
        return MeetState.UNRESOLVED, "missing_coordinate"
    if left_set == right_set:
        return MeetState.COMPATIBLE, "equal"
    if left_set.intersection(right_set):
        return MeetState.COMPATIBLE_WITH_REFINEMENT, "overlap"
    return MeetState.NO_TYPED_MEET, "disjoint"


def assess_entity_resolution(
    *, subject_ref: str, local: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> ResolutionAssessment:
    type_state, type_relation = _set_relation(
        local.get("type_refs") or (), snapshot.get("type_refs") or ()
    )
    local_labels = tuple(
        str(value).casefold()
        for value in (*tuple(local.get("labels") or ()), *tuple(local.get("aliases") or ()))
    )
    external_labels = tuple(
        str(value).casefold()
        for value in (
            *tuple(snapshot.get("labels") or ()),
            *tuple(snapshot.get("aliases") or ()),
        )
    )
    form_state, form_relation = _set_relation(local_labels, external_labels)
    coordinates = (
        CompatibilityCoordinate(
            "type", type_state, type_relation, (str(snapshot.get("snapshot_ref")),)
        ),
        CompatibilityCoordinate(
            "form", form_state, form_relation, (str(snapshot.get("snapshot_ref")),)
        ),
    )
    if type_state == MeetState.NO_TYPED_MEET or form_state == MeetState.NO_TYPED_MEET:
        outcome, selected = ResolutionOutcome.NO_TYPED_MEET, None
    elif type_state == MeetState.COMPATIBLE and form_state in {
        MeetState.COMPATIBLE,
        MeetState.COMPATIBLE_WITH_REFINEMENT,
    }:
        outcome, selected = ResolutionOutcome.RESOLVED, snapshot.get("external_ref")
    else:
        outcome, selected = ResolutionOutcome.POSSIBLE_SAME, None
    return ResolutionAssessment(
        assessment_ref=f"assessment:{_digest([subject_ref, local, snapshot])[:16]}",
        subject_ref=subject_ref,
        left_ref=str(local.get("local_ref") or local.get("mention_ref") or subject_ref),
        right_ref=str(snapshot.get("snapshot_ref")),
        subject_kind="entity",
        coordinates=coordinates,
        outcome=outcome,
        selected_identity_ref=str(selected) if selected else None,
    )


def assess_event_resolution(
    *, subject_ref: str, local: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> ResolutionAssessment:
    type_state, type_relation = _set_relation(
        local.get("type_refs") or (), snapshot.get("type_refs") or ()
    )
    participant_state, participant_relation = _set_relation(
        (
            ref
            for refs in (local.get("participants") or {}).values()
            for ref in refs
        ),
        (
            ref
            for refs in (snapshot.get("participants") or {}).values()
            for ref in refs
        ),
    )
    local_time, external_time = local.get("temporal") or {}, snapshot.get("temporal") or {}
    if local_time and external_time:
        if set(local_time.values()).intersection(external_time.values()):
            temporal_state, temporal_relation = (
                MeetState.COMPATIBLE,
                "shared_temporal_anchor",
            )
        else:
            temporal_state, temporal_relation = (
                MeetState.COMPATIBLE_WITH_REFINEMENT,
                "distinct_temporal_roles",
            )
    else:
        temporal_state, temporal_relation = MeetState.UNRESOLVED, "missing_temporal_role"
    local_space, external_space = local.get("spatial") or {}, snapshot.get("spatial") or {}
    if local_space and external_space:
        if set(map(str, local_space.values())).intersection(
            map(str, external_space.values())
        ):
            spatial_state, spatial_relation = MeetState.COMPATIBLE, "shared_spatial_anchor"
        else:
            spatial_state, spatial_relation = (
                MeetState.COMPATIBLE_WITH_REFINEMENT,
                "spatial_refinement_required",
            )
    else:
        spatial_state, spatial_relation = MeetState.UNRESOLVED, "missing_spatial_coordinate"
    local_labels = tuple(
        str(value).casefold()
        for value in (*tuple(local.get("labels") or ()), *tuple(local.get("aliases") or ()))
    )
    external_labels = tuple(
        str(value).casefold()
        for value in (
            *tuple(snapshot.get("labels") or ()),
            *tuple(snapshot.get("aliases") or ()),
        )
    )
    form_state, form_relation = _set_relation(local_labels, external_labels)
    lineage_state = (
        MeetState.COMPATIBLE_WITH_REFINEMENT
        if snapshot.get("lineage_refs")
        else MeetState.UNRESOLVED
    )
    role = str(snapshot.get("evidence_role") or "")
    occurrence_state = (
        MeetState.COMPATIBLE
        if role == EvidenceRole.OCCURRENCE.value
        else MeetState.COMPATIBLE_WITH_REFINEMENT
    )
    occurrence_relation = (
        "same_occurrence_role"
        if role == EvidenceRole.OCCURRENCE.value
        else f"{role}_of_occurrence"
    )
    coordinates = (
        CompatibilityCoordinate("event_type", type_state, type_relation),
        CompatibilityCoordinate("temporal", temporal_state, temporal_relation),
        CompatibilityCoordinate("spatial", spatial_state, spatial_relation),
        CompatibilityCoordinate(
            "participants", participant_state, participant_relation
        ),
        CompatibilityCoordinate("form", form_state, form_relation),
        CompatibilityCoordinate(
            "lineage",
            lineage_state,
            "lineage_recorded" if snapshot.get("lineage_refs") else "lineage_missing",
        ),
        CompatibilityCoordinate(
            "observation_occurrence", occurrence_state, occurrence_relation
        ),
    )
    states = {MeetState(coordinate.state) for coordinate in coordinates}
    if MeetState.CONTRADICTION in states:
        outcome = ResolutionOutcome.CONTRADICTION
    elif MeetState.NO_TYPED_MEET in states:
        outcome = ResolutionOutcome.NO_TYPED_MEET
    elif states <= {MeetState.COMPATIBLE, MeetState.NOT_APPLICABLE} and role == "occurrence":
        outcome = ResolutionOutcome.RESOLVED
    elif type_state in {
        MeetState.COMPATIBLE,
        MeetState.COMPATIBLE_WITH_REFINEMENT,
    }:
        outcome = ResolutionOutcome.POSSIBLE_SAME
    else:
        outcome = ResolutionOutcome.NOT_EVALUATED
    selected = snapshot.get("external_ref") if outcome == ResolutionOutcome.RESOLVED else None
    return ResolutionAssessment(
        assessment_ref=f"assessment:{_digest([subject_ref, local, snapshot])[:16]}",
        subject_ref=subject_ref,
        left_ref=str(local.get("local_ref") or local.get("mention_ref") or subject_ref),
        right_ref=str(snapshot.get("snapshot_ref")),
        subject_kind="event_occurrence",
        coordinates=coordinates,
        outcome=outcome,
        selected_identity_ref=str(selected) if selected else None,
    )


@dataclass(frozen=True)
class PNFRefinement:
    refinement_ref: str
    partial_pnf_ref: str
    slot_ref: str
    prior_alternatives: tuple[str, ...]
    added_alternatives: tuple[str, ...] = ()
    retained_alternatives: tuple[str, ...] = ()
    rejected_alternatives: tuple[str, ...] = ()
    prior_residuals: tuple[str, ...] = ()
    remaining_residuals: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    assessment_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        prior = set(_refs(self.prior_alternatives))
        retained = set(_refs(self.retained_alternatives))
        rejected = set(_refs(self.rejected_alternatives))
        if not retained.issubset(prior) or not rejected.issubset(prior):
            raise ValueError("retained/rejected alternatives must exist in prior factor")
        if retained.intersection(rejected):
            raise ValueError("an alternative cannot be retained and rejected")
        row = {
            "schema_version": "sl.pnf_refinement.v0_1",
            "refinement_ref": _text(self.refinement_ref, "refinement_ref"),
            "partial_pnf_ref": _text(self.partial_pnf_ref, "partial_pnf_ref"),
            "slot_ref": _text(self.slot_ref, "slot_ref"),
            "prior_alternatives": sorted(prior),
            "added_alternatives": list(_refs(self.added_alternatives)),
            "retained_alternatives": sorted(retained),
            "rejected_alternatives": sorted(rejected),
            "prior_residuals": list(_refs(self.prior_residuals)),
            "remaining_residuals": list(_refs(self.remaining_residuals)),
            "evidence_refs": list(_refs(self.evidence_refs)),
            "assessment_refs": list(_refs(self.assessment_refs)),
            "authority": REFINEMENT_AUTHORITY,
            "unchanged_factor_witness": {
                "all_other_slots_unchanged": True,
                "changed_slot_ref": self.slot_ref,
            },
        }
        row["refinement_sha256"] = _digest(row)
        return row


def refine_partial_pnf_factor(
    *,
    partial_pnf: Mapping[str, Any],
    slot_ref: str,
    assessments: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], PNFRefinement]:
    slots = [dict(slot) for slot in partial_pnf.get("slots") or ()]
    index = next(
        (i for i, slot in enumerate(slots) if str(slot.get("slot_ref")) == slot_ref),
        None,
    )
    if index is None:
        raise ValueError("slot_ref does not exist in PartialPNF")
    target = slots[index]
    prior = tuple(target.get("alternatives") or target.get("candidate_refs") or ())
    prior_residuals = tuple(target.get("residual_refs") or ())
    added: set[str] = set()
    rejected: set[str] = set()
    retained = set(prior)
    evidence_refs: set[str] = set()
    assessment_refs: set[str] = set()
    remaining_residuals = set(prior_residuals)
    for assessment in assessments:
        assessment_refs.add(str(assessment.get("assessment_ref")))
        outcome = str(assessment.get("outcome"))
        identity_ref = assessment.get("selected_identity_ref")
        evidence_refs.add(str(assessment.get("right_ref")))
        if outcome == ResolutionOutcome.RESOLVED.value and identity_ref:
            added.add(str(identity_ref))
            remaining_residuals.discard("external_identity_unresolved")
        elif outcome in {
            ResolutionOutcome.NO_TYPED_MEET.value,
            ResolutionOutcome.CONTRADICTION.value,
        }:
            rejected.add(str(assessment.get("right_ref")))
    target["alternatives"] = sorted(retained.union(added) - rejected)
    target["residual_refs"] = sorted(remaining_residuals)
    slots[index] = target
    refined = dict(partial_pnf)
    refined["slots"] = slots
    refined["prior_pnf_ref"] = partial_pnf.get("partial_pnf_ref")
    refined["partial_pnf_ref"] = (
        f"{partial_pnf.get('partial_pnf_ref')}:refined:{_digest(target)[:12]}"
    )
    receipt = PNFRefinement(
        refinement_ref=f"refinement:{_digest([slot_ref, assessments])[:16]}",
        partial_pnf_ref=str(partial_pnf.get("partial_pnf_ref")),
        slot_ref=slot_ref,
        prior_alternatives=prior,
        added_alternatives=tuple(added),
        retained_alternatives=tuple(retained),
        rejected_alternatives=tuple(rejected.intersection(retained)),
        prior_residuals=prior_residuals,
        remaining_residuals=tuple(remaining_residuals),
        evidence_refs=tuple(evidence_refs),
        assessment_refs=tuple(assessment_refs),
    )
    return refined, receipt


@dataclass(frozen=True)
class ReadinessDecision:
    decision_ref: str
    subject_ref: str
    outcome: ReadinessOutcome | str
    reason_refs: tuple[str, ...]
    assessment_refs: tuple[str, ...] = ()
    refinement_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        reasons = _refs(self.reason_refs)
        if not reasons:
            raise ValueError("readiness decisions require reasons")
        return {
            "schema_version": "sl.resolution_readiness.v0_1",
            "decision_ref": _text(self.decision_ref, "decision_ref"),
            "subject_ref": _text(self.subject_ref, "subject_ref"),
            "outcome": ReadinessOutcome(self.outcome).value,
            "reason_refs": list(reasons),
            "assessment_refs": list(_refs(self.assessment_refs)),
            "refinement_refs": list(_refs(self.refinement_refs)),
            "authority": READINESS_AUTHORITY,
            "editing_authority": False,
        }


def assess_readiness(
    *,
    subject_ref: str,
    partial_pnf: Mapping[str, Any],
    assessments: Sequence[Mapping[str, Any]],
    refinement_refs: Sequence[str] = (),
) -> ReadinessDecision:
    residuals = {
        str(residual)
        for slot in partial_pnf.get("slots") or ()
        for residual in slot.get("residual_refs") or ()
    }
    outcomes = {str(row.get("outcome")) for row in assessments}
    reasons: list[str] = []
    if ResolutionOutcome.CONTRADICTION.value in outcomes:
        outcome = ReadinessOutcome.HOLD
        reasons.append("typed_contradiction")
    elif ResolutionOutcome.NO_TYPED_MEET.value in outcomes:
        outcome = ReadinessOutcome.ABSTAIN
        reasons.append("no_typed_meet")
    elif residuals:
        outcome = ReadinessOutcome.HOLD
        reasons.extend(f"residual:{value}" for value in sorted(residuals))
    elif not assessments:
        outcome = ReadinessOutcome.AUDIT
        reasons.append("assessment_missing")
    else:
        outcome = ReadinessOutcome.PROMOTE
        reasons.append("typed_factors_closed_for_review")
    return ReadinessDecision(
        decision_ref=f"readiness:{_digest([subject_ref, partial_pnf, assessments])[:16]}",
        subject_ref=subject_ref,
        outcome=outcome,
        reason_refs=tuple(reasons),
        assessment_refs=tuple(str(row.get("assessment_ref")) for row in assessments),
        refinement_refs=tuple(refinement_refs),
    )
