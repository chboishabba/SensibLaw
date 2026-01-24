from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import requests

from src.graph.inference import (
    PREDICTION_VERSION,
    PredictionSet,
    build_prediction_set,
    get_case_identifiers,
    get_provision_identifiers,
    legal_graph_to_triples,
    load_predictions_json,
    load_predictions_sqlite,
    persist_predictions_json,
    persist_predictions_sqlite,
    rank_predictions,
    score_applies_predictions,
    train_complex,
    train_distmult,
    train_mure,
    train_rotate,
    train_transe,
)
from src.graph.models import EdgeType, GraphEdge, GraphNode, LegalGraph, NodeType

from . import receipts as receipts_cli


def _print_json(data: object) -> None:
    """Serialise ``data`` to JSON and print it to stdout."""

    print(json.dumps(data, ensure_ascii=False))


def _load_graph_data(path: Path | str | None, *, flag: str = "--graph") -> dict:
    if path is None:
        raise ValueError("graph path is required")
    resolved = Path(path)
    if not resolved.exists():
        raise SystemExit(f"{flag} {resolved} does not exist")
    mode = resolved.stat().st_mode
    if not os.access(resolved, os.R_OK) or (mode & 0o444) == 0:
        raise SystemExit(f"{flag} {resolved} is not readable")
    data = json.loads(resolved.read_text(encoding="utf-8"))
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    return data


def _subgraph_from_data(data: Mapping[str, Sequence[Mapping[str, object]]], seeds: Sequence[str], hops: int) -> dict:
    """Return a subgraph containing nodes reachable from ``seeds`` within ``hops``."""

    nodes = list(data.get("nodes", []))
    edges = list(data.get("edges", []))
    id_key = "id" if nodes and "id" in nodes[0] else "identifier"
    node_map = {node[id_key]: node for node in nodes if id_key in node}
    if not seeds:
        selected_ids = set(node_map.keys())
    else:
        selected_ids = set(seeds) & set(node_map.keys())
        frontier = set(selected_ids)
        for _ in range(max(hops, 0)):
            next_frontier: set[str] = set()
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")
                if source in frontier and target in node_map:
                    next_frontier.add(target)
                if target in frontier and source in node_map:
                    next_frontier.add(source)
            next_frontier -= selected_ids
            if not next_frontier:
                break
            selected_ids.update(next_frontier)
            frontier = next_frontier
    selected_nodes = [node_map[node_id] for node_id in selected_ids if node_id in node_map]
    selected_edges = [
        edge
        for edge in edges
        if edge.get("source") in selected_ids and edge.get("target") in selected_ids
    ]
    return {"nodes": selected_nodes, "edges": selected_edges}


def _subgraph_to_dot(data: Mapping[str, Sequence[Mapping[str, object]]], *, id_key: str = "identifier") -> str:
    lines = ["digraph G {"]
    for node in data.get("nodes", []):
        identifier = node.get(id_key) or node.get("id")
        if identifier is None:
            continue
        lines.append(f'    "{identifier}" [label="{identifier}"];')
    for edge in data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        label = edge.get("type", "")
        if source is None or target is None:
            continue
        lines.append(f'    "{source}" -> "{target}" [label="{label}"];')
    lines.append("}")
    return "\n".join(lines)


def _coerce_node_type(value: object) -> NodeType:
    if isinstance(value, NodeType):
        return value
    if value is None:
        return NodeType.DOCUMENT
    text = str(value)
    for node_type in NodeType:
        if node_type.value == text.lower() or node_type.name.lower() == text.lower():
            return node_type
    return NodeType.DOCUMENT


def _coerce_edge_type(value: object) -> EdgeType:
    if isinstance(value, EdgeType):
        return value
    if value is None:
        return EdgeType.CITES
    text = str(value)
    for edge_type in EdgeType:
        if edge_type.value == text.lower() or edge_type.name.lower() == text.lower():
            return edge_type
    return EdgeType.CITES


def _normalise_relation(value: Optional[str]) -> str:
    if not value:
        return EdgeType.APPLIES.value
    for edge_type in EdgeType:
        if edge_type.value == value.lower() or edge_type.name.lower() == value.lower():
            return edge_type.value
    return value


def _graph_from_payload(data: Mapping[str, Sequence[Mapping[str, object]]]) -> LegalGraph:
    graph = LegalGraph()
    for node in data.get("nodes", []):
        identifier = node.get("id") or node.get("identifier")
        if not identifier:
            continue
        metadata = {
            key: value
            for key, value in node.items()
            if key not in {"id", "identifier", "type", "metadata", "date"}
        }
        if isinstance(node.get("metadata"), Mapping):
            metadata.update(node["metadata"])
        node_date = node.get("date")
        parsed_date = date.fromisoformat(node_date) if isinstance(node_date, str) else None
        graph.add_node(
            GraphNode(
                type=_coerce_node_type(node.get("type")),
                identifier=str(identifier),
                metadata=dict(metadata),
                date=parsed_date,
            )
        )
    for edge in data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        if source not in graph.nodes or target not in graph.nodes:
            continue
        metadata = {
            key: value
            for key, value in edge.items()
            if key not in {"source", "target", "type", "weight", "metadata", "date"}
        }
        if isinstance(edge.get("metadata"), Mapping):
            metadata.update(edge["metadata"])
        edge_date = edge.get("date")
        parsed_date = date.fromisoformat(edge_date) if isinstance(edge_date, str) else None
        raw_weight = edge.get("weight", 1.0)
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            weight = 1.0
        graph.add_edge(
            GraphEdge(
                type=_coerce_edge_type(edge.get("type")),
                source=str(source),
                target=str(target),
                metadata=dict(metadata),
                date=parsed_date,
                weight=weight,
            )
        )
    return graph


def _prediction_payload(predictions: PredictionSet) -> Dict[str, object]:
    return {
        "version": PREDICTION_VERSION,
        "relation": predictions.relation,
        "generated_at": predictions.generated_at,
        "non_deterministic": predictions.non_deterministic,
        "predictions": [
            {
                "case_id": item.case_id,
                "provision_id": item.provision_id,
                "score": item.score,
                "rank": item.rank,
            }
            for item in predictions.predictions
        ],
    }


def _require_path(path: Optional[Path], flag: str) -> Path:
    if path is None:
        raise SystemExit(f"{flag} is required")
    return path


def _handle_publish(args: argparse.Namespace) -> None:
    from src.publish.mirror import generate_site

    generate_site(args.seed, args.out, pack_path=args.pack)


def _handle_eval_goldset(args: argparse.Namespace) -> None:
    from scripts.eval_goldset import main as eval_goldset_main

    eval_goldset_main(args.threshold)


def _handle_get(args: argparse.Namespace) -> None:
    from src.storage import VersionedStore

    store = VersionedStore(args.db)
    try:
        as_at = date.fromisoformat(args.as_at) if args.as_at else date.today()
        doc = store.snapshot(int(args.id), as_at)
        if doc is None:
            print("Not found")
            return
        print(doc.to_json())
    finally:
        store.close()


def _handle_view(args: argparse.Namespace) -> None:
    from src.storage import VersionedStore
    from src.rules.extractor import extract_rules

    store = VersionedStore(args.db)
    try:
        doc = store.get_by_canonical_id(args.id)
        if doc is None:
            raise SystemExit(f"No document with canonical id '{args.id}'")
        rules = extract_rules(doc.body)
        result = {
            "text": doc.body,
            "metadata": doc.metadata.to_dict(),
            "provenance": doc.metadata.provenance,
            "ontology_tags": doc.metadata.ontology_tags,
            "rules": [rule.__dict__ for rule in rules],
        }
        _print_json(result)
    finally:
        store.close()


def _handle_extract_rules(args: argparse.Namespace) -> None:
    from src.rules.extractor import extract_rules

    rules = extract_rules(args.text)
    _print_json([rule.__dict__ for rule in rules])


def _handle_ontology_lookup(args: argparse.Namespace) -> None:
    from src.ontology.search import filter_candidates

    response = requests.get(args.url, params={"q": args.term})
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise SystemExit("Ontology service did not return a list")
    results = filter_candidates(
        args.term,
        data,
        threshold=args.threshold,
        limit=args.limit,
    )
    _print_json(results)


def _handle_ontology_upsert(args: argparse.Namespace) -> None:
    from sensiblaw.db.dao import LegalSourceDAO, ensure_database

    connection = sqlite3.connect(args.db)
    try:
        ensure_database(connection)
        dao = LegalSourceDAO(connection)
        source_id = dao.upsert_source(
            legal_system_code=args.legal_system,
            norm_source_category_code=args.category,
            citation=args.citation,
            title=args.title,
            source_url=args.url,
            promulgation_date=args.promulgation_date,
            summary=args.summary,
            notes=args.notes,
        )
        record = dao.get_by_citation(
            legal_system_code=args.legal_system, citation=args.citation
        )
        payload = {"id": source_id, "citation": args.citation}
        if record:
            payload.update(
                {
                    "title": record.title,
                    "category": record.norm_source_category_code,
                    "legal_system": record.legal_system_code,
                }
            )
        _print_json(payload)
    finally:
        connection.close()


def _handle_extract_frl(args: argparse.Namespace) -> None:
    from src.ingestion.frl import fetch_acts

    payload = json.loads(args.data.read_text()) if args.data else None
    nodes, edges = fetch_acts(args.api_url, data=payload)
    _print_json({"nodes": nodes, "edges": edges})


def _handle_extract(args: argparse.Namespace) -> None:
    if args.extract_command == "rules":
        _handle_extract_rules(args)
        return
    if args.extract_command == "frl":
        _handle_extract_frl(args)
        return
    if getattr(args, "text", None):
        _handle_extract_rules(args)
        return
    parser = getattr(args, "parser", None)
    if parser is not None:
        parser.print_help()
    raise SystemExit(2)


def _handle_check(args: argparse.Namespace) -> None:
    from src.rules import Rule
    from src.rules.reasoner import check_rules

    data = json.loads(args.rules)
    rules = [Rule(**item) for item in data]
    issues = check_rules(rules)
    _print_json(issues)


def _handle_pdf_fetch(args: argparse.Namespace) -> None:
    from src.pdf_ingest import process_pdf

    doc, stored_id = process_pdf(
        args.path,
        output=args.output,
        jurisdiction=args.jurisdiction,
        citation=args.citation,
        title=args.title,
        cultural_flags=args.cultural_flags,
        db_path=args.db,
        doc_id=args.doc_id,
    )
    source_id = (
        args.logic_tree_source_id
        or doc.metadata.canonical_id
        or (str(stored_id) if stored_id is not None else None)
        or args.path.stem
    )

    sqlite_path = args.logic_tree_sqlite or (args.logic_tree_artifacts / "logic_tree.sqlite")
    logic_tree_info: dict[str, object] | None = None
    try:
        from src import pipeline

        pipeline.build_and_persist_logic_tree(
            doc.body,
            source_id=source_id,
            artifacts_dir=args.logic_tree_artifacts,
            sqlite_path=sqlite_path,
            enable_fts=not args.logic_tree_disable_fts,
        )
        logic_tree_info = {
            "source_id": source_id,
            "json": str(args.logic_tree_artifacts / f"{source_id}.logic_tree.json"),
            "sqlite": str(sqlite_path),
            "enable_fts": not args.logic_tree_disable_fts,
        }
    except Exception as exc:  # pragma: no cover - defensive to avoid failing ingestion
        logic_tree_info = {"source_id": source_id, "error": f"logic tree build skipped: {exc}"}

    result = {"document": doc.to_dict()}
    if stored_id is not None:
        result["doc_id"] = stored_id
    if logic_tree_info is not None:
        result["logic_tree"] = logic_tree_info
    _print_json(result)


def _handle_polis_import(args: argparse.Namespace) -> None:
    from src.ingest import polis as polis_ingest
    from src.receipts import build_pack

    seeds = polis_ingest.fetch_conversation(
        args.conversation,
        limit=args.limit,
        max_retries=args.max_retries,
        sleep_between_retries=args.sleep_between_retries,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        seed_id = seed.get("id")
        if not seed_id:
            continue
        label = seed.get("label") or ""
        build_pack(args.out / seed_id, label)
    _print_json({"concepts": seeds})


def _handle_distinguish(args: argparse.Namespace) -> None:
    if not args.case:
        raise SystemExit("--case is required")
    if not args.story:
        raise SystemExit("--story is required")
    story_path = Path(args.story)
    if not story_path.exists():
        raise SystemExit("Error: story file not found")

    if args.case == "[2002] HCA 14":
        from src.distinguish.factor_packs import distinguish_story

        result = distinguish_story(args.case, story_path)
        _print_json(result)
        return

    from src.distinguish.engine import compare_story_to_case
    from src.distinguish.loader import load_case_silhouette

    try:
        case_silhouette = load_case_silhouette(args.case)
    except Exception as exc:  # pragma: no cover - error path tested via CLI tests
        raise SystemExit(str(exc)) from exc

    try:
        story_data = json.loads(story_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Error reading story: {exc}") from exc

    raw_tags = story_data.get("facts") or story_data.get("tags") or {}
    story_tags = {key: bool(value) for key, value in raw_tags.items()}
    result = compare_story_to_case(story_tags, case_silhouette)

    overlaps: List[dict[str, object]] = []
    for item in result.get("overlaps", []):
        paragraph = item.get("candidate", {}).get("paragraph")
        if paragraph:
            overlaps.append({"text": paragraph})

    missing: List[dict[str, object]] = []
    seen: set[str] = set()
    for fact_text in case_silhouette.fact_tags.keys():
        key = fact_text.replace(" ", "_")
        if not story_tags.get(key, False) and fact_text not in seen:
            missing.append({"text": fact_text})
            seen.add(fact_text)
    for item in result.get("missing", []):
        fact_id = item.get("id")
        if not fact_id:
            continue
        text = fact_id.replace("_", " ")
        if text not in seen:
            missing.append({"text": text})
            seen.add(text)

    _print_json({"overlaps": overlaps, "missing": missing})


def _handle_concepts_match(args: argparse.Namespace) -> None:
    from src.concepts.matcher import ConceptMatcher

    text = args.text or args.text_arg
    if not text:
        parser = getattr(args, "parser", None)
        if parser is not None:
            parser.error("invalid choice: text is required")
        raise SystemExit("text is required")
    matcher = ConceptMatcher()
    hits = matcher.match(text)
    payload = [{"concept_id": hit.concept_id, "start": hit.start, "end": hit.end} for hit in hits]
    _print_json(payload)


def _handle_query_case(args: argparse.Namespace) -> None:
    from src.api import routes
    from src.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
    from src.ingestion import hca

    nodes, edges = hca.crawl_year(args.year)
    for node in nodes:
        metadata = {k: v for k, v in node.items() if k not in {"id", "type"}}
        routes._graph.add_node(
            GraphNode(type=NodeType.DOCUMENT, identifier=node["id"], metadata=metadata)
        )
    for edge in edges:
        routes._graph.add_edge(
            GraphEdge(type=EdgeType.CITES, source=edge["from"], target=edge["to"])
        )
    case = next((node for node in nodes if node["id"] == args.id), None)
    if case is None:
        _print_json({})
        return
    citations = [edge["to"] for edge in edges if edge["from"] == args.id]
    result = {"catchwords": case.get("catchwords", []), "citations": citations}
    _print_json(result)


def _handle_query_concepts(args: argparse.Namespace) -> None:
    from src.pipeline import build_cloud, match_concepts, normalise
    from src.pipeline.input_handler import parse_input

    if args.graph:
        data = json.loads(Path(args.graph).read_text(encoding="utf-8"))
        raw_query = parse_input(data)
    else:
        raw_query = parse_input(args.text)
    text = normalise(raw_query)
    concepts = match_concepts(text)
    cloud = build_cloud(concepts)
    _print_json({"cloud": cloud})


def _handle_query_timeline(args: argparse.Namespace) -> None:
    from src.reason.timeline import build_timeline

    graph_path = _require_path(args.graph_file, "--graph-file")
    data = _load_graph_data(graph_path, flag="--graph-file")
    events = build_timeline(data.get("nodes", []), data.get("edges", []), args.case)
    payload = [
        {
            "date": event.date.isoformat(),
            "text": event.text,
            **({"citation": event.citation} if event.citation else {}),
        }
        for event in events
    ]
    _print_json(payload)


def _handle_graph_subgraph(args: argparse.Namespace) -> None:
    output_dot = args.dot
    if args.graph_file:
        if str(args.graph_file) == "-":
            raw = sys.stdin.read()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise SystemExit(f"Invalid JSON supplied via stdin: {exc}") from exc
            output_dot = True
        else:
            data = _load_graph_data(args.graph_file, flag="--graph-file")
        subgraph = _subgraph_from_data(data, args.node or [], args.hops)
        if output_dot:
            print(_subgraph_to_dot(subgraph, id_key="id"))
        else:
            _print_json(subgraph)
        return

    from src import sample_data

    subgraph = sample_data.build_subgraph(args.node, args.limit, args.offset)
    if output_dot:
        print(sample_data.subgraph_to_dot(subgraph))
    else:
        _print_json(subgraph)


def _handle_graph_query(args: argparse.Namespace) -> None:
    data = _load_graph_data(args.graph, flag="--graph")
    id_map = {node["id"]: node for node in data["nodes"] if "id" in node}
    selected_ids: set[str]
    if args.type:
        selected_ids = {node_id for node_id, node in id_map.items() if node.get("type") == args.type}
    else:
        selected_ids = set(id_map.keys())
    if args.start:
        from collections import deque

        queue = deque([(args.start, 0)])
        visited: set[str] = set()
        while queue:
            current, depth = queue.popleft()
            if current not in id_map or current in visited:
                continue
            visited.add(current)
            if depth >= args.depth:
                continue
            for edge in data["edges"]:
                if edge.get("source") == current:
                    queue.append((edge.get("target"), depth + 1))
                if edge.get("target") == current:
                    queue.append((edge.get("source"), depth + 1))
        selected_ids &= visited
    selected_nodes = [id_map[node_id] for node_id in selected_ids if node_id in id_map]
    selected_edges = [
        edge
        for edge in data["edges"]
        if edge.get("source") in selected_ids and edge.get("target") in selected_ids
    ]
    _print_json({"nodes": selected_nodes, "edges": selected_edges})


def _handle_graph_export(args: argparse.Namespace) -> None:
    data = _load_graph_data(args.graph, flag="--graph")
    graph = _graph_from_payload(data)
    triples_pack = legal_graph_to_triples(
        graph, include_external_refs=args.include_external_refs
    )
    _print_json(asdict(triples_pack))


def _handle_graph_inference_train(args: argparse.Namespace) -> None:
    relation = _normalise_relation(args.relation)
    data = _load_graph_data(args.graph)
    graph = _graph_from_payload(data)

    triples_pack = legal_graph_to_triples(graph)
    if not triples_pack.triples:
        raise SystemExit("Graph does not contain any edges to train on")

    training_kwargs = {"num_epochs": args.epochs, "batch_size": args.batch_size}
    optimizer_kwargs = {"lr": args.learning_rate}
    model_kwargs = {"embedding_dim": args.embedding_dim} if args.embedding_dim else {}

    trainers = {
        "transe": train_transe,
        "distmult": train_distmult,
        "complex": train_complex,
        "rotate": train_rotate,
        "mure": train_mure,
    }
    trainer = trainers[args.model.lower()]

    try:
        artifacts = trainer(
            triples_pack.triples,
            training_kwargs=training_kwargs,
            model_kwargs=model_kwargs or None,
            optimizer_kwargs=optimizer_kwargs,
            random_seed=args.random_seed,
        )
    except RuntimeError as exc:  # pragma: no cover - surfaced to CLI
        raise SystemExit(str(exc)) from exc

    cases = sorted(set(args.case)) if args.case else get_case_identifiers(graph)
    provisions = (
        sorted(set(args.provision)) if args.provision else get_provision_identifiers(graph)
    )

    if not cases:
        raise SystemExit("No case nodes available for scoring")
    if not provisions:
        raise SystemExit("No provision nodes available for scoring")

    raw_predictions = score_applies_predictions(
        artifacts.pipeline_result,
        artifacts.triples_factory,
        cases=cases,
        provisions=provisions,
        relation=relation,
    )

    ranked_predictions = rank_predictions(
        raw_predictions,
        relation=relation,
        top_k=args.top_k,
    )
    prediction_set = build_prediction_set(
        ranked_predictions,
        relation=relation,
        random_seed=args.random_seed,
    )

    if args.json_out:
        persist_predictions_json(prediction_set, Path(args.json_out))
    if args.sqlite_out:
        persist_predictions_sqlite(prediction_set, Path(args.sqlite_out))

    payload = _prediction_payload(prediction_set)
    _print_json(payload)


def _handle_graph_inference_rank(args: argparse.Namespace) -> None:
    relation = _normalise_relation(args.relation)
    prediction_set: Optional[PredictionSet] = None

    if args.sqlite:
        prediction_set = load_predictions_sqlite(Path(args.sqlite), relation=relation)
    elif args.json:
        prediction_set = load_predictions_json(Path(args.json))
    else:
        raise SystemExit("--json or --sqlite is required")

    if prediction_set.relation != relation:
        relation = prediction_set.relation

    predictions = prediction_set.for_case(args.case, top_k=args.top_k)
    payload = {
        "relation": relation,
        "generated_at": prediction_set.generated_at,
        "non_deterministic": prediction_set.non_deterministic,
        "case_id": args.case,
        "predictions": [
            {
                "case_id": item.case_id,
                "provision_id": item.provision_id,
                "score": item.score,
                "rank": item.rank,
            }
            for item in predictions
        ],
    }
    _print_json(payload)


def _handle_tests_run(args: argparse.Namespace) -> None:
    if args.template and args.facts:
        from src.tests.evaluator import evaluate as eval_table

        template = json.loads(args.template.read_text(encoding="utf-8"))
        facts = json.loads(args.facts.read_text(encoding="utf-8"))
        table = eval_table(template, facts)
        _print_json(table.to_json())
        return

    ids = args.tests or args.ids
    if not ids:
        raise SystemExit("--tests or --ids is required")
    if not args.story:
        raise SystemExit("--story is required")
    story = json.loads(args.story.read_text(encoding="utf-8"))

    if args.tests:
        factor_data: Mapping[str, Mapping[str, object]] = story.get("factors", {})
        results: List[dict[str, object]] = []
        for factor_id, info in factor_data.items():
            status_value = info.get("status")
            if status_value is True:
                status = "satisfied"
            elif status_value is False:
                status = "unsatisfied"
            else:
                status = "unknown"
            evidence = list(info.get("evidence", [])) if isinstance(info, Mapping) else []
            results.append(
                {
                    "id": factor_id,
                    "description": factor_id,
                    "status": status,
                    "evidence": evidence,
                }
            )
        payload = {"concept_id": ids[0], "results": results}
        _print_json(payload)
        return

    from src.api.routes import execute_tests

    result = execute_tests(ids, story)
    _print_json(result)


def _handle_cases_treatment(args: argparse.Namespace) -> None:
    from src.api.routes import ensure_sample_treatment_graph, fetch_case_treatment

    ensure_sample_treatment_graph()
    result = fetch_case_treatment(args.case_id)
    _print_json(result)


def _handle_harm_compute(args: argparse.Namespace) -> None:
    from tempfile import TemporaryDirectory

    from src.harm.index import _classify, _load_weights
    from src.tools.harm_index import compute_harm_index

    story = json.loads(args.story.read_text(encoding="utf-8"))
    weights_cfg = _load_weights()
    metrics: dict[str, float] = {"lost_evidence_items": story.get("lost_evidence_items", 0)}
    delay = min(story.get("delay_months", 0), weights_cfg.get("max_delay_months", 1))
    metrics["delay_months"] = delay / float(weights_cfg.get("max_delay_months", 1))
    for flag in story.get("flags", []):
        metrics[flag] = 1.0

    weights = {
        "lost_evidence_items": weights_cfg.get("lost_evidence_items", 0),
        "delay_months": weights_cfg.get("delay_months", 0),
    }
    for flag, weight in weights_cfg.get("flags", {}).items():
        weights[flag] = weight

    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "story.json"
        tmp_path.write_text(json.dumps({"stakeholder": "story", "metrics": metrics}))
        scores = compute_harm_index(data_dir=Path(tmpdir), weights=weights)

    score = scores.get("story", 0.0)
    level = _classify(
        score,
        weights_cfg.get("medium_threshold", 0.33),
        weights_cfg.get("high_threshold", 0.66),
    )
    result = {"score": score, "level": level}
    if args.out:
        Path(args.out).write_text(json.dumps(result))
    _print_json(result)


def _handle_treatment(args: argparse.Namespace) -> None:
    from src import sample_data

    limit = args.limit if args.limit is not None else sys.maxsize
    offset = args.offset or 0
    data = sample_data.treatments_for(args.doc, limit, offset)
    _print_json(data)


def _handle_provision(args: argparse.Namespace) -> None:
    from src import sample_data

    provision = sample_data.get_provision(args.doc, args.id)
    if provision is None:
        raise SystemExit("Provision not found")
    _print_json(provision)


def _handle_austlii_fetch(args: argparse.Namespace) -> None:
    from src.austlii_client import AustLIIClient
    from src.storage import VersionedStore

    sections = [s.strip() for s in args.sections.split(",") if s.strip()]
    base = args.act.rstrip("/")
    urls = [f"{base}/table.html", f"{base}/notes.html"]
    for section in sections:
        if section.endswith(".html"):
            urls.append(f"{base}/{section}")
        else:
            urls.append(f"{base}/{section}.html")

    client = AustLIIClient()
    store = VersionedStore(args.db)
    try:
        for url in urls:
            document = client.fetch_legislation(url)
            doc_id = store.generate_id()
            effective = document.metadata.date if isinstance(document.metadata.date, date) else date.today()
            store.add_revision(doc_id, document, effective)
    finally:
        store.close()


def _handle_concepts(args: argparse.Namespace) -> None:
    if args.concepts_command == "match":
        _handle_concepts_match(args)
    else:
        raise SystemExit("Unknown concepts command")


def _handle_tools_claim_builder(args: argparse.Namespace) -> None:
    from src.tools.claim_builder import build_claim

    directory = args.dir
    build_claim(directory)


def _handle_tools_counter_brief(args: argparse.Namespace) -> None:
    from src.tools.counter_brief import generate_counter_brief

    result = generate_counter_brief(args.file, args.output_dir)
    _print_json(result)


def _handle_intake_parse(args: argparse.Namespace) -> None:
    from src.intake.email_parser import fetch_messages, parse_email
    from src.intake.stub_builder import build_stub

    messages = fetch_messages(str(args.mailbox))
    for message in messages:
        data = parse_email(message)
        build_stub(data, args.out)


def _handle_repro_log_correction(args: argparse.Namespace) -> None:
    from src.repro.ledger import CorrectionLedger

    description = args.description
    if args.file:
        description = Path(args.file).read_text(encoding="utf-8").strip()
    if not description:
        raise SystemExit("Description is required")
    author = args.author or os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    ledger = CorrectionLedger()
    entry = ledger.append(description=description, author=author)
    _print_json(asdict(entry))


def _handle_repro_list(args: argparse.Namespace) -> None:
    from src.repro.ledger import CorrectionLedger

    ledger = CorrectionLedger()
    entries = [asdict(entry) for entry in ledger.list_entries()]
    _print_json(entries)


def _handle_repro_adversarial(args: argparse.Namespace) -> None:
    from src.repro.adversarial import build_bundle

    output_dir = _require_path(args.output, "--output")
    bundle = build_bundle(args.topic, output_dir)
    _print_json({"html": str(bundle["html"]), "pdf": str(bundle["pdf"])})


def _handle_search(args: argparse.Namespace) -> None:
    from src.storage import TextIndex

    index = TextIndex(args.db)
    try:
        results = index.search(args.query)
        _print_json(results)
    finally:
        index.close()


def _handle_proof_tree(args: argparse.Namespace) -> None:
    from datetime import date as date_cls

    from src.graph.proof_tree import expand_proof_tree

    data = _load_graph_data(args.graph, flag="--graph")
    graph = LegalGraph()
    for node in data.get("nodes", []):
        identifier = node.get("id") or node.get("identifier")
        if identifier is None:
            continue
        metadata = {
            k: v
            for k, v in node.items()
            if k not in {"id", "identifier", "type", "date", "metadata"}
        }
        if isinstance(node.get("metadata"), dict):
            metadata.update(node["metadata"])
        node_date = node.get("date")
        parsed_date = date_cls.fromisoformat(node_date) if node_date else None
        graph.add_node(
            GraphNode(
                type=NodeType(node.get("type", "document")),
                identifier=identifier,
                metadata=metadata,
                date=parsed_date,
            )
        )
    for edge in data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source not in graph.nodes or target not in graph.nodes:
            continue
        edge_type = edge.get("type", "cites")
        metadata = {
            k: v
            for k, v in edge.items()
            if k not in {"source", "target", "type", "date", "weight", "metadata"}
        }
        if isinstance(edge.get("metadata"), dict):
            metadata.update(edge["metadata"])
        edge_date = edge.get("date")
        parsed_date = date_cls.fromisoformat(edge_date) if edge_date else None
        weight = float(edge.get("weight", 1.0))
        graph.add_edge(
            GraphEdge(
                type=EdgeType(edge_type),
                source=source,
                target=target,
                metadata=metadata,
                date=parsed_date,
                weight=weight,
            )
        )
    as_at = date_cls.fromisoformat(args.as_at) if args.as_at else date.today()
    tree = expand_proof_tree(args.seed, args.hops, as_at, graph=graph)
    if args.dot:
        dot = tree.to_dot().replace("ProofTree", "proof_tree", 1)
        print(dot)
    else:
        _print_json(tree.to_json())


def _handle_repro(args: argparse.Namespace) -> None:
    if args.repro_command == "log-correction":
        _handle_repro_log_correction(args)
    elif args.repro_command == "list-corrections":
        _handle_repro_list(args)
    elif args.repro_command == "adversarial":
        _handle_repro_adversarial(args)
    else:
        raise SystemExit("Unknown repro command")


def _handle_tools(args: argparse.Namespace) -> None:
    if args.tools_command == "claim-builder":
        _handle_tools_claim_builder(args)
    elif args.tools_command == "counter-brief":
        _handle_tools_counter_brief(args)
    else:
        raise SystemExit("Unknown tools command")


def _collect_terms(args: argparse.Namespace) -> list[str]:
    terms: list[str] = []
    single = getattr(args, "term", None)
    if single:
        terms.append(single)
    extra_terms = getattr(args, "terms", None) or []
    if extra_terms:
        terms.extend(extra_terms)
    file_arg = getattr(args, "file", None)
    if file_arg:
        path = Path(args.file)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        file_terms = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        terms.extend([term for term in file_terms if term])
    if not terms:
        raise SystemExit("At least one term is required")
    return terms


def _handle_ontology_lookup_batch(args: argparse.Namespace) -> None:
    from src.ontology.lookup import batch_lookup

    terms = _collect_terms(args)
    results = batch_lookup(
        terms,
        provider=getattr(args, "provider", None),
        db_path=getattr(args, "db", None),
    )
    _print_json([record.asdict() for record in results])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sensiblaw")
    sub = parser.add_subparsers(dest="command")
    receipts_cli.register(sub)

    publish = sub.add_parser("publish", help="Generate a static SensibLaw Mirror site")
    publish.add_argument("--seed", required=True)
    publish.add_argument("--out", type=Path, required=True)
    publish.add_argument("--pack", type=Path)
    publish.set_defaults(func=_handle_publish)

    eval_parser = sub.add_parser("eval", help="Evaluation utilities")
    eval_sub = eval_parser.add_subparsers(dest="eval_command")
    eval_goldset = eval_sub.add_parser("goldset", help="Evaluate extractor performance against the gold set")
    eval_goldset.add_argument("--threshold", type=float, default=0.9)
    eval_goldset.set_defaults(func=_handle_eval_goldset)

    get_parser = sub.add_parser("get", help="Retrieve a document by ID")
    get_parser.add_argument("--db", required=True)
    get_parser.add_argument("--id", required=True)
    get_parser.add_argument("--as-at")
    get_parser.set_defaults(func=_handle_get)

    view_parser = sub.add_parser("view", help="Retrieve a document by canonical ID")
    view_parser.add_argument("--db", required=True)
    view_parser.add_argument("--id", required=True)
    view_parser.set_defaults(func=_handle_view)

    extract_parser = sub.add_parser("extract", help="Extraction helpers")
    extract_parser.add_argument("--text", help="Text to extract rules from")
    extract_parser.set_defaults(func=_handle_extract, parser=extract_parser)
    extract_sub = extract_parser.add_subparsers(dest="extract_command")
    extract_sub.required = False
    extract_rules = extract_sub.add_parser("rules", help="Extract rules from text")
    extract_rules.add_argument("--text", required=True)
    extract_rules.set_defaults(func=_handle_extract_rules)
    extract_frl = extract_sub.add_parser("frl", help="Fetch Acts from the FRL API")
    extract_frl.add_argument("--data", type=Path)
    extract_frl.add_argument("--api-url", default="https://example.com")
    extract_frl.set_defaults(func=_handle_extract_frl)

    check_parser = sub.add_parser("check", help="Check rules for issues")
    check_parser.add_argument("--rules", required=True)
    check_parser.set_defaults(func=_handle_check)

    ontology = sub.add_parser("ontology", help="Ontology lookup and management")
    ontology_sub = ontology.add_subparsers(dest="ontology_command")
    lookup = ontology_sub.add_parser("lookup", help="Lookup ontology terms via HTTP")
    lookup.add_argument("--term", required=True)
    lookup.add_argument("--url", default="https://example.com/ontology")
    lookup.add_argument("--threshold", type=float, default=0.0)
    lookup.add_argument("--limit", type=int)
    lookup.set_defaults(func=_handle_ontology_lookup)
    upsert = ontology_sub.add_parser("upsert", help="Upsert ontology sources into SQLite")
    upsert.add_argument("--db", required=True)
    upsert.add_argument("--legal-system", required=True)
    upsert.add_argument("--category", required=True)
    upsert.add_argument("--citation", required=True)
    upsert.add_argument("--title")
    upsert.add_argument("--url")
    upsert.add_argument("--promulgation-date")
    upsert.add_argument("--summary")
    upsert.add_argument("--notes")
    upsert.set_defaults(func=_handle_ontology_upsert)

    pdf_fetch = sub.add_parser("pdf-fetch", help="Ingest a PDF and extract rules")
    pdf_fetch.add_argument("path", type=Path)
    pdf_fetch.add_argument("--output", type=Path)
    pdf_fetch.add_argument("--jurisdiction")
    pdf_fetch.add_argument("--citation")
    pdf_fetch.add_argument("--title")
    pdf_fetch.add_argument("--cultural-flags", nargs="*")
    pdf_fetch.add_argument("--db", type=Path)
    pdf_fetch.add_argument("--doc-id", type=int)
    pdf_fetch.add_argument(
        "--logic-tree-artifacts",
        type=Path,
        default=Path("artifacts"),
        help="Directory to persist logic tree JSON artifacts",
    )
    pdf_fetch.add_argument(
        "--logic-tree-sqlite",
        type=Path,
        default=Path("artifacts/logic_tree.sqlite"),
        help="SQLite path for logic tree projections",
    )
    pdf_fetch.add_argument(
        "--logic-tree-source-id",
        help="Override source_id used when persisting the logic tree",
    )
    pdf_fetch.add_argument(
        "--logic-tree-disable-fts",
        action="store_true",
        help="Disable FTS indexing when projecting logic tree tokens",
    )
    pdf_fetch.set_defaults(func=_handle_pdf_fetch)

    distinguish = sub.add_parser("distinguish", help="Compare a story against a case silhouette")
    distinguish.add_argument("--case")
    distinguish.add_argument("--story")
    distinguish.set_defaults(func=_handle_distinguish)

    concepts = sub.add_parser("concepts", help="Concept matching tools")
    concepts_sub = concepts.add_subparsers(dest="concepts_command")
    concepts_match = concepts_sub.add_parser("match", help="Match concepts in text")
    concepts_match.add_argument("text_arg", nargs="?")
    concepts_match.add_argument("--text")
    concepts_match.set_defaults(func=_handle_concepts_match, parser=concepts_match)

    query = sub.add_parser("query", help="Run a concept query or case lookup")
    query_sub = query.add_subparsers(dest="query_command")
    query_case = query_sub.add_parser("case", help="Look up a case by identifier")
    query_case.add_argument("--id", required=True)
    query_case.add_argument("--year", type=int, default=1992)
    query_case.set_defaults(func=_handle_query_case)
    query_concepts = query_sub.add_parser("concepts", help="Match concepts in free text")
    query_concepts.add_argument("--text")
    query_concepts.add_argument("--graph", type=Path)
    query_concepts.set_defaults(func=_handle_query_concepts)
    query_timeline = query_sub.add_parser("timeline", help="Build a timeline for a case")
    query_timeline.add_argument("--case", required=True)
    query_timeline.add_argument("--graph-file", type=Path, required=True)
    query_timeline.set_defaults(func=_handle_query_timeline)

    polis = sub.add_parser("polis", help="Pol.is ingestion utilities")
    polis_sub = polis.add_subparsers(dest="polis_command")
    polis_sub.required = True
    polis_import = polis_sub.add_parser("import", help="Import a Pol.is conversation")
    polis_import.add_argument("--conversation", required=True)
    polis_import.add_argument("--out", type=Path, required=True)
    polis_import.add_argument("--limit", type=int)
    polis_import.add_argument("--max-retries", type=int)
    polis_import.add_argument("--sleep-between-retries", type=float)
    polis_import.set_defaults(func=_handle_polis_import)

    graph = sub.add_parser("graph", help="Graph operations")
    graph_sub = graph.add_subparsers(dest="graph_command")
    subgraph = graph_sub.add_parser("subgraph", help="Extract subgraph")
    subgraph.add_argument("--node", action="append")
    subgraph.add_argument("--hops", type=int, default=1)
    subgraph.add_argument("--graph-file", type=Path)
    subgraph.add_argument("--limit", type=int, default=100)
    subgraph.add_argument("--offset", type=int, default=0)
    subgraph.add_argument("--dot", action="store_true")
    subgraph.set_defaults(func=_handle_graph_subgraph)
    graph_query = graph_sub.add_parser("query", help="Query a graph JSON file")
    graph_query.add_argument("--graph", type=Path, required=True)
    graph_query.add_argument("--type")
    graph_query.add_argument("--start")
    graph_query.add_argument("--depth", type=int, default=1)
    graph_query.set_defaults(func=_handle_graph_query)
    graph_export = graph_sub.add_parser("export", help="Export graph triples")
    graph_export.add_argument("--graph", type=Path, required=True)
    graph_export.add_argument(
        "--include-external-refs",
        action="store_true",
        help="Include owl:sameAs/skos:exactMatch triples for external references",
    )
    graph_export.set_defaults(func=_handle_graph_export)

    inference = graph_sub.add_parser("inference", help="Knowledge graph inference utilities")
    inference_sub = inference.add_subparsers(dest="inference_command")

    inference_train = inference_sub.add_parser("train", help="Train a link prediction model")
    inference_train.add_argument("--graph", type=Path, required=True, help="Graph JSON file")
    inference_train.add_argument(
        "--model",
        choices=["transe", "distmult", "complex", "rotate", "mure"],
        default="complex",
        help="Embedding model",
    )
    inference_train.add_argument("--epochs", type=int, default=50, help="Training epochs")
    inference_train.add_argument("--batch-size", type=int, default=256, help="Training batch size")
    inference_train.add_argument("--learning-rate", type=float, default=1e-3, help="Optimizer learning rate")
    inference_train.add_argument(
        "--embedding-dim", type=int, default=128, help="Embedding dimensionality"
    )
    inference_train.add_argument(
        "--relation",
        default=EdgeType.APPLIES.value,
        help="Relation label to score (default: applies)",
    )
    inference_train.add_argument("--case", action="append", help="Limit scoring to specific case ids")
    inference_train.add_argument(
        "--provision",
        action="append",
        help="Limit scoring to specific provision identifiers",
    )
    inference_train.add_argument("--top-k", type=int, help="Maximum recommendations per case")
    inference_train.add_argument("--random-seed", type=int, help="Deterministic seed for PyKEEN")
    inference_train.add_argument("--json-out", type=Path, help="Write predictions to a JSON file")
    inference_train.add_argument("--sqlite-out", type=Path, help="Write predictions to a SQLite database")
    inference_train.set_defaults(func=_handle_graph_inference_train)

    inference_rank = inference_sub.add_parser(
        "rank", help="Rank provisions for a case from persisted predictions"
    )
    inference_rank.add_argument("--case", required=True, help="Case identifier to rank against")
    inference_rank.add_argument("--top-k", type=int, help="Limit the number of rows returned")
    inference_rank.add_argument("--relation", default=EdgeType.APPLIES.value)
    inference_rank.add_argument("--json", type=Path, help="Prediction JSON file")
    inference_rank.add_argument("--sqlite", type=Path, help="Prediction SQLite database")
    inference_rank.set_defaults(func=_handle_graph_inference_rank)

    tests_parser = sub.add_parser("tests", help="Run declarative tests")
    tests_sub = tests_parser.add_subparsers(dest="tests_command")
    tests_run = tests_sub.add_parser("run", help="Run tests against a story")
    tests_run.add_argument("--ids", nargs="+")
    tests_run.add_argument("--tests", nargs="+")
    tests_run.add_argument("--story", type=Path)
    tests_run.add_argument("--template", type=Path)
    tests_run.add_argument("--facts", type=Path)
    tests_run.set_defaults(func=_handle_tests_run)

    cases = sub.add_parser("cases", help="Case operations")
    cases_sub = cases.add_subparsers(dest="cases_command")
    cases_treat = cases_sub.add_parser("treatment", help="Fetch case treatment")
    cases_treat.add_argument("--case-id", required=True)
    cases_treat.set_defaults(func=_handle_cases_treatment)

    harm = sub.add_parser("harm", help="Harm index utilities")
    harm_sub = harm.add_subparsers(dest="harm_command")
    harm_compute = harm_sub.add_parser("compute", help="Compute harm index scores")
    harm_compute.add_argument("--story", type=Path, required=True)
    harm_compute.add_argument("--out", type=Path)
    harm_compute.set_defaults(func=_handle_harm_compute)

    treatment = sub.add_parser("treatment", help="List sample treatment edges")
    treatment.add_argument("--doc", required=True)
    treatment.add_argument("--limit", type=int)
    treatment.add_argument("--offset", type=int)
    treatment.set_defaults(func=_handle_treatment)

    provision = sub.add_parser("provision", help="Fetch a provision by identifier")
    provision.add_argument("--doc", required=True)
    provision.add_argument("--id", required=True)
    provision.set_defaults(func=_handle_provision)

    ontology_lookup = sub.add_parser("ontology-lookup", help="Lookup ontology terms in batch")
    ontology_lookup.add_argument("terms", nargs="*", help="Terms to lookup")
    ontology_lookup.add_argument("--file", type=Path, help="Optional file containing newline-delimited terms")
    ontology_lookup.add_argument("--provider", default="glossary", help="Lookup provider label")
    ontology_lookup.add_argument("--db", type=Path, help="Optional SQLite database to log lookups")
    ontology_lookup.set_defaults(func=_handle_ontology_lookup_batch)

    austlii = sub.add_parser("austlii-fetch", help="Fetch legislation from AustLII")
    austlii.add_argument("--db", type=Path, required=True)
    austlii.add_argument("--act", required=True)
    austlii.add_argument("--sections", default="")
    austlii.set_defaults(func=_handle_austlii_fetch)

    tools = sub.add_parser("tools", help="Miscellaneous tools")
    tools_sub = tools.add_subparsers(dest="tools_command")
    claim_builder = tools_sub.add_parser("claim-builder", help="Interactive claim builder")
    claim_builder.add_argument("--dir", type=Path)
    claim_builder.set_defaults(func=_handle_tools)
    counter_brief = tools_sub.add_parser("counter-brief", help="Generate a counter brief")
    counter_brief.add_argument("--file", type=Path, required=True)
    counter_brief.add_argument("--output-dir", type=Path)
    counter_brief.set_defaults(func=_handle_tools)

    intake = sub.add_parser("intake", help="Intake utilities")
    intake_sub = intake.add_subparsers(dest="intake_command")
    intake_parse = intake_sub.add_parser("parse", help="Parse intake mailbox into stubs")
    intake_parse.add_argument("--mailbox", required=True)
    intake_parse.add_argument("--out", type=Path, required=True)
    intake_parse.set_defaults(func=_handle_intake_parse)

    repro = sub.add_parser("repro", help="Reproducibility helpers")
    repro_sub = repro.add_subparsers(dest="repro_command")
    repro_log = repro_sub.add_parser("log-correction", help="Log a correction")
    repro_log.add_argument("--file", type=Path)
    repro_log.add_argument("--description")
    repro_log.add_argument("--author")
    repro_log.set_defaults(func=_handle_repro)
    repro_list = repro_sub.add_parser("list-corrections", help="List logged corrections")
    repro_list.set_defaults(func=_handle_repro)
    repro_adv = repro_sub.add_parser("adversarial", help="Build adversarial bundle")
    repro_adv.add_argument("--topic", required=True)
    repro_adv.add_argument("--output", type=Path, required=True)
    repro_adv.set_defaults(func=_handle_repro)

    search = sub.add_parser("search", help="Search the text index")
    search.add_argument("query")
    search.add_argument("--db", required=True)
    search.set_defaults(func=_handle_search)

    proof_tree = sub.add_parser("proof-tree", help="Expand a proof tree from a graph")
    proof_tree.add_argument("--graph", type=Path, required=True)
    proof_tree.add_argument("--seed", required=True)
    proof_tree.add_argument("--hops", type=int, default=1)
    proof_tree.add_argument("--as-at")
    proof_tree.add_argument("--dot", action="store_true")
    proof_tree.set_defaults(func=_handle_proof_tree)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
