from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence


def _print_json(data: object) -> None:
    """Serialise ``data`` to JSON and print it to stdout."""

    print(json.dumps(data, ensure_ascii=False))


def _load_graph_data(path: Path | str | None) -> dict:
    if path is None:
        raise ValueError("graph path is required")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
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


def _handle_extract_frl(args: argparse.Namespace) -> None:
    from src.ingestion.frl import fetch_acts

    payload = json.loads(args.data.read_text()) if args.data else None
    nodes, edges = fetch_acts(args.api_url, data=payload)
    _print_json({"nodes": nodes, "edges": edges})


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
    result = {"document": doc.to_dict()}
    if stored_id is not None:
        result["doc_id"] = stored_id
    _print_json(result)


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


def _handle_graph_subgraph(args: argparse.Namespace) -> None:
    if args.graph_file:
        if str(args.graph_file) == "-":
            data = json.load(sys.stdin)
        else:
            data = _load_graph_data(args.graph_file)
        subgraph = _subgraph_from_data(data, args.node or [], args.hops)
        if args.dot:
            print(_subgraph_to_dot(subgraph, id_key="id"))
        else:
            _print_json(subgraph)
        return

    from src import sample_data

    subgraph = sample_data.build_subgraph(args.node, args.limit, args.offset)
    if args.dot:
        print(sample_data.subgraph_to_dot(subgraph))
    else:
        _print_json(subgraph)


def _handle_graph_query(args: argparse.Namespace) -> None:
    data = _load_graph_data(args.graph)
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

    from src.graph.models import EdgeType, GraphEdge, GraphNode, LegalGraph, NodeType
    from src.graph.proof_tree import expand_proof_tree

    data = _load_graph_data(args.graph)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sensiblaw")
    sub = parser.add_subparsers(dest="command")

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
    extract_sub = extract_parser.add_subparsers(dest="extract_command")
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

    pdf_fetch = sub.add_parser("pdf-fetch", help="Ingest a PDF and extract rules")
    pdf_fetch.add_argument("path", type=Path)
    pdf_fetch.add_argument("--output", type=Path)
    pdf_fetch.add_argument("--jurisdiction")
    pdf_fetch.add_argument("--citation")
    pdf_fetch.add_argument("--title")
    pdf_fetch.add_argument("--cultural-flags", nargs="*")
    pdf_fetch.add_argument("--db", type=Path)
    pdf_fetch.add_argument("--doc-id", type=int)
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
    concepts_match.set_defaults(func=_handle_concepts)

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
