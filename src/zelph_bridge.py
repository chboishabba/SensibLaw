from __future__ import annotations

import copy
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from src.fact_intake.lexical_packs import build_fact_lexical_projection


ZELPH_BRIDGE_VERSION = "fact_intake.zelph_bridge.v1"
_TRIPLE_RE = re.compile(r'"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"')
_ASSERTION_PREDICATES = {"claimed", "denied", "admitted", "alleged"}
_PROCEDURAL_OUTCOME_PREDICATES = {"ordered", "ruled", "decided_by", "held_that"}


def _escape_zelph_text(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _quote_zelph_text(value: Any) -> str:
    return f'"{_escape_zelph_text(value)}"'


def _fact_node_id(fact_id: Any) -> str:
    raw = str(fact_id or "unknown")
    return f"fact_{raw.replace(':', '_').replace('-', '_')}"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if str(value).strip()))


def load_zelph_rules(*rule_paths: Path) -> str:
    blocks: list[str] = []
    for path in rule_paths:
        blocks.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(block for block in blocks if block)


def parse_zelph_inference(output: str) -> list[dict[str, str]]:
    triples: list[dict[str, str]] = []
    for line in output.splitlines():
        match = _TRIPLE_RE.search(line.strip())
        if not match:
            continue
        subject, predicate, obj = match.groups()
        triples.append(
            {
                "subject": bytes(subject, "utf-8").decode("unicode_escape"),
                "predicate": bytes(predicate, "utf-8").decode("unicode_escape"),
                "object": bytes(obj, "utf-8").decode("unicode_escape"),
            }
        )
    return triples


def run_zelph_inference(facts: str, rules: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        facts_file = tmpdir_path / "facts.zlp"
        rules_file = tmpdir_path / "rules.zlp"
        query_file = tmpdir_path / "query.zph"

        facts_file.write_text(facts, encoding="utf-8")
        rules_file.write_text(rules, encoding="utf-8")
        query_file.write_text(f'include "{rules_file}"\ninclude "{facts_file}"\n', encoding="utf-8")

        try:
            result = subprocess.run(
                ["zelph", str(query_file)],
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError:
            return {
                "status": "engine_unavailable",
                "stdout": "",
                "stderr": "zelph command not found",
                "triples": [],
            }
        except subprocess.CalledProcessError as exc:
            return {
                "status": "engine_error",
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "triples": [],
            }

        return {
            "status": "ok",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "triples": parse_zelph_inference(result.stdout),
        }


def workbench_to_zelph_facts(workbench: Mapping[str, Any]) -> str:
    facts: list[str] = []
    fact_lookup = {
        str(fact.get("fact_id")): fact
        for fact in workbench.get("facts", [])
        if isinstance(fact, Mapping) and fact.get("fact_id")
    }
    for fact_id, fact in fact_lookup.items():
        node = _fact_node_id(fact_id)
        facts.append(f'{_quote_zelph_text(node)} "fact_id" {_quote_zelph_text(fact_id)}.')
        for source_type in fact.get("source_types", []):
            facts.append(f'{_quote_zelph_text(node)} "source_type" {_quote_zelph_text(source_type)}.')
        for value in fact.get("source_signal_classes", []):
            facts.append(f'{_quote_zelph_text(node)} "source_signal_class" {_quote_zelph_text(value)}.')
        for value in fact.get("signal_classes", []):
            facts.append(f'{_quote_zelph_text(node)} "signal_class" {_quote_zelph_text(value)}.')
        for predicate in fact.get("legal_procedural_predicates", []):
            facts.append(f'{_quote_zelph_text(node)} "legal_procedural_predicate" {_quote_zelph_text(predicate)}.')
        projection = build_fact_lexical_projection(fact)
        for pack_name in projection.pack_names:
            facts.append(f'{_quote_zelph_text(node)} "lexical pack" {_quote_zelph_text(pack_name)}.')
        facts.extend(projection.facts)

    for observation in workbench.get("observations", []):
        if not isinstance(observation, Mapping):
            continue
        observation_statement_id = observation.get("statement_id")
        predicate = str(observation.get("predicate_key") or "").strip()
        if not predicate:
            continue
        for fact in fact_lookup.values():
            if observation_statement_id not in set(fact.get("statement_ids", [])):
                continue
            node = _fact_node_id(fact["fact_id"])
            facts.append(f'{_quote_zelph_text(node)} "has_observation_predicate" {_quote_zelph_text(predicate)}.')
            object_text = str(observation.get("object_text") or "").strip()
            if object_text:
                facts.append(f'{_quote_zelph_text(node)} {_quote_zelph_text(predicate)} {_quote_zelph_text(object_text)}.')
            provenance = observation.get("provenance")
            if isinstance(provenance, Mapping):
                for value in provenance.get("signal_classes", []):
                    facts.append(f'{_quote_zelph_text(node)} "observation_signal_class" {_quote_zelph_text(value)}.')

    return "\n".join(_dedupe(facts))


def _native_rule_triples(workbench: Mapping[str, Any]) -> list[dict[str, str]]:
    inferred: list[dict[str, str]] = []
    for fact in workbench.get("facts", []):
        if not isinstance(fact, Mapping):
            continue
        fact_id = str(fact.get("fact_id") or "").strip()
        if not fact_id:
            continue
        node = _fact_node_id(fact_id)
        source_types = set(str(value) for value in fact.get("source_types", []) if str(value).strip())
        source_signal_classes = set(str(value) for value in fact.get("source_signal_classes", []) if str(value).strip())
        signal_classes = set(str(value) for value in fact.get("signal_classes", []) if str(value).strip())
        observation_predicates = {str(row.get("predicate_key")) for row in fact.get("observations", []) if isinstance(row, Mapping)}
        projection = build_fact_lexical_projection(fact)
        lexical_signal_classes = set(projection.signal_classes)
        lexical_source_signal_classes = set(projection.source_signal_classes)

        if "wiki_article" in source_types:
            inferred.append({"subject": node, "predicate": "source_signal_class", "object": "public_summary"})
            inferred.append({"subject": node, "predicate": "source_signal_class", "object": "wiki_article"})
        if "wikidata_claim_sheet" in source_types:
            inferred.append({"subject": node, "predicate": "source_signal_class", "object": "wikidata_claim"})
        if observation_predicates & _ASSERTION_PREDICATES:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "party_assertion"})
        if observation_predicates & _PROCEDURAL_OUTCOME_PREDICATES:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "procedural_outcome"})
        for value in lexical_source_signal_classes:
            inferred.append({"subject": node, "predicate": "source_signal_class", "object": value})
        for value in lexical_signal_classes:
            inferred.append({"subject": node, "predicate": "signal_class", "object": value})
        if "is_reversion" in observation_predicates or "volatility_signal" in signal_classes or "volatility_signal" in lexical_signal_classes:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "volatility_signal"})
        if {"public_summary", "wiki_article"} & source_signal_classes and not {"legal_record", "procedural_record", "strong_legal_source"} & source_signal_classes:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "authority_transfer_risk"})
        if {"public_summary", "wiki_article"} & source_signal_classes and {"legal_record", "procedural_record", "strong_legal_source"} & source_signal_classes:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "public_knowledge_not_authority"})
        if "wikidata_claim" in source_signal_classes and ({"public_summary", "wiki_article"} & source_signal_classes or {"identity_claim", "structural_ambiguity", "procedural_outcome"} & signal_classes):
            inferred.append({"subject": node, "predicate": "signal_class", "object": "wiki_wikidata_claim_alignment"})

    return inferred


def _apply_inferred_triples(workbench: Mapping[str, Any], triples: list[dict[str, str]]) -> dict[str, Any]:
    enriched = copy.deepcopy(dict(workbench))
    fact_by_id = {
        str(fact.get("fact_id")): fact
        for fact in enriched.get("facts", [])
        if isinstance(fact, dict) and fact.get("fact_id")
    }
    fact_id_by_node = {_fact_node_id(fact_id): fact_id for fact_id in fact_by_id}
    inferred_by_fact_id: dict[str, dict[str, list[str]]] = {}
    for triple in triples:
        subject = str(triple.get("subject") or "")
        predicate = str(triple.get("predicate") or "")
        obj = str(triple.get("object") or "")
        fact_id = fact_id_by_node.get(subject)
        if fact_id not in fact_by_id:
            continue
        bucket = inferred_by_fact_id.setdefault(fact_id, {"signal_classes": [], "source_signal_classes": []})
        if predicate == "signal_class":
            bucket["signal_classes"].append(obj)
        elif predicate == "source_signal_class":
            bucket["source_signal_classes"].append(obj)

    for fact_id, payload in inferred_by_fact_id.items():
        fact = fact_by_id[fact_id]
        fact["signal_classes"] = _dedupe(list(fact.get("signal_classes", [])) + payload["signal_classes"])
        fact["source_signal_classes"] = _dedupe(list(fact.get("source_signal_classes", [])) + payload["source_signal_classes"])
        fact["inferred_signal_classes"] = _dedupe(payload["signal_classes"])
        fact["inferred_source_signal_classes"] = _dedupe(payload["source_signal_classes"])

    for fact in fact_by_id.values():
        fact.setdefault("inferred_signal_classes", [])
        fact.setdefault("inferred_source_signal_classes", [])

    for queue_key in ("review_queue",):
        rows = enriched.get(queue_key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            fact = fact_by_id.get(str(row.get("fact_id") or ""))
            if not fact:
                continue
            row["signal_classes"] = list(fact.get("signal_classes", []))
            row["source_signal_classes"] = list(fact.get("source_signal_classes", []))
            row["inferred_signal_classes"] = list(fact.get("inferred_signal_classes", []))
            row["inferred_source_signal_classes"] = list(fact.get("inferred_source_signal_classes", []))

    operator_views = enriched.get("operator_views")
    if isinstance(operator_views, dict):
        for view in operator_views.values():
            if not isinstance(view, dict):
                continue
            items = view.get("items")
            if isinstance(items, list):
                for idx, row in enumerate(items):
                    if not isinstance(row, dict):
                        continue
                    fact = fact_by_id.get(str(row.get("fact_id") or ""))
                    if fact:
                        items[idx] = {
                            **row,
                            "signal_classes": list(fact.get("signal_classes", [])),
                            "source_signal_classes": list(fact.get("source_signal_classes", [])),
                            "inferred_signal_classes": list(fact.get("inferred_signal_classes", [])),
                            "inferred_source_signal_classes": list(fact.get("inferred_source_signal_classes", [])),
                        }

    serialized_fact_lines = workbench_to_zelph_facts(workbench)
    active_packs = sorted(
        {
            pack_name
            for fact in workbench.get("facts", [])
            if isinstance(fact, Mapping)
            for pack_name in build_fact_lexical_projection(fact).pack_names
        }
    )
    enriched["zelph"] = {
        "version": ZELPH_BRIDGE_VERSION,
        "rule_status": "portable_ok" if inferred_by_fact_id else "portable_noop",
        "facts_serialized_count": len(serialized_fact_lines.splitlines()) if serialized_fact_lines else 0,
        "inferred_fact_count": len(inferred_by_fact_id),
        "inferred_by_fact_id": inferred_by_fact_id,
        "active_packs": active_packs,
        "triples": triples,
    }
    return enriched


def enrich_workbench_with_zelph(
    workbench: Mapping[str, Any],
    *,
    rules: str | None = None,
) -> dict[str, Any]:
    facts = workbench_to_zelph_facts(workbench)
    portable_triples = _native_rule_triples(workbench)
    engine_result: dict[str, Any] | None = None
    rule_status = "portable_only"
    triples = list(portable_triples)
    if rules:
        engine_result = run_zelph_inference(facts, rules)
        if engine_result["status"] == "ok":
            rule_status = "engine_ok"
            triples.extend(engine_result.get("triples", []))
        else:
            rule_status = str(engine_result["status"])

    enriched = _apply_inferred_triples(workbench, _dedupe_triples(triples))
    enriched["zelph"] = {
        **enriched["zelph"],
        "rule_status": rule_status,
        "engine": engine_result,
    }
    return enriched


def _dedupe_triples(triples: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for triple in triples:
        key = (str(triple.get("subject") or ""), str(triple.get("predicate") or ""), str(triple.get("object") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append({"subject": key[0], "predicate": key[1], "object": key[2]})
    return out
