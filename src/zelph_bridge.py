from __future__ import annotations

import copy
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping




ZELPH_BRIDGE_VERSION = "fact_intake.zelph_bridge.v1"
_ASSERTION_PREDICATES = {"claimed", "denied", "admitted", "alleged"}
_PROCEDURAL_OUTCOME_PREDICATES = {"ordered", "ruled", "decided_by", "held_that"}
_DERIVATION_RE = re.compile(r"^\(\s*(.*?)\s*\)\s*⇐")


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
    
    def _parse_column_triple(payload: str) -> dict[str, str] | None:
        parts = [part for part in re.split(r"\s{2,}", payload.strip()) if part.strip()]
        if len(parts) != 3:
            return None
        return {
            "subject": parts[0].strip(),
            "predicate": parts[1].strip(),
            "object": parts[2].strip(),
        }

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        
        # Check for derivation format: ( sub pred obj ) <= ...
        derivation_match = _DERIVATION_RE.match(line)
        if derivation_match:
            triple = _parse_column_triple(derivation_match.group(1))
            if triple:
                triples.append(triple)
            continue
            
        # Strip "Answer: " prefix if present (some versions of zelph output this)
        if line.startswith("Answer:"):
            line = line.removeprefix("Answer:").strip()
            
        # Ignore rules and internal structures
        if "=>" in line or line.startswith("{"):
            continue
            
        triple = _parse_column_triple(line)
        if triple:
            triples.append(triple)
        elif line.count(" ") == 2:
            # Fallback for exactly 2 spaces (simple s p o)
            parts = line.split()
            if len(parts) == 3:
                triples.append({"subject": parts[0], "predicate": parts[1], "object": parts[2]})
            
    return triples


def run_zelph_inference(facts: str, rules: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        bundle_path = tmpdir_path / "bundle.zlp"
        bundle_text = facts + "\n\n" + rules
        bundle_path.write_text(bundle_text, encoding="utf-8")
        
        # Debugging: write bundle to /tmp as well
        Path("/tmp/zelph_debug_bundle.zlp").write_text(bundle_text, encoding="utf-8")

        try:
            result = subprocess.run(
                ["zelph", str(bundle_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,  # Safety timeout for recursive rules
            )
        except FileNotFoundError:
            return {
                "status": "engine_unavailable",
                "stdout": "",
                "stderr": "zelph command not found",
                "triples": [],
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "engine_timeout",
                "stdout": "",
                "stderr": "Zelph engine timed out (recursive rule limit?)",
                "triples": [],
            }
        except subprocess.CalledProcessError as exc:
            return {
                "status": "engine_error",
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "triples": [],
            }

        # Debugging: print raw output to stderr if needed
        # print(f"DEBUG: ZELPH STDOUT:\n{result.stdout}", file=sys.stderr)
        # print(f"DEBUG: ZELPH STDERR:\n{result.stderr}", file=sys.stderr)

        return {
            "status": "ok",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "triples": parse_zelph_inference(result.stdout),
        }


def workbench_to_zelph_facts(workbench: Mapping[str, Any]) -> str:
    from src.fact_intake.lexical_packs import build_fact_lexical_projection
    facts: list[str] = []
    fact_lookup = {
        str(fact.get("fact_id")): fact
        for fact in workbench.get("facts", [])
        if isinstance(fact, Mapping) and fact.get("fact_id")
    }
    for fact_id, fact in fact_lookup.items():
        node = _fact_node_id(fact_id)
        facts.append(f'{node} "fact_id" {_quote_zelph_text(fact_id)}')
        for source_type in fact.get("source_types", []):
            facts.append(f'{node} "source_type" {_quote_zelph_text(source_type)}')
        for value in fact.get("source_signal_classes", []):
            facts.append(f'{node} "source_signal_class" {_quote_zelph_text(value)}')
        for value in fact.get("signal_classes", []):
            facts.append(f'{node} "signal_class" {_quote_zelph_text(value)}')
        for predicate in fact.get("legal_procedural_predicates", []):
            facts.append(f'{node} "legal_procedural_predicate" {_quote_zelph_text(predicate)}')
        projection = build_fact_lexical_projection(fact)
        for pack_name in projection.pack_names:
            facts.append(f'{node} "lexical pack" {_quote_zelph_text(pack_name)}')
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
            node = _fact_node_id(fact.get("fact_id"))
            facts.append(f'{node} "has_observation_predicate" {_quote_zelph_text(predicate)}')
            object_text = str(observation.get("object_text") or "").strip()
            if object_text:
                facts.append(f'{node} {_quote_zelph_text(predicate)} {_quote_zelph_text(object_text)}')
            provenance = observation.get("provenance")
            if isinstance(provenance, Mapping):
                for value in provenance.get("signal_classes", []):
                    facts.append(f'{node} "observation_signal_class" {_quote_zelph_text(value)}')

    for idx, row in enumerate(workbench.get("rule_atoms", [])):
        if not isinstance(row, Mapping):
            continue
        uid = f"db_atom_{idx}"
        doc_id = row.get("doc_id")
        if doc_id:
            facts.append(f'{uid} "from document" {_quote_zelph_text(f"doc_{doc_id}")}')
        stable_id = row.get("stable_id")
        if stable_id:
            facts.append(f'{uid} "stable id" {_quote_zelph_text(stable_id)}')
        for field in ("party", "role", "modality", "action", "scope"):
            val = row.get(field)
            if val:
                facts.append(f'{uid} "has {field}" {_quote_zelph_text(val)}')

    return "\n".join(_dedupe(facts))


def _native_rule_triples(workbench: Mapping[str, Any]) -> list[dict[str, str]]:
    from src.fact_intake.lexical_packs import build_fact_lexical_projection
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

        all_source_signals = source_signal_classes | lexical_source_signal_classes
        all_signals = signal_classes | lexical_signal_classes

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
        if "is_reversion" in observation_predicates or "volatility_signal" in all_signals:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "volatility_signal"})
        if "reversion_edit" in all_signals:
            inferred.append({"subject": node, "predicate": "is_reversion", "object": "True"})
        if "has_context_reason" in all_signals:
            inferred.append({"subject": node, "predicate": "has_context_reason", "object": "True"})

        if ("is_reversion" in observation_predicates or "reversion_edit" in all_signals) and not ("has_context_reason" in all_signals):
            inferred.append({"subject": node, "predicate": "signal_class", "object": "Reversion without context"})

        if "administrative_edit" in all_signals:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "administrative_edit"})
        if "archive_management_edit" in all_signals:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "archive_management_edit"})
        if {"public_summary", "wiki_article"} & all_source_signals and not {"legal_record", "procedural_record", "strong_legal_source"} & all_source_signals:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "authority_transfer_risk"})
        if {"public_summary", "wiki_article"} & all_source_signals and {"legal_record", "procedural_record", "strong_legal_source"} & all_source_signals:
            inferred.append({"subject": node, "predicate": "signal_class", "object": "public_knowledge_not_authority"})
        if "wikidata_claim" in all_source_signals and ({"public_summary", "wiki_article"} & all_source_signals or {"identity_claim", "structural_ambiguity", "procedural_outcome"} & all_signals):
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
    from src.fact_intake.lexical_packs import build_fact_lexical_projection
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
