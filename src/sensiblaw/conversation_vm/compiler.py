"""Turn compiler for the Conversation VM.

The compiler is deliberately structural. It preserves source/excerpt/statement
receipts, projects statement carriers through optional reducer adapters when
available, and otherwise emits abstention-visible local carriers.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

from .schema import TURN_DELTA_SCHEMA, receipt, stable_id

try:
    from src.text.sentences import segment_sentences
except ModuleNotFoundError:  # pragma: no cover - installed package import path
    try:
        from text.sentences import segment_sentences
    except ModuleNotFoundError:  # pragma: no cover - minimal external use
        segment_sentences = None  # type: ignore[assignment]


def compile_turn(turn: dict[str, Any] | str) -> dict[str, Any]:
    payload = _coerce_turn(turn)
    text = str(payload.get("text", ""))
    turn_id = str(payload.get("turn_id") or stable_id("turn", {"text": text, "meta": payload.get("metadata", {})}))

    source = _source_record(turn_id, text, payload)
    excerpts = _excerpt_records(source, text)
    statements = [_statement_record(source, excerpt) for excerpt in excerpts]
    observations = _observation_records(source, excerpts, statements, payload)
    atoms, pnfs, projection_abstentions = _predicate_records(statements, payload)
    residuals = _residual_records(atoms)
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
        return [(sentence.start_char, sentence.end_char) for sentence in sentences if sentence.text.strip()]

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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    supplied_atoms = payload.get("predicate_atoms")
    if supplied_atoms:
        atoms = [_normalize_supplied_atom(atom) for atom in supplied_atoms]
    else:
        projector = _optional_projector()
        atoms = []
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
                    }
                )

    pnfs = []
    abstentions = []
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
    for module_name, function_name in (
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
            return [dict(item) for item in result]

        return projector
    return None


def _relations_to_atoms(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    atoms_by_id = {atom["id"]: atom for atom in bundle.get("atoms", []) if isinstance(atom, dict)}
    projected: list[dict[str, Any]] = []
    for relation in bundle.get("relations", []):
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
            projected.append(
                {
                    "predicate": str(relation.get("type") or "relation"),
                    "roles": roles,
                    "arguments": [value["value"] for value in roles.values()],
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
    }


def _residual_records(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    residuals = []
    for left_index, left in enumerate(atoms):
        for right in atoms[left_index + 1 :]:
            same_body = left["predicate"] == right["predicate"] and left["arguments"] == right["arguments"]
            if same_body and left.get("polarity") != right.get("polarity"):
                status = "contested"
                relation = "polarity-conflict"
            else:
                status = "abstained"
                relation = "no-typed-meet"
            residuals.append(
                {
                    "id": stable_id("resid", {"left": left["id"], "right": right["id"], "relation": relation}),
                    "left_atom_id": left["id"],
                    "right_atom_id": right["id"],
                    "relation": relation,
                    "status": status,
                    "receipt_ids": sorted(left.get("receipt_ids", []) + right.get("receipt_ids", [])),
                }
            )
    return residuals


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
