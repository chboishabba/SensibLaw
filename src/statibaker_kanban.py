from __future__ import annotations

from typing import Any, Iterable, Mapping


STATIBAKER_TASK_MEMORY_SCHEMA_VERSION = "sl.statibaker_task_memory.v0_1"
STATIBAKER_KANBAN_SCHEMA_VERSION = "sl.statibaker_kanban_projection.v0_1"
PROJECT_CONTEXT_PNF_INDEX_SCHEMA_VERSION = "sl.project_context_pnf_index.v0_1"
STATIBAKER_TASK_TIMELINE_PROBE_SCHEMA_VERSION = "sl.statibaker_task_timeline_probe.v0_1"
STATIBAKER_RUNSHEET_BRIDGE_SCHEMA_VERSION = "sl.statibaker_runsheet_bridge.v0_1"

PROMOTABLE_WRAPPERS = {
    "asserted_defect",
    "asserted_progress_update",
    "committed",
    "committed_in_progress",
    "commanded",
    "explicit_commitment",
    "explicit_request",
    "imperative",
    "in_progress",
    "requested",
    "resolved",
    "task_marker",
}

HELD_WRAPPERS = {
    "reported_only",
    "speculative",
    "quoted",
    "forwarded_context",
}

OPEN_LIFECYCLE_EFFECTS = {
    "append_evidence",
    "create_candidate",
    "mark_blocked",
    "mark_cancelled",
    "mark_done",
    "mark_in_progress",
    "mark_review",
    "promote_todo",
}

CLOSED_LIFECYCLE_EFFECTS = {"mark_cancelled", "no_task_transition"}
PROMOTABLE_TASK_RESIDUALS = {"exact", "partial"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _key(value: Any) -> str:
    return " ".join(_text(value).casefold().replace("_", " ").split())


def _id_key(value: Any) -> str:
    return _key(value).replace(" ", "_")


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _grounding_rows(grounding_catalog: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    raw_rows = grounding_catalog.get("groundings")
    if not isinstance(raw_rows, Mapping):
        raw_rows = grounding_catalog
    for phrase, raw in raw_rows.items():
        if str(phrase).startswith("_"):
            continue
        candidates = [_dict(item) for item in _list(raw) if isinstance(item, Mapping)]
        if candidates:
            rows[_key(phrase)] = candidates
    return rows


def _iter_segments(document: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    raw_segments = document.get("segments")
    if isinstance(raw_segments, list) and raw_segments:
        for index, raw_segment in enumerate(raw_segments):
            if isinstance(raw_segment, Mapping):
                segment = dict(raw_segment)
                segment.setdefault("segment_id", f"{document.get('doc_id', 'doc')}:s{index + 1}")
                segment.setdefault("text", document.get("raw_text") or document.get("text") or "")
                yield segment
        return
    yield {
        "segment_id": f"{document.get('doc_id', 'doc')}:s1",
        "text": document.get("raw_text") or document.get("text") or "",
        "atoms": document.get("atoms", []),
    }


def _role_text(atom: Mapping[str, Any], *names: str) -> str:
    roles = atom.get("roles")
    if not isinstance(roles, Mapping):
        return ""
    for name in names:
        value = roles.get(name)
        if isinstance(value, Mapping):
            text = _text(value.get("text") or value.get("value") or value.get("span") or value.get("label"))
        else:
            text = _text(value)
        if text:
            return text
    return ""


def _atom_wrapper(atom: Mapping[str, Any], segment: Mapping[str, Any], document: Mapping[str, Any]) -> str:
    return _text(
        atom.get("wrapper_state")
        or atom.get("wrapper")
        or segment.get("wrapper_state")
        or document.get("wrapper_state")
        or "reported_only"
    )


def _atom_kind(atom: Mapping[str, Any]) -> str:
    return _text(
        atom.get("task_kind")
        or atom.get("kind")
        or atom.get("predicate_family")
        or _task_frame(atom).get("predicate_family")
        or "task"
    ).casefold()


def _atom_action(atom: Mapping[str, Any]) -> str:
    frame = _task_frame(atom)
    return _text(
        atom.get("action")
        or frame.get("action_type")
        or _role_text(atom, "action")
        or frame.get("predicate_family")
        or "follow up"
    )


def _atom_object(atom: Mapping[str, Any]) -> str:
    frame = _task_frame(atom)
    return _text(
        atom.get("object")
        or atom.get("topic")
        or frame.get("object")
        or frame.get("affected_system")
        or _role_text(atom, "object", "topic", "target", "target_system", "feature", "artifact")
    )


def _task_frame(atom: Mapping[str, Any]) -> dict[str, Any]:
    raw_frame = atom.get("task_pnf") or atom.get("task_frame") or atom.get("pnf")
    return _dict(raw_frame)


def _qualifiers(atom: Mapping[str, Any]) -> dict[str, Any]:
    qualifiers = _dict(atom.get("qualifiers"))
    frame_qualifiers = _dict(_task_frame(atom).get("qualifiers"))
    return {**frame_qualifiers, **qualifiers}


def _lifecycle_effect(atom: Mapping[str, Any]) -> str:
    frame = _task_frame(atom)
    return _text(atom.get("lifecycle_effect") or frame.get("lifecycle_effect")).casefold()


def _predicate_family(atom: Mapping[str, Any]) -> str:
    frame = _task_frame(atom)
    return _text(atom.get("predicate_family") or frame.get("predicate_family")).casefold()


def _project_relevant(atom: Mapping[str, Any], groundings: list[Mapping[str, Any]]) -> bool:
    frame = _task_frame(atom)
    raw = atom.get("project_relevant")
    if raw is None:
        raw = frame.get("project_relevant")
    if raw is not None:
        return bool(raw)
    return bool(groundings)


def _closed_or_negated(atom: Mapping[str, Any]) -> bool:
    qualifiers = _qualifiers(atom)
    polarity = _text(atom.get("polarity") or qualifiers.get("polarity")).casefold()
    lifecycle_effect = _lifecycle_effect(atom)
    wrapper = _text(atom.get("wrapper_state") or atom.get("wrapper")).casefold()
    if polarity in {"negated", "negative"}:
        return True
    if wrapper in {"negated", "historical", "cancelled"}:
        return True
    return lifecycle_effect in CLOSED_LIFECYCLE_EFFECTS


def _purely_phatic(atom: Mapping[str, Any]) -> bool:
    frame = _task_frame(atom)
    raw = atom.get("purely_phatic")
    if raw is None:
        raw = frame.get("purely_phatic")
    return bool(raw)


def _has_lifecycle_transition(atom: Mapping[str, Any]) -> bool:
    return _lifecycle_effect(atom) in OPEN_LIFECYCLE_EFFECTS


def _context_atoms(project_context: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(project_context, Mapping):
        return []
    raw_atoms = project_context.get("context_pnfs") or project_context.get("atoms") or []
    atoms = [_dict(atom) for atom in _list(raw_atoms) if isinstance(atom, Mapping)]
    for section in (
        "project_ontology",
        "service_repo",
        "board_state",
        "owners",
        "environments",
        "incidents",
        "task_schemas",
        "policies",
    ):
        for atom in _list(project_context.get(section)):
            if isinstance(atom, Mapping):
                atom_row = dict(atom)
                atom_row.setdefault("context_family", section)
                atoms.append(atom_row)
    return atoms


def _context_roles(atom: Mapping[str, Any]) -> dict[str, str]:
    roles = _dict(atom.get("roles"))
    row: dict[str, str] = {}
    for key, value in roles.items():
        if isinstance(value, Mapping):
            text = _text(value.get("id") or value.get("value") or value.get("text") or value.get("label"))
        else:
            text = _text(value)
        if text:
            row[str(key)] = text
    for key in (
        "entity",
        "object",
        "feature",
        "service",
        "repo",
        "owner",
        "task_id",
        "status",
        "environment",
        "action",
        "lifecycle_effect",
    ):
        text = _text(atom.get(key))
        if text:
            row.setdefault(key, text)
    return row


def _context_entity_keys(atom: Mapping[str, Any]) -> set[str]:
    roles = _context_roles(atom)
    keys: set[str] = set()
    for key in ("entity", "object", "feature", "service", "repo", "environment", "task_object", "affected_system"):
        if roles.get(key):
            keys.add(_key(roles[key]))
    for alias in _list(atom.get("aliases")):
        if _text(alias):
            keys.add(_key(alias))
    label = _text(atom.get("label") or atom.get("name"))
    if label:
        keys.add(_key(label))
    return {key for key in keys if key}


def build_project_context_pnf_index(project_context: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize supplied project context into PNF-style lookup indexes."""

    atoms = _context_atoms(project_context)
    entity_index: dict[str, list[dict[str, Any]]] = {}
    structural_signature_index: dict[str, list[str]] = {}
    role_slot_index: dict[str, list[str]] = {}
    role_arg_index: dict[str, list[str]] = {}
    atom_ref_map: dict[str, dict[str, Any]] = {}
    task_schema_index: dict[str, list[dict[str, Any]]] = {}
    board_state_index: dict[str, list[dict[str, Any]]] = {}
    policy_index: dict[str, list[dict[str, Any]]] = {}
    owner_index: dict[str, list[dict[str, Any]]] = {}
    dependency_index: dict[str, list[dict[str, Any]]] = {}
    for position, atom in enumerate(atoms):
        row = dict(atom)
        row.setdefault("context_pnf_id", f"gamma:{position + 1}")
        atom_ref = _text(row.get("atom_id") or row.get("context_pnf_id"))
        atom_ref_map[atom_ref] = row
        family = _text(row.get("context_family") or row.get("predicate_family") or row.get("predicate")).casefold()
        roles = _context_roles(row)
        structural_signature = _text(row.get("structural_signature"))
        if structural_signature:
            structural_signature_index.setdefault(structural_signature, []).append(atom_ref)
        for role_slot, role_value in roles.items():
            role_slot_index.setdefault(role_slot, []).append(atom_ref)
            role_arg_index.setdefault(f"{role_slot}:{_key(role_value)}", []).append(atom_ref)
        for key in _context_entity_keys(row):
            entity_index.setdefault(key, []).append(row)
        effect = _text(row.get("lifecycle_effect") or roles.get("lifecycle_effect")).casefold()
        if family in {"task_schema", "task_schemas", "schema"} or effect:
            if effect:
                task_schema_index.setdefault(effect, []).append(row)
        task_id = _text(row.get("task_id") or roles.get("task_id"))
        if task_id or family in {"board_state", "task_status", "task_card"}:
            if task_id:
                board_state_index.setdefault(task_id, []).append(row)
            object_key = _key(row.get("object") or roles.get("object") or roles.get("task_object"))
            if object_key:
                board_state_index.setdefault(object_key, []).append(row)
        if family in {"policy", "policies", "policy_boundary", "requires_approval"}:
            action = _key(row.get("action") or roles.get("action"))
            environment = _key(row.get("environment") or roles.get("environment"))
            if action or environment:
                policy_index.setdefault(f"{action}:{environment}", []).append(row)
        owner = _key(row.get("owner") or roles.get("owner"))
        owned = _key(row.get("object") or roles.get("object") or roles.get("feature"))
        if owner or owned:
            owner_index.setdefault(owned or owner, []).append(row)
        blocker = _key(row.get("blocker") or roles.get("blocker"))
        blocked = _key(row.get("blocked_object") or roles.get("blocked_object") or roles.get("object"))
        if blocker or blocked:
            dependency_index.setdefault(blocked or blocker, []).append(row)
    return {
        "schema_version": PROJECT_CONTEXT_PNF_INDEX_SCHEMA_VERSION,
        "context_id": _text(project_context.get("context_id")) if isinstance(project_context, Mapping) else "",
        "source_refs": [_text(ref) for ref in _list(project_context.get("source_refs"))] if isinstance(project_context, Mapping) else [],
        "context_source": _text(project_context.get("context_source")) if isinstance(project_context, Mapping) else "",
        "context_atom_count": len(atoms),
        "context_pnfs": atoms,
        "predicate_pnf_index": atoms,
        "structural_signature_index": structural_signature_index,
        "role_slot_index": role_slot_index,
        "role_arg_index": role_arg_index,
        "atom_ref_map": atom_ref_map,
        "residual_index": [],
        "receipt_policy": "no_fabricated_PNFEmissionReceipt",
        "authority_policy": "review_only",
        "indexes": {
            "EntityIndexΓ": entity_index,
            "TaskSchemaIndexΓ": task_schema_index,
            "BoardStateIndexΓ": board_state_index,
            "PolicyIndexΓ": policy_index,
            "OwnerIndexΓ": owner_index,
            "DependencyIndexΓ": dependency_index,
        },
        "authority_boundary": {
            "context_is_pnf_indexed": True,
            "context_is_not_hand_blob": True,
            "structured_imports_must_normalize_to_pnf": True,
            "free_text_context_requires_pnf_extraction": True,
            "no_fabricated_PNFEmissionReceipt": True,
        },
    }


def _context_index(project_context: Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(project_context, Mapping) and project_context.get("schema_version") == PROJECT_CONTEXT_PNF_INDEX_SCHEMA_VERSION:
        return dict(project_context)
    return build_project_context_pnf_index(project_context)


def _context_meet(
    atom: Mapping[str, Any],
    groundings: list[Mapping[str, Any]],
    context_index: Mapping[str, Any],
) -> dict[str, Any]:
    indexes = _dict(context_index.get("indexes"))
    entity_index = _dict(indexes.get("EntityIndexΓ"))
    schema_index = _dict(indexes.get("TaskSchemaIndexΓ"))
    board_index = _dict(indexes.get("BoardStateIndexΓ"))
    policy_index = _dict(indexes.get("PolicyIndexΓ"))
    object_text = _atom_object(atom)
    object_key = _key(object_text)
    lifecycle_effect = _lifecycle_effect(atom)
    qualifiers = _qualifiers(atom)
    matched_entities: list[dict[str, Any]] = []
    for key in {object_key} | {_key(g.get("grounded_label") or g.get("grounded_node")) for g in groundings}:
        if key and key in entity_index:
            matched_entities.extend(_list(entity_index[key]))
    matched_schema = [_dict(row) for row in _list(schema_index.get(lifecycle_effect))]
    matched_board = [_dict(row) for row in _list(board_index.get(object_key))]
    action = _key(_atom_action(atom))
    environment = _key(qualifiers.get("environment"))
    matched_policy = [_dict(row) for row in _list(policy_index.get(f"{action}:{environment}"))]
    blockers: list[str] = []
    if matched_policy and lifecycle_effect in {"promote_todo", "mark_in_progress", "mark_done", "mark_review"}:
        blockers.append("policy_boundary")
    if not matched_entities and not groundings:
        blockers.append("no_context_entity_meet")
    if not matched_schema:
        blockers.append("no_task_schema_meet")
    if matched_policy:
        residual = "contradiction"
    elif not matched_entities and not matched_schema and not groundings:
        residual = "no_typed_meet"
    elif blockers:
        residual = "partial"
    elif matched_board:
        residual = "exact"
    else:
        residual = "partial"
    return {
        "residual": residual,
        "matched_entity_count": len(matched_entities),
        "matched_schema_count": len(matched_schema),
        "matched_board_count": len(matched_board),
        "matched_policy_count": len(matched_policy),
        "matched_entities": matched_entities,
        "matched_schemas": matched_schema,
        "matched_board_cards": matched_board,
        "matched_policies": matched_policy,
        "blockers": sorted(set(blockers)),
    }


def _task_like(
    atom: Mapping[str, Any],
    groundings: list[Mapping[str, Any]],
    wrapper: str,
    context_meet: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    """Evaluate taskhood as a structural PNF/context meet, not a keyword class."""

    reasons: list[str] = []
    if not _task_frame(atom) and not _lifecycle_effect(atom):
        reasons.append("missing_task_pnf")
    if not _has_lifecycle_transition(atom):
        reasons.append("missing_lifecycle_transition")
    if not _project_relevant(atom, groundings):
        reasons.append("not_project_relevant")
    if wrapper not in PROMOTABLE_WRAPPERS and wrapper not in HELD_WRAPPERS:
        reasons.append("non_promotable_wrapper")
    residual = _text(context_meet.get("residual")).casefold()
    if residual not in PROMOTABLE_TASK_RESIDUALS:
        reasons.append(f"context_residual:{residual or 'missing'}")
    if _closed_or_negated(atom):
        reasons.append("closed_or_negated")
    if _purely_phatic(atom):
        reasons.append("purely_phatic")
    return not reasons, sorted(set(reasons))


def _acceptance(atom: Mapping[str, Any]) -> str:
    return _text(
        atom.get("acceptance_criteria")
        or atom.get("acceptance")
        or _role_text(atom, "acceptance", "acceptance_criteria")
    )


def _owner(atom: Mapping[str, Any]) -> str:
    return _text(atom.get("owner") or _role_text(atom, "owner", "actor", "assignee"))


def _requester(atom: Mapping[str, Any], segment: Mapping[str, Any]) -> str:
    return _text(atom.get("requester") or _role_text(atom, "requester") or segment.get("speaker"))


def _candidate_groundings(object_text: str, grounding_catalog: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not object_text:
        return []
    catalog = _grounding_rows(grounding_catalog)
    object_key = _key(object_text)
    rows: list[dict[str, Any]] = []
    for phrase, candidates in catalog.items():
        if phrase == object_key or phrase in object_key or object_key in phrase:
            for candidate in candidates:
                rows.append(
                    {
                        "span": object_text,
                        "matched_phrase": phrase,
                        "grounded_node": _text(candidate.get("grounded_node") or candidate.get("qid") or candidate.get("id")),
                        "grounded_label": _text(
                            candidate.get("grounded_label") or candidate.get("label") or candidate.get("grounded_node")
                        ),
                        "grounding_residual": _text(candidate.get("grounding_residual") or "partial_grounding"),
                        "topic_closure": [_dict(topic) for topic in _list(candidate.get("topic_closure"))],
                    }
                )
    return rows


def _grounding_key(object_text: str, groundings: list[Mapping[str, Any]]) -> str:
    for grounding in groundings:
        grounded = _text(grounding.get("grounded_node"))
        if grounded:
            return grounded
    return _id_key(object_text or "unknown")


def _status_from_atom(atom: Mapping[str, Any], wrapper: str) -> str:
    lifecycle_effect = _lifecycle_effect(atom)
    if lifecycle_effect == "mark_done" or wrapper == "resolved":
        return "done"
    if lifecycle_effect == "mark_review":
        return "review"
    if lifecycle_effect == "mark_blocked":
        return "blocked"
    if lifecycle_effect == "mark_in_progress" or wrapper in {"in_progress", "committed_in_progress"}:
        return "in_progress"
    if lifecycle_effect == "create_candidate" or wrapper == "question":
        return "candidate"
    if wrapper in HELD_WRAPPERS:
        return "held"
    if lifecycle_effect == "promote_todo" or wrapper in PROMOTABLE_WRAPPERS:
        return "todo"
    return "candidate"


def _column_for_status(status: str) -> str:
    return {
        "candidate": "Inbox",
        "todo": "Todo",
        "in_progress": "Doing",
        "blocked": "Blocked",
        "review": "Review",
        "done": "Done",
        "held": "Held",
    }.get(status, "Inbox")


def _status_rank(status: str) -> int:
    return {
        "held": 0,
        "candidate": 1,
        "todo": 2,
        "in_progress": 3,
        "blocked": 4,
        "review": 5,
        "done": 6,
    }.get(status, 1)


def _merge_status(existing: str, new: str) -> str:
    if new == "blocked":
        return "blocked"
    if existing == "blocked" and new != "done":
        return "blocked"
    return new if _status_rank(new) >= _status_rank(existing) else existing


def _priority(atom: Mapping[str, Any], object_text: str) -> str:
    explicit = _text(atom.get("priority") or _role_text(atom, "priority")).casefold()
    if explicit:
        return explicit
    qualifiers = _qualifiers(atom)
    urgency = _text(qualifiers.get("urgency")).casefold()
    environment = _text(qualifiers.get("environment")).casefold()
    if urgency in {"critical", "high"} or environment in {"production", "prod"}:
        return "high"
    if urgency in {"low", "parking_lot"}:
        return urgency
    return "normal"


def _title(action: str, object_text: str) -> str:
    if object_text:
        return f"{action.strip().capitalize()} {object_text}".strip()
    return action.strip().capitalize() or "Review task candidate"


def _dependency_refs(atom: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    qualifiers = _qualifiers(atom)
    for value in _list(atom.get("dependencies")) + _list(qualifiers.get("depends_on")):
        text = _text(value)
        if text:
            refs.append(text)
    condition = _text(qualifiers.get("after") or _role_text(atom, "dependency", "after"))
    if condition:
        refs.append(condition)
    return refs


def build_task_memory_index(
    *,
    documents: Iterable[Mapping[str, Any]],
    grounding_catalog: Mapping[str, Any],
    ontology_snapshot_id: str,
    project_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build task candidates from supplied ITIR atoms and supplied groundings.

    This helper does not create tasks from raw free text. A segment contributes
    only when the runtime has already supplied a task-like atom/PNF surface.
    """

    context_index = _context_index(project_context)
    tasks_by_key: dict[str, dict[str, Any]] = {}
    ignored_segments: list[dict[str, Any]] = []
    evidence_log: list[dict[str, Any]] = []
    for document in documents:
        doc_id = _text(document.get("doc_id")) or f"doc_{len(tasks_by_key) + 1}"
        doc_provenance = _dict(document.get("provenance"))
        for segment in _iter_segments(document):
            atoms = [_dict(atom) for atom in _list(segment.get("atoms")) if isinstance(atom, Mapping)]
            if not atoms:
                ignored_segments.append(
                    {
                        "doc_id": doc_id,
                        "segment_id": _text(segment.get("segment_id")),
                        "reason": "no_supplied_atoms",
                    }
                )
                continue
            segment_had_task = False
            for atom in atoms:
                action = _atom_action(atom)
                object_text = _atom_object(atom)
                wrapper = _atom_wrapper(atom, segment, document)
                groundings = _candidate_groundings(object_text, grounding_catalog)
                context_meet = _context_meet(atom, groundings, context_index)
                is_task_like, non_task_reasons = _task_like(atom, groundings, wrapper, context_meet)
                if not is_task_like:
                    ignored_segments.append(
                        {
                            "doc_id": doc_id,
                            "segment_id": _text(segment.get("segment_id")),
                            "atom_id": _text(atom.get("atom_id")),
                            "reason": "not_structural_tasklike",
                            "tasklike_rejection_reasons": non_task_reasons,
                            "context_meet": context_meet,
                        }
                    )
                    continue
                segment_had_task = True
                grounding_key = _grounding_key(object_text, groundings)
                task_key = _text(atom.get("task_key")) or f"{_id_key(action)}:{grounding_key}"
                evidence_id = f"task_receipt:{len(evidence_log) + 1}"
                status = _status_from_atom(atom, wrapper)
                acceptance = _acceptance(atom)
                task = tasks_by_key.get(task_key)
                existing_acceptance = bool(task and _text(task.get("acceptance_criteria")))
                promotion = "candidate_only"
                hold_reasons: list[str] = []
                if wrapper in HELD_WRAPPERS:
                    hold_reasons.append(f"wrapper:{wrapper}")
                if not groundings:
                    hold_reasons.append("missing_grounding")
                if context_meet.get("residual") == "partial":
                    hold_reasons.extend([f"context:{reason}" for reason in _list(context_meet.get("blockers"))])
                if context_meet.get("residual") == "contradiction":
                    hold_reasons.append("context:policy_boundary")
                if not acceptance and not existing_acceptance and status in {"todo", "in_progress", "done"}:
                    hold_reasons.append("missing_acceptance_criteria")
                hold_reasons = sorted(set(hold_reasons))
                if status == "held" or hold_reasons:
                    promotion = "held_for_review"
                    if status not in {"blocked", "done"}:
                        status = "held"
                elif wrapper in PROMOTABLE_WRAPPERS or status in {"blocked", "done"}:
                    promotion = "promoted_candidate_card"
                evidence = {
                    "evidence_id": evidence_id,
                    "doc_id": doc_id,
                    "segment_id": _text(segment.get("segment_id")),
                    "atom_id": _text(atom.get("atom_id")) or f"{doc_id}:{len(evidence_log) + 1}",
                    "snippet": _text(segment.get("text")),
                    "predicate": _text(atom.get("predicate")),
                    "predicate_family": _predicate_family(atom),
                    "lifecycle_effect": _lifecycle_effect(atom),
                    "context_residual": context_meet.get("residual"),
                    "wrapper_state": wrapper,
                    "provenance": doc_provenance,
                }
                evidence_log.append(evidence)
                if task is None:
                    task = {
                        "task_id": f"task:{len(tasks_by_key) + 1}",
                        "task_key": task_key,
                        "title": _title(action, object_text),
                        "action": action,
                        "object": object_text,
                        "kind": _atom_kind(atom) or "task",
                        "predicate_family": _predicate_family(atom),
                        "lifecycle_effect": _lifecycle_effect(atom),
                        "context_meet": context_meet,
                        "owner": _owner(atom),
                        "requester": _requester(atom, segment),
                        "priority": _priority(atom, object_text),
                        "status": status,
                        "column": _column_for_status(status),
                        "promotion_status": promotion,
                        "hold_reasons": hold_reasons,
                        "acceptance_criteria": acceptance,
                        "dependencies": _dependency_refs(atom),
                        "blockers": [],
                        "grounding_refs": groundings,
                        "evidence_refs": [evidence_id],
                        "source_receipts": [evidence],
                    }
                    tasks_by_key[task_key] = task
                    continue
                task["status"] = _merge_status(_text(task.get("status")), status)
                task["column"] = _column_for_status(_text(task.get("status")))
                if promotion == "held_for_review":
                    task["promotion_status"] = "held_for_review"
                elif task.get("promotion_status") != "held_for_review":
                    task["promotion_status"] = promotion
                if _owner(atom):
                    task["owner"] = _owner(atom)
                if acceptance:
                    task["acceptance_criteria"] = acceptance
                task["context_meet"] = _merge_context_meet(_dict(task.get("context_meet")), context_meet)
                task["priority"] = max([_text(task.get("priority")), _priority(atom, object_text)], key=_priority_rank)
                task["dependencies"] = sorted(set(_list(task.get("dependencies")) + _dependency_refs(atom)))
                task["hold_reasons"] = sorted(set(_list(task.get("hold_reasons")) + hold_reasons))
                task["evidence_refs"].append(evidence_id)
                task["source_receipts"].append(evidence)
            if not segment_had_task:
                if not any(
                    row.get("doc_id") == doc_id
                    and row.get("segment_id") == _text(segment.get("segment_id"))
                    for row in ignored_segments
                ):
                    ignored_segments.append(
                        {
                            "doc_id": doc_id,
                            "segment_id": _text(segment.get("segment_id")),
                            "reason": "no_task_like_atoms",
                        }
                    )
    tasks = sorted(tasks_by_key.values(), key=lambda task: task["task_id"])
    return {
        "schema_version": STATIBAKER_TASK_MEMORY_SCHEMA_VERSION,
        "ontology_snapshot_id": ontology_snapshot_id,
        "task_count": len(tasks),
        "project_context": context_index,
        "tasks": tasks,
        "evidence_log": evidence_log,
        "ignored_segments": ignored_segments,
        "authority_boundary": {
            "candidate_task_receipts_only": True,
            "raw_keyword_tasking": False,
            "stati_baker_live_mutation": False,
            "completion_requires_receipt": True,
            "groundings_are_packet_supplied": True,
            "human_project_governance_required": True,
            "tasklike_is_structural": True,
            "project_context_is_pnf_indexed": True,
            "keyword_presence_neither_necessary_nor_sufficient": True,
            "local_json_is_canonical": True,
            "kanboard_apply_requires_opt_in": True,
            "kanboard_inbound_sync_enabled": False,
            "two_way_sync_without_conflict_policy": False,
            "secrets_logged": False,
        },
    }


def _merge_context_meet(existing: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
    residual_rank = {"exact": 0, "partial": 1, "no_typed_meet": 2, "contradiction": 3}
    existing_residual = _text(existing.get("residual") or "partial")
    new_residual = _text(new.get("residual") or "partial")
    residual = (
        new_residual
        if residual_rank.get(new_residual, 1) > residual_rank.get(existing_residual, 1)
        else existing_residual
    )
    merged = dict(existing)
    merged["residual"] = residual
    for key in ("matched_entities", "matched_schemas", "matched_board_cards", "matched_policies"):
        merged[key] = _list(existing.get(key)) + _list(new.get(key))
    merged["blockers"] = sorted(set(_list(existing.get("blockers")) + _list(new.get("blockers"))))
    for key in ("matched_entity_count", "matched_schema_count", "matched_board_count", "matched_policy_count"):
        merged[key] = int(existing.get(key, 0) or 0) + int(new.get(key, 0) or 0)
    return merged


def _priority_rank(priority: str) -> int:
    return {
        "parking_lot": 0,
        "low": 1,
        "normal": 2,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }.get(_text(priority).casefold(), 2)


def project_kanban(task_memory_index: Mapping[str, Any]) -> dict[str, Any]:
    columns = {name: [] for name in ("Inbox", "Todo", "Doing", "Blocked", "Review", "Done", "Held")}
    cards: list[dict[str, Any]] = []
    for raw_task in task_memory_index.get("tasks", []):
        if not isinstance(raw_task, Mapping):
            continue
        task = dict(raw_task)
        column = _column_for_status(_text(task.get("status")))
        card = {
            "card_id": task.get("task_id"),
            "task_key": task.get("task_key"),
            "title": task.get("title"),
            "column": column,
            "status": task.get("status"),
            "promotion_status": task.get("promotion_status"),
            "owner": task.get("owner"),
            "priority": task.get("priority"),
            "tags": _task_tags(task),
            "acceptance_criteria": task.get("acceptance_criteria"),
            "dependencies": task.get("dependencies", []),
            "hold_reasons": task.get("hold_reasons", []),
            "evidence_refs": task.get("evidence_refs", []),
            "latest_status_event": _list(task.get("source_receipts"))[-1] if _list(task.get("source_receipts")) else {},
            "source_receipts": task.get("source_receipts", []),
            "grounding_refs": task.get("grounding_refs", []),
        }
        columns[column].append(card)
        cards.append(card)
    return {
        "schema_version": STATIBAKER_KANBAN_SCHEMA_VERSION,
        "source_schema_version": task_memory_index.get("schema_version"),
        "ontology_snapshot_id": task_memory_index.get("ontology_snapshot_id"),
        "card_count": len(cards),
        "columns": columns,
        "cards": cards,
        "authority_boundary": {
            "kanban_projection_only": True,
            "stati_baker_live_mutation": False,
            "candidate_task_receipts_only": True,
            "human_project_governance_required": True,
            "local_json_is_canonical": True,
            "kanboard_apply_requires_opt_in": True,
            "kanboard_inbound_sync_enabled": False,
            "two_way_sync_without_conflict_policy": False,
            "secrets_logged": False,
        },
    }


def _task_tags(task: Mapping[str, Any]) -> list[str]:
    tags = {_text(task.get("kind")), _text(task.get("priority"))}
    for grounding in _list(task.get("grounding_refs")):
        if isinstance(grounding, Mapping):
            label = _text(grounding.get("grounded_label") or grounding.get("grounded_node"))
            if label:
                tags.add(label)
    return sorted(tag for tag in tags if tag)


def _timeline_event(raw_event: Mapping[str, Any], phase: str, position: int) -> dict[str, Any]:
    event = dict(raw_event)
    event.setdefault("event_id", f"{phase}:{position + 1}")
    event.setdefault("phase", phase)
    event.setdefault("event_type", _text(event.get("lifecycle_event_type") or event.get("type")))
    event.setdefault("residual", _text(event.get("residual") or "partial"))
    event.setdefault("expected_slot_matched", bool(event.get("expected_slot")))
    return event


def _timeline_graph_effects(events: list[Mapping[str, Any]]) -> list[str]:
    effects: set[str] = set()
    graph_effect_types = {
        "blocked",
        "closed",
        "completed",
        "implemented",
        "reframed",
        "spawned_successor",
        "split_into",
        "merged_with",
        "superseded",
        "held_missing_evidence",
    }
    for event in events:
        for value in _list(event.get("task_graph_effects")) + _list(event.get("task_graph_effect")):
            text = _text(value)
            if text:
                effects.add(text)
        event_type = _text(event.get("event_type"))
        if event_type in graph_effect_types:
            effects.add(event_type)
    return sorted(effects)


def _matched_expected_slots(events: list[Mapping[str, Any]]) -> list[str]:
    slots: set[str] = set()
    for event in events:
        if event.get("expected_slot_matched") is False:
            continue
        for value in _list(event.get("expected_slot")) + _list(event.get("matched_expected_slots")):
            text = _text(value)
            if text:
                slots.add(text)
    return sorted(slots)


def _timeline_residual(events: list[Mapping[str, Any]], missing_slots: list[str]) -> str:
    residuals = {_text(event.get("residual")) for event in events}
    if "contradiction" in residuals:
        return "contradiction"
    if missing_slots:
        return "incomplete"
    if residuals and residuals <= {"exact"}:
        return "exact"
    return "partial"


def _timeline_status(events: list[Mapping[str, Any]], fallback: str = "") -> str:
    for event in reversed(events):
        status = _text(event.get("status_after") or event.get("inferred_status"))
        if status:
            return status
    return fallback or "observed"


def build_task_timeline_probe(*, timeline_cases: Iterable[Mapping[str, Any]], source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build bidirectional task-timeline reconciliations from supplied receipts.

    The probe is a deterministic read model. It does not query a live archive and
    does not infer task events from raw text; each event must be supplied as a
    TaskPNF/lifecycle receipt by the caller or fixture.
    """

    timelines: list[dict[str, Any]] = []
    for case_index, raw_case in enumerate(timeline_cases):
        case = dict(raw_case)
        prior_events = [
            _timeline_event(_dict(event), "prior", index)
            for index, event in enumerate(_list(case.get("prior_event_receipts")))
            if isinstance(event, Mapping)
        ]
        seed_event = _timeline_event(_dict(case.get("seed_message_receipt")), "seed", 0)
        later_events = [
            _timeline_event(_dict(event), "later", index)
            for index, event in enumerate(_list(case.get("later_event_receipts")))
            if isinstance(event, Mapping)
        ]
        events = prior_events + [seed_event] + later_events
        expected_slots = sorted({_text(slot) for slot in _list(case.get("expected_event_slots")) if _text(slot)})
        matched_slots = _matched_expected_slots(events)
        explicit_missing = sorted({_text(slot) for slot in _list(case.get("missing_expected_slots")) if _text(slot)})
        missing_slots = explicit_missing or [slot for slot in expected_slots if slot not in set(matched_slots)]
        graph_effects = _timeline_graph_effects(events)
        final_status = _timeline_status(events, _text(case.get("final_task_status")))
        timeline = {
            "timeline_id": _text(case.get("timeline_id")) or f"archive_timeline:{case_index + 1}",
            "task_id": _text(case.get("task_id")) or f"task:{case_index + 1}",
            "task_title": _text(case.get("task_title")),
            "canonical_thread_id": _text(case.get("canonical_thread_id")),
            "thread_title": _text(case.get("thread_title")),
            "seed_role": _text(case.get("seed_role")),
            "seed_task_pnf": _dict(case.get("seed_task_pnf")),
            "prior_event_receipts": prior_events,
            "seed_message_receipt": seed_event,
            "later_event_receipts": later_events,
            "observed_lifecycle_events": events,
            "expected_event_slots": expected_slots,
            "matched_expected_slots": matched_slots,
            "missing_expected_slots": missing_slots,
            "successor_tasks": [_dict(task) for task in _list(case.get("successor_tasks")) if isinstance(task, Mapping)],
            "split_or_merge_events": [
                _dict(event) for event in _list(case.get("split_or_merge_events")) if isinstance(event, Mapping)
            ],
            "task_graph_effects": graph_effects,
            "final_task_status": final_status,
            "task_identity_residual": _text(case.get("task_identity_residual") or "partial"),
            "lifecycle_residual": _text(case.get("lifecycle_residual") or _timeline_residual(events, missing_slots)),
            "authority_policy": "receipt_backed_reconciliation_only",
        }
        timelines.append(timeline)
    return {
        "schema_version": STATIBAKER_TASK_TIMELINE_PROBE_SCHEMA_VERSION,
        "source": dict(source or {}),
        "timeline_count": len(timelines),
        "timelines": timelines,
        "summary": {
            "with_prior_evidence": sum(1 for row in timelines if row["prior_event_receipts"]),
            "with_later_evidence": sum(1 for row in timelines if row["later_event_receipts"]),
            "with_successors": sum(1 for row in timelines if row["successor_tasks"]),
            "with_missing_expected_slots": sum(1 for row in timelines if row["missing_expected_slots"]),
        },
        "authority_boundary": {
            "archive_thread_reconciliation_only": True,
            "raw_keyword_tasking": False,
            "live_archive_query": False,
            "task_timeline_is_bidirectional": True,
            "seed_is_not_assumed_origin": True,
            "prior_and_later_events_are_folded": True,
            "completion_requires_receipt": True,
            "human_project_governance_required": True,
        },
    }


def _runsheet_status_from_task(task: Mapping[str, Any]) -> str:
    status = _text(task.get("status")).casefold()
    promotion_status = _text(task.get("promotion_status")).casefold()
    hold_reasons = [row for row in _list(task.get("hold_reasons")) if _text(row)]
    evidence_refs = [row for row in _list(task.get("evidence_refs")) if _text(row)]
    if not evidence_refs:
        return "skipped"
    if status == "done":
        return "done"
    if status in {"blocked", "held"}:
        return "blocked"
    if status in {"in_progress", "review"}:
        return "in_progress"
    if promotion_status == "held_for_review" or hold_reasons:
        return "blocked"
    if status in {"todo", "candidate"}:
        return "todo"
    return "todo"


def _runsheet_status_from_timeline(timeline: Mapping[str, Any]) -> str:
    lifecycle_residual = _text(timeline.get("lifecycle_residual")).casefold()
    task_graph_effects = {_text(effect).casefold() for effect in _list(timeline.get("task_graph_effects")) if _text(effect)}
    final_status = _text(timeline.get("final_task_status")).casefold()
    if lifecycle_residual in {"contradiction", "incomplete"}:
        return "blocked"
    if "blocked" in task_graph_effects or "blocked" in final_status:
        return "blocked"
    if task_graph_effects & {"completed", "implemented", "closed"} or any(
        token in final_status for token in ("done", "completed", "closed", "accepted")
    ):
        return "done"
    later_events = _list(timeline.get("later_event_receipts"))
    if later_events:
        return "in_progress"
    return "todo"


def _runsheet_status_rank(status: str) -> int:
    return {
        "skipped": 0,
        "todo": 1,
        "in_progress": 2,
        "done": 3,
        "blocked": 4,
    }.get(_text(status).casefold(), 1)


def _merge_runsheet_status(existing: str, new: str) -> str:
    return new if _runsheet_status_rank(new) >= _runsheet_status_rank(existing) else existing


def build_runsheet_bridge(
    *,
    task_memory_index: Mapping[str, Any],
    kanban_projection: Mapping[str, Any] | None = None,
    timeline_probe: Mapping[str, Any] | None = None,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bridge task memory + Kanban + timeline receipts into runsheet rows.

    This helper is still read-only. It normalizes existing receipt-backed
    artifacts into orchestrator-facing task/subtask statuses.
    """

    board = dict(kanban_projection) if isinstance(kanban_projection, Mapping) else project_kanban(task_memory_index)
    source_row = _dict(source)
    runner_id = _text(source_row.get("orchestrator_id") or source_row.get("runner_id"))
    lane = _text(source_row.get("lane"))
    timelines = (
        [_dict(row) for row in _list(timeline_probe.get("timelines")) if isinstance(row, Mapping)]
        if isinstance(timeline_probe, Mapping)
        else []
    )
    timeline_by_id = {_text(row.get("task_id")): row for row in timelines if _text(row.get("task_id"))}
    timeline_by_title = {_key(row.get("task_title")): row for row in timelines if _text(row.get("task_title"))}
    cards_by_id: dict[str, dict[str, Any]] = {}
    for card in _list(board.get("cards")):
        if isinstance(card, Mapping):
            card_id = _text(card.get("card_id"))
            if card_id:
                cards_by_id[card_id] = dict(card)

    items: list[dict[str, Any]] = []
    matched_timeline_ids: set[str] = set()
    for raw_task in _list(task_memory_index.get("tasks")):
        if not isinstance(raw_task, Mapping):
            continue
        task = dict(raw_task)
        task_id = _text(task.get("task_id")) or _text(task.get("task_key")) or f"task:{len(items) + 1}"
        card = cards_by_id.get(task_id, {})
        timeline = timeline_by_id.get(task_id) or timeline_by_title.get(_key(task.get("title")))
        if timeline:
            matched_timeline_ids.add(_text(timeline.get("timeline_id")))
        base_status = _runsheet_status_from_task(task)
        timeline_status = _runsheet_status_from_timeline(timeline) if timeline else ""
        merged_status = _merge_runsheet_status(base_status, timeline_status) if timeline_status else base_status
        context_meet = _dict(task.get("context_meet"))
        context_residual = _text(context_meet.get("residual") or "partial")
        timeline_lifecycle_residual = _text(timeline.get("lifecycle_residual")) if timeline else ""
        timeline_task_identity_residual = _text(timeline.get("task_identity_residual")) if timeline else ""
        lifecycle_residual = timeline_lifecycle_residual or context_residual
        task_identity_residual = timeline_task_identity_residual or context_residual
        canonical_thread_id = _text(timeline.get("canonical_thread_id")) if timeline else ""
        seed_receipt = _dict(timeline.get("seed_message_receipt")) if timeline else {}
        source_message_id = _text(seed_receipt.get("source_message_id"))
        if not source_message_id and timeline:
            for event in _list(timeline.get("observed_lifecycle_events")):
                event_row = _dict(event)
                source_message_id = _text(event_row.get("source_message_id"))
                if source_message_id:
                    break
        evidence_refs = [_text(row) for row in _list(task.get("evidence_refs")) if _text(row)]
        hold_reasons = [_text(row) for row in _list(task.get("hold_reasons")) if _text(row)]
        provenance = {
            "task_memory_task_id": task_id,
            "source_task_status": _text(task.get("status")),
            "kanban_column": _text(card.get("column") or task.get("column")),
            "promotion_status": _text(task.get("promotion_status")),
            "context_residual": context_residual,
            "timeline_id": _text(timeline.get("timeline_id")) if timeline else "",
            "timeline_lifecycle_residual": timeline_lifecycle_residual,
            "lifecycle_residual": lifecycle_residual,
            "task_identity_residual": task_identity_residual,
            "evidence_refs": evidence_refs,
        }
        item = {
            "id": task_id,
            "stable_id": task_id,
            "title": _text(task.get("title")) or _text(task.get("object")) or task_id,
            "status": merged_status,
            "source": "statibaker_task_memory",
            "runner_id": runner_id,
            "lane": lane,
            "source_task_status": _text(task.get("status")),
            "kanban_column": _text(card.get("column") or task.get("column")),
            "priority": _text(task.get("priority") or card.get("priority") or "normal"),
            "promotion_status": _text(task.get("promotion_status")),
            "context_residual": context_residual,
            "hold_reasons": hold_reasons,
            "evidence_refs": evidence_refs,
            "timeline_ref": _text(timeline.get("timeline_id")) if timeline else "",
            "timeline_lifecycle_residual": timeline_lifecycle_residual,
            "canonical_thread_id": canonical_thread_id,
            "source_message_id": source_message_id,
            "lifecycle_residual": lifecycle_residual,
            "task_identity_residual": task_identity_residual,
            "acceptance_criteria": _text(task.get("acceptance_criteria")),
            "provenance": provenance,
        }
        items.append(item)

    unmatched_timelines: list[dict[str, Any]] = []
    for timeline in timelines:
        timeline_id = _text(timeline.get("timeline_id"))
        if timeline_id and timeline_id in matched_timeline_ids:
            continue
        unmatched_timelines.append(
            {
                "timeline_id": timeline_id,
                "task_id": _text(timeline.get("task_id")),
                "task_title": _text(timeline.get("task_title")),
                "lifecycle_residual": _text(timeline.get("lifecycle_residual")),
                "final_task_status": _text(timeline.get("final_task_status")),
            }
        )

    status_counts = {name: 0 for name in ("todo", "in_progress", "blocked", "done", "skipped")}
    for row in items:
        name = _text(row.get("status"))
        if name in status_counts:
            status_counts[name] += 1
    total = len([item for item in items if _text(item.get("status")) != "skipped"])
    completed = len([item for item in items if _text(item.get("status")) == "done"])
    return {
        "schema_version": STATIBAKER_RUNSHEET_BRIDGE_SCHEMA_VERSION,
        "source": dict(source_row),
        "orchestrator_id": runner_id,
        "runner_id": runner_id,
        "lane": lane,
        "task_memory_schema_version": _text(task_memory_index.get("schema_version")),
        "kanban_schema_version": _text(board.get("schema_version")),
        "timeline_schema_version": _text(timeline_probe.get("schema_version")) if isinstance(timeline_probe, Mapping) else "",
        "items": items,
        "runsheet": {"items": items},
        "status_counts": status_counts,
        "heartbeat": {
            "completed_items": completed,
            "total_items": total,
        },
        "boundary_gaps": {
            "missing_kanban_projection": not isinstance(kanban_projection, Mapping),
            "missing_timeline_probe": not isinstance(timeline_probe, Mapping),
            "unmatched_timeline_count": len(unmatched_timelines),
            "unmatched_timeline_receipts": unmatched_timelines,
        },
        "authority_boundary": {
            "receipt_backed_bridge_only": True,
            "no_keyword_only_promotion": True,
            "no_live_kanboard_mutation": True,
            "missing_adapter_boundary_is_explicit": True,
        },
    }


__all__ = [
    "PROJECT_CONTEXT_PNF_INDEX_SCHEMA_VERSION",
    "STATIBAKER_KANBAN_SCHEMA_VERSION",
    "STATIBAKER_RUNSHEET_BRIDGE_SCHEMA_VERSION",
    "STATIBAKER_TASK_TIMELINE_PROBE_SCHEMA_VERSION",
    "STATIBAKER_TASK_MEMORY_SCHEMA_VERSION",
    "build_project_context_pnf_index",
    "build_runsheet_bridge",
    "build_task_memory_index",
    "build_task_timeline_probe",
    "project_kanban",
]
