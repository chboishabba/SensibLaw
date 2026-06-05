"""Turn compiler for the Conversation VM.

The compiler is deliberately structural. It preserves source/excerpt/statement
receipts, projects statement carriers through optional reducer adapters when
available, and otherwise emits abstention-visible local carriers.
"""

from __future__ import annotations

import importlib
import time
from typing import Any, Callable

from .schema import TURN_DELTA_SCHEMA, receipt, stable_id

try:
    from src.text.sentences import segment_sentences
except ModuleNotFoundError:  # pragma: no cover - installed package import path
    try:
        from text.sentences import segment_sentences
    except ModuleNotFoundError:  # pragma: no cover - minimal external use
        segment_sentences = None  # type: ignore[assignment]


_PROJECTOR_UNSET = object()
_PROJECTOR_CACHE: Callable[[str], list[dict[str, Any]]] | None | object = _PROJECTOR_UNSET


def compile_turn(turn: dict[str, Any] | str, metrics_callback: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    payload = _coerce_turn(turn)
    text = str(payload.get("text", ""))
    turn_id = str(payload.get("turn_id") or stable_id("turn", {"text": text, "meta": payload.get("metadata", {})}))

    source = _source_record(turn_id, text, payload)
    with _MetricSpan(metrics_callback, "segmentation", turn_id=turn_id, input_chars=len(text)):
        excerpts = _excerpt_records(source, text)
    statements = [_statement_record(source, excerpt) for excerpt in excerpts]
    observations = _observation_records(source, excerpts, statements, payload)
    atoms, pnfs, projection_abstentions = _predicate_records(statements, payload, metrics_callback, turn_id)
    with _MetricSpan(metrics_callback, "residual_pair_construction", turn_id=turn_id, atom_count=len(atoms)):
        residuals = _residual_records(atoms)
    with _MetricSpan(metrics_callback, "pnf_receipt_construction", turn_id=turn_id, atom_count=len(atoms), residual_count=len(residuals)):
        pnf_emission_receipts = _pnf_emission_receipts(atoms, pnfs)
        pnf_residual_receipts = _pnf_residual_receipts(residuals, pnf_emission_receipts)
    with _MetricSpan(metrics_callback, "gate_construction", turn_id=turn_id, atom_count=len(atoms)):
        gates = _promotion_gates(source, excerpts, statements, observations, atoms)

    abstentions = list(projection_abstentions)
    if not atoms:
        abstentions.append(
            {
                "id": stable_id("abstain", {"turn_id": turn_id, "reason": "no-predicate-atoms"}),
                "status": "abstained",
                "reason": "no-predicate-atoms",
                "receipt_ids": [source["receipt_id"]],
            }
        )

    delta_body = {
        "schema": TURN_DELTA_SCHEMA,
        "id": stable_id("delta", {"turn_id": turn_id, "text": text, "metadata": payload.get("metadata", {})}),
        "turn_id": turn_id,
        "sources": [source],
        "excerpts": excerpts,
        "statements": statements,
        "observations": observations,
        "predicate_atoms": atoms,
        "predicate_pnfs": pnfs,
        "pnf_emission_receipts": pnf_emission_receipts,
        "pnf_residual_receipts": pnf_residual_receipts,
        "residual_comparisons": residuals,
        "promotion_gates": gates,
        "proof_obligations": _proof_obligations(gates),
        "blockers": [gate for gate in gates if gate["status"] == "blocked"],
        "abstentions": abstentions,
        "contested_items": [],
        "compact_payload_metadata": {
            "source_count": 1,
            "excerpt_count": len(excerpts),
            "statement_count": len(statements),
            "atom_count": len(atoms),
            "deterministic": True,
        },
    }
    return delta_body


def _coerce_turn(turn: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(turn, str):
        return {"text": turn, "metadata": {}}
    text = turn.get("text")
    if text is None:
        parts = []
        for key in ("prompt", "response", "content", "message"):
            if turn.get(key):
                parts.append(str(turn[key]))
        text = "\n".join(parts)
    return {**turn, "text": str(text or ""), "metadata": dict(turn.get("metadata", {}))}


def _source_record(turn_id: str, text: str, payload: dict[str, Any]) -> dict[str, Any]:
    source_id = stable_id("src", {"turn_id": turn_id, "text": text})
    source = {
        "id": source_id,
        "turn_id": turn_id,
        "source_type": str(payload.get("source_type", "archive_turn")),
        "text": text,
        "metadata": payload.get("metadata", {}),
    }
    source["receipt_id"] = receipt("source-preserved", source_id, [], {"sha256_source": stable_id("txt", text)})["id"]
    return source


def _excerpt_records(source: dict[str, Any], text: str) -> list[dict[str, Any]]:
    excerpts = []
    for index, span in enumerate(_sentence_spans(text)):
        start, end = span
        excerpt_text = text[start:end].strip()
        if not excerpt_text:
            continue
        excerpt_id = stable_id("ex", {"source_id": source["id"], "start": start, "end": end, "text": excerpt_text})
        excerpt_receipt = receipt(
            "excerpt-bounded",
            excerpt_id,
            [source["receipt_id"]],
            {"source_id": source["id"], "start": start, "end": end},
        )
        excerpts.append(
            {
                "id": excerpt_id,
                "source_id": source["id"],
                "index": index,
                "span": {"start": start, "end": end},
                "text": excerpt_text,
                "receipt_id": excerpt_receipt["id"],
            }
        )
    return excerpts


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    if segment_sentences is not None:
        sentences = segment_sentences(text)
        spans: list[tuple[int, int]] = []
        cursor = 0
        for sentence in sentences:
            sentence_text = str(sentence.text or "").strip()
            if not sentence_text:
                continue
            found = text.find(sentence_text, cursor)
            if found >= 0:
                start = found
                end = found + len(sentence_text)
            else:
                start = int(sentence.start_char)
                end = int(sentence.end_char)
            spans.append((start, end))
            cursor = end
        return spans

    spans: list[tuple[int, int]] = []
    start = 0
    for index, char in enumerate(text):
        if char in ".!?\n":
            end = index + 1
            if text[start:end].strip():
                spans.append((start, end))
            start = end
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def _statement_record(source: dict[str, Any], excerpt: dict[str, Any]) -> dict[str, Any]:
    statement_id = stable_id("stmt", {"excerpt_id": excerpt["id"], "text": excerpt["text"]})
    statement_receipt = receipt(
        "statement-from-excerpt",
        statement_id,
        [source["receipt_id"], excerpt["receipt_id"]],
        {"excerpt_id": excerpt["id"]},
    )
    return {
        "id": statement_id,
        "source_id": source["id"],
        "excerpt_id": excerpt["id"],
        "text": excerpt["text"],
        "status": "candidate",
        "receipt_ids": [statement_receipt["id"], excerpt["receipt_id"], source["receipt_id"]],
    }


def _observation_records(
    source: dict[str, Any],
    excerpts: list[dict[str, Any]],
    statements: list[dict[str, Any]],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    observations = []
    fact_candidates = payload.get("fact_candidates") or payload.get("facts") or []
    for index, statement in enumerate(statements):
        status = "supported" if index < len(fact_candidates) else "candidate"
        obs_id = stable_id("obs", {"statement_id": statement["id"], "status": status})
        obs_receipt = receipt(
            "observation-receipted",
            obs_id,
            statement["receipt_ids"],
            {"statement_id": statement["id"], "fact_intake": index < len(fact_candidates)},
        )
        observations.append(
            {
                "id": obs_id,
                "source_id": source["id"],
                "excerpt_id": excerpts[index]["id"],
                "statement_id": statement["id"],
                "status": status,
                "claim": fact_candidates[index] if index < len(fact_candidates) else None,
                "receipt_ids": [obs_receipt["id"], *statement["receipt_ids"]],
            }
        )
    return observations


def _predicate_records(
    statements: list[dict[str, Any]],
    payload: dict[str, Any],
    metrics_callback: Callable[[dict[str, Any]], None] | None = None,
    turn_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    supplied_atoms = payload.get("predicate_atoms")
    if supplied_atoms:
        with _MetricSpan(metrics_callback, "projection", turn_id=turn_id, statement_count=len(statements), supplied_atom_count=len(supplied_atoms)):
            atoms = [_normalize_supplied_atom(atom) for atom in supplied_atoms]
    else:
        with _MetricSpan(metrics_callback, "projector_probe", turn_id=turn_id, statement_count=len(statements)):
            projector = _optional_projector()
        atoms = []
        with _MetricSpan(metrics_callback, "projection", turn_id=turn_id, statement_count=len(statements)):
            for statement in statements:
                projected = _project_with_fallback(projector, statement)
                for atom in projected:
                    atom_id = stable_id("atom", {"statement_id": statement["id"], "atom": atom})
                    atom_receipt = receipt("predicate-atom-projected", atom_id, statement["receipt_ids"], {"statement_id": statement["id"]})
                    atoms.append(
                        {
                            "id": atom_id,
                            "statement_id": statement["id"],
                            "predicate": atom["predicate"],
                            "arguments": atom["arguments"],
                            "polarity": atom.get("polarity", "positive"),
                            "status": "candidate",
                            "projection_method": atom.get("projection_method", "conversation_vm_structural_parser"),
                            "receipt_ids": [atom_receipt["id"], *statement["receipt_ids"]],
                            **_optional_atom_fields(atom),
                        }
                    )

    pnfs = []
    abstentions = []
    with _MetricSpan(metrics_callback, "pnf_construction", turn_id=turn_id, atom_count=len(atoms)):
        for atom in atoms:
            pnf_id = stable_id("pnf", {"atom_id": atom["id"], "predicate": atom["predicate"], "arguments": atom["arguments"]})
            tokens = _normal_tokens(" ".join(str(arg) for arg in atom["arguments"]))
            if tokens:
                pnfs.append(
                    {
                        "id": pnf_id,
                        "atom_id": atom["id"],
                        "normal_form": {
                            "predicate": atom["predicate"],
                            "polarity": atom.get("polarity", "positive"),
                            "arguments": tokens,
                            **_normal_form_optional_fields(atom),
                        },
                        "status": "candidate",
                        "receipt_ids": atom.get("receipt_ids", []),
                    }
                )
            else:
                abstentions.append(
                    {
                        "id": stable_id("abstain", {"atom_id": atom["id"], "reason": "no-typed-meet"}),
                        "status": "abstained",
                        "reason": "no-typed-meet",
                        "atom_id": atom["id"],
                        "receipt_ids": atom.get("receipt_ids", []),
                    }
                )
    return atoms, pnfs, abstentions


def _project_with_fallback(projector: Callable[[str], list[dict[str, Any]]] | None, statement: dict[str, Any]) -> list[dict[str, Any]]:
    if projector is None:
        return [_local_project_statement(statement)]
    try:
        projected = projector(statement["text"])
    except Exception:
        return [_local_project_statement(statement)]
    return projected or [_local_project_statement(statement)]


def _optional_projector() -> Callable[[str], list[dict[str, Any]]] | None:
    global _PROJECTOR_CACHE
    if _PROJECTOR_CACHE is not _PROJECTOR_UNSET:
        return _PROJECTOR_CACHE  # type: ignore[return-value]
    for module_name, function_name in (
        ("src.sensiblaw.interfaces.shared_reducer", "collect_canonical_predicate_atoms"),
        ("sensiblaw.interfaces.shared_reducer", "collect_canonical_predicate_atoms"),
        ("src.sensiblaw.interfaces.shared_reducer", "collect_canonical_relational_bundle"),
        ("sensiblaw.interfaces.shared_reducer", "collect_canonical_relational_bundle"),
        ("shared_reducer", "project_predicate_atoms"),
        ("shared_reducer", "extract_predicate_atoms"),
    ):
        try:
            module = importlib.import_module(module_name)
            fn = getattr(module, function_name)
        except (ImportError, AttributeError):
            continue

        def projector(text: str, fn: Callable[..., Any] = fn) -> list[dict[str, Any]]:
            result = fn(text)
            if isinstance(result, dict) and "relations" in result:
                return _relations_to_atoms(result)
            if isinstance(result, dict):
                result = result.get("predicate_atoms", [])
            projected = []
            for item in result:
                if hasattr(item, "to_dict"):
                    projected.append(_projected_item_to_dict(dict(item.to_dict())))
                else:
                    projected.append(_projected_item_to_dict(dict(item)))
            return projected

        _PROJECTOR_CACHE = projector
        return projector
    _PROJECTOR_CACHE = None
    return None


def reset_projector_cache_for_tests() -> None:
    global _PROJECTOR_CACHE
    _PROJECTOR_CACHE = _PROJECTOR_UNSET


def _projected_item_to_dict(item: dict[str, Any]) -> dict[str, Any]:
    qualifiers = item.get("qualifiers") if isinstance(item.get("qualifiers"), dict) else {}
    item.setdefault("polarity", qualifiers.get("polarity", "positive"))
    if "arguments" not in item:
        item["arguments"] = _arguments_from_roles(item.get("roles"))
    item.setdefault("projection_method", "sensiblaw.shared_reducer.collect_canonical_predicate_atoms")
    return item


def _arguments_from_roles(roles: Any) -> list[str]:
    if not isinstance(roles, dict):
        return []
    ordered_names = ("subject", "actor", "object", "argument", "recipient", "target")
    arguments: list[str] = []
    seen: set[str] = set()
    for role_name in ordered_names:
        value = _role_value(roles.get(role_name))
        if value and value not in seen:
            arguments.append(value)
            seen.add(value)
    for role_name in sorted(str(key) for key in roles):
        if role_name in {"action", *ordered_names}:
            continue
        value = _role_value(roles.get(role_name))
        if value and value not in seen:
            arguments.append(value)
            seen.add(value)
    return arguments


def _role_value(role: Any) -> str | None:
    if isinstance(role, dict):
        value = role.get("value")
        if value is not None:
            return str(value)
    if role is not None:
        return str(role)
    return None


def _optional_atom_fields(atom: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in (
        "roles",
        "qualifiers",
        "structural_signature",
        "domain",
        "modifiers",
        "wrapper",
        "provenance",
        "atom_id",
        "support_fibres",
        "latent_grounding",
        "semantic_comparison_mode",
    ):
        value = atom.get(key)
        if value not in (None, {}, [], ()):
            fields[key] = value
    return fields


def _normal_form_optional_fields(atom: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if isinstance(atom.get("roles"), dict):
        fields["roles"] = atom["roles"]
    if isinstance(atom.get("qualifiers"), dict):
        fields["qualifiers"] = atom["qualifiers"]
    if atom.get("structural_signature"):
        fields["structural_signature"] = atom["structural_signature"]
    if atom.get("domain"):
        fields["domain"] = atom["domain"]
    if atom.get("support_fibres"):
        fields["support_fibres"] = atom["support_fibres"]
    if atom.get("latent_grounding"):
        fields["latent_grounding"] = atom["latent_grounding"]
    if atom.get("semantic_comparison_mode") and atom.get("semantic_comparison_mode") != "exact":
        fields["semantic_comparison_mode"] = atom["semantic_comparison_mode"]
    return fields


class _MetricSpan:
    def __init__(self, callback: Callable[[dict[str, Any]], None] | None, stage: str, **fields: Any) -> None:
        self.callback = callback
        self.stage = stage
        self.fields = fields
        self.started = 0.0

    def __enter__(self) -> "_MetricSpan":
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.callback is None:
            return
        row = {
            "component": "conversation_vm.compiler",
            "stage": self.stage,
            "elapsed_ms": round((time.perf_counter() - self.started) * 1000, 6),
            **self.fields,
        }
        try:
            self.callback(row)
        except Exception:
            pass


def _relations_to_atoms(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    atoms_by_id = {atom["id"]: atom for atom in bundle.get("atoms", []) if isinstance(atom, dict)}
    projected: list[dict[str, Any]] = []
    for relation in bundle.get("relations", []):
        relation_type = str(relation.get("type") or "relation")
        if relation_type not in {"predicate", "temporal", "composition"}:
            continue
        roles = {}
        for role in relation.get("roles", []):
            atom_id = role.get("atom")
            atom = atoms_by_id.get(atom_id, {})
            role_name = str(role.get("role") or atom_id or "role")
            roles[role_name] = {
                "value": str(atom.get("text") or role.get("value") or atom_id or ""),
                "provenance": [str(atom_id)] if atom_id else [],
            }
        if roles:
            predicate = relation_type
            arguments = [value["value"] for value in roles.values()]
            if relation_type == "predicate" and roles.get("head", {}).get("value"):
                predicate = str(roles["head"]["value"]).lower()
                arguments = [
                    value["value"]
                    for role_name, value in roles.items()
                    if role_name != "head" and str(value.get("value") or "")
                ]
            projected.append(
                {
                    "predicate": predicate,
                    "roles": roles,
                    "arguments": arguments,
                    "polarity": "positive",
                    "projection_method": "sensiblaw.shared_reducer.collect_canonical_relational_bundle",
                }
            )
    return projected


def _local_project_statement(statement: dict[str, Any]) -> dict[str, Any]:
    text = statement["text"].strip()
    tokens = _normal_tokens(text)
    polarity = "negative" if tokens[:1] in (["no"], ["not"], ["never"]) else "positive"
    return {
        "predicate": "utterance.statement",
        "arguments": [stable_id("span", {"text": text}), *tokens[:12]],
        "polarity": polarity,
        "projection_method": "conversation_vm_structural_parser",
    }


def _normal_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in text.lower():
        if char.isalnum() or char in "_-":
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _normalize_supplied_atom(atom: dict[str, Any]) -> dict[str, Any]:
    body = {
        "predicate": atom["predicate"],
        "arguments": list(atom.get("arguments", [])),
        "polarity": atom.get("polarity", "positive"),
    }
    atom_id = str(atom.get("id") or stable_id("atom", body))
    return {
        "id": atom_id,
        "statement_id": atom.get("statement_id"),
        "predicate": body["predicate"],
        "arguments": body["arguments"],
        "polarity": body["polarity"],
        "status": atom.get("status", "candidate"),
        "projection_method": atom.get("projection_method", "supplied-predicate-atom"),
        "receipt_ids": list(atom.get("receipt_ids", [])),
        **_optional_atom_fields(atom),
    }


def _atom_support_signature(atom: dict[str, Any]) -> tuple[Any, ...]:
    roles = atom.get("roles")
    qualifiers = atom.get("qualifiers")
    if isinstance(roles, dict):
        role_parts = []
        for key in sorted(roles):
            if key == "action":
                continue
            value = _role_value(roles.get(key))
            if value:
                role_parts.append((key, value))
        qualifier_parts = []
        if isinstance(qualifiers, dict):
            qualifier_parts = [
                (key, str(value))
                for key, value in sorted(qualifiers.items())
                if key != "polarity" and value not in (None, "", "unknown")
            ]
        return (
            atom.get("domain"),
            atom.get("structural_signature") or atom.get("predicate"),
            atom.get("predicate"),
            tuple(role_parts),
            tuple(qualifier_parts),
        )
    return (
        atom.get("predicate"),
        tuple(atom.get("arguments") or []),
    )


def _residual_records(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    residuals = []
    for left_index, left in enumerate(atoms):
        for right in atoms[left_index + 1 :]:
            same_body = _atom_support_signature(left) == _atom_support_signature(right)
            if same_body and left.get("polarity") != right.get("polarity"):
                status = "contested"
                relation = "polarity-conflict"
                residual_level = "contradiction"
            elif _is_classification_tension(left, right):
                status = "contested"
                relation = "classification-tension"
                residual_level = "contradiction"
            else:
                status = "abstained"
                relation = "no-typed-meet"
                residual_level = "no_typed_meet"
            residuals.append(
                {
                    "id": stable_id("resid", {"left": left["id"], "right": right["id"], "relation": relation}),
                    "left_atom_id": left["id"],
                    "right_atom_id": right["id"],
                    "relation": relation,
                    "status": status,
                    "residual_level": residual_level,
                    "receipt_ids": sorted(left.get("receipt_ids", []) + right.get("receipt_ids", [])),
                }
            )
    return residuals


def _is_classification_tension(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("predicate") != "be/classify" or right.get("predicate") != "be/classify":
        return False
    if left.get("domain") != "classification" or right.get("domain") != "classification":
        return False
    if left.get("polarity") == right.get("polarity"):
        return False
    left_subject = _role_value((left.get("roles") or {}).get("agent") if isinstance(left.get("roles"), dict) else None)
    right_subject = _role_value((right.get("roles") or {}).get("agent") if isinstance(right.get("roles"), dict) else None)
    left_theme = _role_value((left.get("roles") or {}).get("theme") if isinstance(left.get("roles"), dict) else None)
    right_theme = _role_value((right.get("roles") or {}).get("theme") if isinstance(right.get("roles"), dict) else None)
    return bool(left_subject and left_subject == right_subject and left_theme and right_theme and left_theme != right_theme)


def _pnf_emission_receipts(atoms: list[dict[str, Any]], pnfs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pnf_by_atom = {str(pnf.get("atom_id")): pnf for pnf in pnfs if pnf.get("atom_id")}
    receipts = []
    for atom in atoms:
        atom_id = str(atom.get("id") or "")
        pnf = pnf_by_atom.get(atom_id)
        if not atom_id or pnf is None:
            continue
        source_span = _atom_source_span(atom)
        emitted_atom = {
            "predicate": atom.get("predicate"),
            "structural_signature": atom.get("structural_signature") or atom.get("predicate"),
            "roles": atom.get("roles") or {},
            "qualifiers": atom.get("qualifiers") or {"polarity": atom.get("polarity", "positive")},
            "wrapper": atom.get("wrapper") or {"status": "structural_projection", "evidence_only": True},
            "provenance": atom.get("provenance") or [],
            "domain": atom.get("domain"),
            "arguments": atom.get("arguments") or [],
        }
        receipt_id = stable_id("pnfr", {"atom_id": atom_id, "pnf_id": pnf.get("id"), "emitted_atom": emitted_atom, "source_span": source_span})
        receipts.append(
            {
                "id": receipt_id,
                "schema": "sl.pnf_emission_receipt.v0_1",
                "status": "available",
                "parser_profile": "sensiblaw.conversation_vm.compile_turn.v0_1",
                "reducer_profile": atom.get("projection_method", "unknown"),
                "source_span": source_span,
                "atom_id": atom_id,
                "pnf_id": pnf.get("id"),
                "emitted_atom": emitted_atom,
                "receipt_ids": sorted(set(atom.get("receipt_ids") or [])),
            }
        )
    return receipts


def _atom_source_span(atom: dict[str, Any]) -> dict[str, Any]:
    provenance = atom.get("provenance") or []
    for item in provenance:
        text = str(item)
        for prefix in ("copular:", "head:", "arg:", "subject:", "neg:"):
            if text.startswith(prefix):
                try:
                    start, end = text[len(prefix) :].split("-", 1)
                    return {"provenance_ref": text, "start": int(start), "end": int(end)}
                except ValueError:
                    continue
    return {"provenance": list(provenance)}


def _pnf_residual_receipts(
    residuals: list[dict[str, Any]],
    pnf_emission_receipts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    receipt_by_atom = {str(item.get("atom_id")): item for item in pnf_emission_receipts if item.get("atom_id")}
    receipts = []
    for residual in residuals:
        if residual.get("status") != "contested":
            continue
        left = receipt_by_atom.get(str(residual.get("left_atom_id")))
        right = receipt_by_atom.get(str(residual.get("right_atom_id")))
        missing = []
        if left is None:
            missing.append("leftEmissionReceipt")
        if right is None:
            missing.append("rightEmissionReceipt")
        payload = {
            "residual_id": residual.get("id"),
            "left_emission_receipt_id": left.get("id") if left else None,
            "right_emission_receipt_id": right.get("id") if right else None,
            "residual_level": residual.get("residual_level", "contradiction"),
            "relation": residual.get("relation"),
            "residual_computation_profile": "sensiblaw.conversation_vm.residual_records.v0_1",
            "hecke_candidate_pool_receipt_id": None,
            "runtime_provider_status": "missingHeckeCandidatePoolReceiptId",
        }
        status = "diagnostic" if missing else "available_without_hecke_candidate_pool"
        if missing:
            payload["missing_fields"] = missing
        receipt_id = stable_id("pnfres", payload)
        receipts.append(
            {
                "id": receipt_id,
                "schema": "sl.pnf_residual_receipt.v0_1",
                "status": status,
                "left_atom_id": residual.get("left_atom_id"),
                "right_atom_id": residual.get("right_atom_id"),
                "left_emission_receipt_id": payload["left_emission_receipt_id"],
                "right_emission_receipt_id": payload["right_emission_receipt_id"],
                "residual_id": residual.get("id"),
                "residual_level": payload["residual_level"],
                "relation": residual.get("relation"),
                "payload": payload,
                "receipt_ids": sorted(set(residual.get("receipt_ids") or [])),
            }
        )
    return receipts


def _promotion_gates(
    source: dict[str, Any],
    excerpts: list[dict[str, Any]],
    statements: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks = {
        "source_receipt": bool(source.get("receipt_id")),
        "excerpt_receipts": bool(excerpts) and all(item.get("receipt_id") for item in excerpts),
        "statement_receipts": bool(statements) and all(item.get("receipt_ids") for item in statements),
        "observation_receipts": bool(observations) and all(item.get("receipt_ids") for item in observations),
        "predicate_atom_receipts": bool(atoms) and all(item.get("receipt_ids") for item in atoms),
        "external_promotion_authority": False,
    }
    gates = []
    for name, passed in checks.items():
        gates.append(
            {
                "id": stable_id("gate", {"source": source["id"], "name": name}),
                "name": name,
                "status": "supported" if passed else "blocked",
                "receipt_ids": [source["receipt_id"]] if source.get("receipt_id") else [],
            }
        )
    return gates


def _proof_obligations(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": stable_id("obl", {"gate_id": gate["id"]}),
            "gate_id": gate["id"],
            "status": "open",
            "description": f"Supply receipts for gate {gate['name']}",
        }
        for gate in gates
        if gate["status"] == "blocked"
    ]
