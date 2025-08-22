import argparse
import json
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path

"""Backward compatible wrapper for the new :mod:`cli` package."""

from __future__ import annotations

from .storage import VersionedStore
from .proofs.render import dot_to_svg

from cli import main

__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - for direct execution

def _cmd_tests_run(args: argparse.Namespace) -> None:
    """Evaluate a story against a checklist template and print results."""

    from .tests.evaluator import evaluate

    evaluation = evaluate(
        concept_id=args.concept,
        story_path=args.story,
        templates_path=args.templates,
    )

    template = evaluation.template
    print(f"Test: {template.name} ({template.concept_id})")
    header = f"{'Factor':20} {'Status':10} Evidence"
    print(header)
    print("-" * len(header))
    for res in evaluation.results:
        evidence = "; ".join(res.evidence)
        print(f"{res.factor.id:20} {res.status:10} {evidence}")


# graph query utilities
from .graph.query import (
    load_graph,
    search_by_citation,
    search_by_tag,
    search_by_type,
    traverse_edges,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="sensiblaw")
    sub = parser.add_subparsers(dest="command")

    extract_parser = sub.add_parser("extract", help="Extraction helpers")
    extract_parser.add_argument("--text", help="Provision text")
    extract_sub = extract_parser.add_subparsers(dest="extract_command")

    extract_text = extract_sub.add_parser("rules", help="Extract rules from text")
    extract_text.add_argument("--text", required=True, help="Provision text")

    extract_parser = sub.add_parser("extract", help="Extraction operations")
    extract_parser.add_argument("--text", help="Provision text")
    extract_sub = extract_parser.add_subparsers(dest="extract_command")

    extract_rules_parser = extract_sub.add_parser(
        "rules", help="Extract rules from text"
    )
    extract_rules_parser.add_argument("--text", required=True, help="Provision text")

    extract_frl_parser = extract_sub.add_parser(
        "frl", help="Fetch Acts from the Federal Register of Legislation"
    )
    extract_frl_parser.add_argument("--act", required=True, help="Act identifier")
    extract_frl_parser.add_argument(
        "--out", type=Path, required=True, help="Output JSON path"
    )
    extract_frl = extract_sub.add_parser("frl", help="Fetch Acts from the FRL API")
    extract_frl.add_argument("--data", type=Path, help="Path to JSON payload for tests")
    extract_frl.add_argument("--api-url", default="https://example.com", help="FRL API base URL")

    check_parser = sub.add_parser("check", help="Check rules for issues")
    check_parser.add_argument("--rules", required=True, help="JSON encoded rules")

    fetch_parser = sub.add_parser(
        "pdf-fetch", help="Ingest a PDF and extract rules"
    )
    fetch_parser.add_argument("path", type=Path, help="Path to PDF file")
    fetch_parser.add_argument("--output", type=Path, help="Output JSON path")
    fetch_parser.add_argument("--jurisdiction", help="Jurisdiction metadata")
    fetch_parser.add_argument("--citation", help="Citation metadata")
    fetch_parser.add_argument(
        "--cultural-flags", nargs="*", help="List of cultural sensitivity flags"
    )

    graph_parser = sub.add_parser("graph", help="Graph utilities")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")

    graph_query = graph_sub.add_parser("query", help="Query a graph JSON file")
    graph_query.add_argument(
        "--graph", dest="graph_path", required=True, help="Path to graph JSON"
    )
    group = graph_query.add_mutually_exclusive_group()
    group.add_argument("--type", dest="node_type", help="Filter nodes by type")
    group.add_argument("--citation", help="Filter nodes by citation")
    group.add_argument("--tag", help="Filter nodes by tag")
    graph_query.add_argument("--start", help="Start node for traversal")
    graph_query.add_argument(
        "--depth", type=int, default=1, help="Traversal depth from start node"
    )
    graph_query.add_argument(
        "--since", help="Only include edges on or after this date (YYYY-MM-DD)"
    )
    graph_query.add_argument(
        "--min-weight", type=float, help="Only include edges with weight >= value"
    )
    law_parser = sub.add_parser("law", help="Law document utilities")
    law_sub = law_parser.add_subparsers(dest="law_command")
    law_redline = law_sub.add_parser(
        "redline", help="Generate HTML diff between two statute versions"
    )
    law_redline.add_argument("--old", type=Path, required=True, help="Path to old version")
    law_redline.add_argument("--new", type=Path, required=True, help="Path to new version")
    law_redline.add_argument("--out", type=Path, required=True, help="Output HTML file")

    dist_parser = sub.add_parser(
        "distinguish", help="Compare a story against a case silhouette"
    )
    dist_parser.add_argument(
        "--base", type=Path, help="Base case paragraphs as JSON"

        "--case",
        required=True,
        help="Neutral citation identifying the base case",
    )
    dist_parser.add_argument(
        "--story",
        type=Path,
        help="Candidate case paragraphs as JSON",

        required=True,
        help="Path to a fact-tagged story JSON file",
    )
    dist_parser.add_argument("--case", help="Base case citation")
    dist_parser.add_argument("--story", type=Path, help="Story facts as JSON")

    publish_parser = sub.add_parser("publish", help="Generate a static site")
    publish_parser.add_argument("--seed", required=True, help="Seed node identifier")
    publish_parser.add_argument(
        "--out", type=Path, required=True, help="Directory to write the site"
    )

    concepts_parser = sub.add_parser("concepts", help="Concept operations")
    concepts_sub = concepts_parser.add_subparsers(dest="concepts_command")
    concepts_match = concepts_sub.add_parser(
        "match", help="Match concept triggers within text"
    )
    concepts_match.add_argument(
        "--patterns-file",
        type=Path,
        required=True,
        help="JSON file mapping phrases to concept identifiers",
    )
    concepts_match.add_argument("--text", required=True, help="Text to match")

    query_parser = sub.add_parser(
        "query", help="Run concept or case queries"
    )
    query_sub = query_parser.add_subparsers(dest="query_command")
    treat_parser = query_sub.add_parser(
        "treatment", help="Fetch treatment information for a case"
    )

    )
    query_sub = query_parser.add_subparsers(dest="query_command")
    treat_parser = query_sub.add_parser(
        "treatment", help="Fetch treatment information for a case"
    )
    treat_parser.add_argument("--case", required=True, help="Case identifier")

    group = query_parser.add_mutually_exclusive_group()
    group.add_argument("--text", help="Question or keyword query")
    group.add_argument(

        "query", help="Run concept queries or case lookups"
    )
    query_parser.add_argument("--text", help="Question or keyword query")
    query_parser.add_argument(
        "--graph",
        type=Path,
        help="Path to a StoryGraph JSON file representing the query",
    )
    query_sub = query_parser.add_subparsers(dest="query_command")
    case_q = query_sub.add_parser("case", help="Look up a case by identifier")
    case_q.add_argument("--id", required=True, help="Case identifier")
    case_q.add_argument("--year", type=int, default=1992, help="Year of judgment")
    treat_q = query_sub.add_parser("treatment", help="Fetch treatment for a case")
    treat_q.add_argument(
        "--case", required=True, help="Neutral citation identifying the case"
    )

    timeline_q = query_sub.add_parser("timeline", help="Generate timeline for a case")
    timeline_q.add_argument("--case", required=True, help="Case identifier")
    timeline_q.add_argument(
        "--graph-file",
        type=Path,
        help="Graph JSON file (use '-' for stdin)",
    )
    timeline_q.add_argument(
        "--svg",
        action="store_true",
        help="Output SVG instead of JSON",
    )

    graph_parser = sub.add_parser("graph", help="Graph operations")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    subgraph_parser = graph_sub.add_parser("subgraph", help="Extract subgraph")
    subgraph_parser.add_argument(
        "--seeds",
        nargs="+",
        required=True,
        help="Seed node identifiers",
    )
    subgraph_parser.add_argument(
        "--hops", type=int, default=1, help="Number of hops"
    )
    subgraph_parser.add_argument(
        "--as-at",
        help="Only include nodes/edges on or before this date (YYYY-MM-DD)",
    )
    subgraph_parser.add_argument(
        "--graph-file",
        type=Path,
        help="Graph JSON file (use '-' for stdin)",
    )
    subgraph_parser.add_argument(
        "--dot",
        action="store_true",
        help="Output Graphviz DOT instead of JSON",
    )

    subgraph_parser.add_argument(
        "--svg",
        action="store_true",
        help="Output rendered SVG",
    )

    eval_parser = sub.add_parser("eval", help="Evaluation helpers")
    eval_sub = eval_parser.add_subparsers(dest="eval_command")
    gold_eval = eval_sub.add_parser(
        "goldset", help="Evaluate extractors against gold sets"
    )
    gold_eval.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="Minimum acceptable precision/recall",
    )

    tests_parser = sub.add_parser("tests", help="Run declarative tests")
    tests_sub = tests_parser.add_subparsers(dest="tests_command")
    tests_run = tests_sub.add_parser("run", help="Run checklist tests against a story")
    tests_run.add_argument(
        "--tests-file", type=Path, required=True, help="Checklist JSON file"
    )
    tests_run.add_argument(
        "--story-file", type=Path, required=True, help="Story JSON file"
    )

    definitions_parser = sub.add_parser("definitions", help="Definition operations")
    definitions_sub = definitions_parser.add_subparsers(dest="definitions_command")
    definitions_expand = definitions_sub.add_parser("expand", help="Expand term definitions")
    definitions_expand.add_argument("--term", required=True, help="Term identifier")
    definitions_expand.add_argument("--depth", type=int, default=1, help="Expansion depth")


    harm_parser = sub.add_parser("harm", help="Harm assessment utilities")
    harm_sub = harm_parser.add_subparsers(dest="harm_command")
    harm_compute = harm_sub.add_parser("compute", help="Compute harm index")
    harm_compute.add_argument(
        "--story", type=Path, required=True, help="Path to story JSON file"
    )

    cases_parser = sub.add_parser("cases", help="Case operations")
    cases_sub = cases_parser.add_subparsers(dest="cases_command")
    cases_treat = cases_sub.add_parser("treatment", help="Fetch case treatment")
    cases_treat.add_argument("--case-id", required=True, help="Case identifier")

    repro_parser = sub.add_parser("repro", help="Generate reproducibility bundles")
    repro_sub = repro_parser.add_subparsers(dest="repro_command")
    adv_parser = repro_sub.add_parser(
        "adversarial", help="Compile adversarial counter-arguments"
    )
    adv_parser.add_argument("--topic", required=True, help="Topic identifier")
    adv_parser.add_argument(
        "--output", type=Path, default=Path("output"), help="Output directory"

    tools_parser = sub.add_parser("tools", help="Utility helper commands")
    tools_sub = tools_parser.add_subparsers(dest="tools_command")
    counter_brief = tools_sub.add_parser(
        "counter-brief", help="Generate a structured counter brief"
    )
    counter_brief.add_argument(
        "--file", type=Path, required=True, help="Path to the input brief"

    repro_parser = sub.add_parser("repro", help="Reproducibility helpers")
    repro_sub = repro_parser.add_subparsers(dest="repro_command")
    repro_log = repro_sub.add_parser("log-correction", help="Log a correction entry")
    repro_log.add_argument(
        "--file", type=Path, required=True, help="Path to correction description file"
    )
    repro_sub.add_parser("list-corrections", help="List logged corrections")

    receipts_parser = sub.add_parser("receipts", help="Receipt operations")
    receipts_sub = receipts_parser.add_subparsers(dest="receipts_command")
    receipts_diff = receipts_sub.add_parser(
        "diff", help="Compare two receipt files"
    )
    receipts_diff.add_argument("--old", type=Path, required=True, help="Old receipt")
    receipts_diff.add_argument("--new", type=Path, required=True, help="New receipt")
    polis_parser = sub.add_parser("polis", help="Pol.is conversation operations")
    polis_sub = polis_parser.add_subparsers(dest="polis_command")
    polis_import = polis_sub.add_parser("import", help="Import conversation as concepts")
    polis_import.add_argument("--conversation", required=True, help="Conversation ID")
    polis_import.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Directory to write proof packs",
    )

    tools_parser = sub.add_parser("tools", help="Utility tools")
    tools_sub = tools_parser.add_subparsers(dest="tools_command")
    claim_builder = tools_sub.add_parser(
        "claim-builder", help="Interactively build a claim"
    )
    claim_builder.add_argument(
        "--dir",
        type=Path,
        default=Path("data/claims"),
        help="Directory to save claim files",
    )

    intake_parser = sub.add_parser("intake", help="Email intake operations")
    intake_sub = intake_parser.add_subparsers(dest="intake_command")
    intake_parse = intake_sub.add_parser(
        "parse", help="Parse an email mailbox into claim stubs"
    )
    intake_parse.add_argument(
        "--mailbox",
        required=True,
        help="IMAP URL or directory containing .eml files",
    )
    intake_parse.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Directory for generated claim stubs",
    )

    tests_parser = sub.add_parser("tests", help="Evaluate declarative tests")
    tests_sub = tests_parser.add_subparsers(dest="tests_command")
    tests_run = tests_sub.add_parser("run", help="Run a test template against a story")
    tests_run.add_argument("--tests", required=True, help="Test template ID")
    tests_run.add_argument(
        "--story", type=Path, required=True, help="Path to story JSON file"
    )

    tests_parser = sub.add_parser(
        "tests", help="Run declarative concept checklists"
    )
    tests_sub = tests_parser.add_subparsers(dest="tests_command")
    run_parser = tests_sub.add_parser("run", help="Evaluate a story against a checklist")
    run_parser.add_argument("--templates", type=Path, required=True, help="Path to templates JSON")
    run_parser.add_argument("--story", type=Path, required=True, help="Path to story JSON")
    run_parser.add_argument("--concept", required=True, help="Concept ID to evaluate")

    concepts_parser = sub.add_parser("concepts", help="Concept utilities")
    concepts_sub = concepts_parser.add_subparsers(dest="concepts_command")
    match_parser = concepts_sub.add_parser("match", help="Match concepts in text")
    match_parser.add_argument("text", help="Text to analyse")

    search_parser = sub.add_parser(
        "search", help="Full text search over indexed graph nodes"
    )
    search_parser.add_argument("query", help="Search expression")
    search_parser.add_argument(
        "--db", default="data/search.db", help="Path to search index"
    )

    subgraph_parser = sub.add_parser(
        "subgraph", help="Generate a concept cloud subgraph from text"
    )
    subgraph_parser.add_argument("--text", required=True, help="Query text")
    subgraph_parser.add_argument(
        "--dot", type=Path, help="Optional path to write Graphviz DOT output"
    )

    treatment_parser = sub.add_parser(
        "treatment", help="Extract rules from provision text"
    )
    treatment_parser.add_argument("--text", required=True, help="Provision text")
    treatment_parser.add_argument(
        "--dot", type=Path, help="Optional path to write Graphviz DOT output"
    )

    provision_parser = sub.add_parser(
        "provision", help="Tag a provision of law"
    )
    provision_parser.add_argument("--text", required=True, help="Provision text")
    provision_parser.add_argument(
        "--dot", type=Path, help="Optional path to write Graphviz DOT output"
    )

    tests_parser = sub.add_parser("tests-run", help="Run the test suite")
    tests_parser.add_argument(
        "--dot", type=Path, help="Optional path to write Graphviz DOT output"
    )

    tree_parser = sub.add_parser(
        "proof-tree", help="Expand a proof tree from a seed node",
    )
    tree_parser.add_argument("--graph", type=Path, required=True, help="Graph JSON file")
    tree_parser.add_argument("--seed", required=True, help="Seed node identifier")
    tree_parser.add_argument("--hops", type=int, default=1, help="Traversal depth")
    tree_parser.add_argument(
        "--as-at", help="Consider only nodes/edges up to this date (YYYY-MM-DD)",
    )
    tree_parser.add_argument(
        "--dot", action="store_true", help="Output Graphviz DOT instead of JSON",
    )

    tree_parser = sub.add_parser(
        "proof-tree", help="Expand a proof tree from a seed node",
    )
    tree_parser.add_argument("--graph", type=Path, required=True, help="Graph JSON file")
    tree_parser.add_argument("--seed", required=True, help="Seed node identifier")
    tree_parser.add_argument("--hops", type=int, default=1, help="Traversal depth")
    tree_parser.add_argument(
        "--as-at", help="Consider only nodes/edges up to this date (YYYY-MM-DD)",
    )
    tree_parser.add_argument(
        "--dot", action="store_true", help="Output Graphviz DOT instead of JSON",
    )

    # Graph and provisioning commands
    graph_parser = sub.add_parser("graph", help="Graph operations")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    sg_parser = graph_sub.add_parser("subgraph", help="Retrieve subgraph")
    sg_parser.add_argument("--node", action="append", help="Node identifier", default=[])
    sg_parser.add_argument("--limit", type=int, default=50)
    sg_parser.add_argument("--offset", type=int, default=0)
    sg_parser.add_argument("--dot", action="store_true", help="Output DOT format")

    treatment_parser = sub.add_parser("treatment", help="Show treatments for a document")
    treatment_parser.add_argument("--doc", required=True, help="Document identifier")
    treatment_parser.add_argument("--limit", type=int, default=50)
    treatment_parser.add_argument("--offset", type=int, default=0)
    treatment_parser.add_argument("--dot", action="store_true", help="Output DOT format")

    provision_parser = sub.add_parser("provision", help="Retrieve a provision")
    provision_parser.add_argument("--doc", required=True, help="Document identifier")
    provision_parser.add_argument("--id", required=True, help="Provision identifier")

    # Tests evaluation command
    tests_parser = sub.add_parser(
        "tests", help="Evaluate legal test templates against facts"
    )
    tests_sub = tests_parser.add_subparsers(dest="tests_command")
    tests_run = tests_sub.add_parser(
        "run", help="Evaluate a test template with provided facts"
    )
    tests_run.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Path to JSON template describing factors",
    )
    tests_run.add_argument(
        "--facts",
        type=Path,
        required=True,
        help="Path to JSON file mapping factors to evidence references",
    )

    concepts_parser = sub.add_parser(
        "concepts", help="Concept matching utilities",
    )
    concepts_sub = concepts_parser.add_subparsers(dest="concepts_command")
    match_parser = concepts_sub.add_parser(
        "match", help="Match concepts in text",
    )
    match_parser.add_argument("--text", required=True, help="Text to match")

    args = parser.parse_args()
    if args.command == "get":
        store = VersionedStore(args.db)
        if args.as_at:
            as_at = datetime.fromisoformat(args.as_at).date()
        else:
            as_at = date.today()
        doc = store.snapshot(args.id, as_at)
        if doc is None:
            print("Not found")
        else:
            print(doc.to_json())
        store.close()
    elif args.command == "extract":
        if args.extract_command == "rules" or (
            args.extract_command is None and args.text
        ):
        if args.extract_command == "rules" or (args.extract_command is None and args.text):
            from .rules.extractor import extract_rules

            rules = extract_rules(args.text)
            print(json.dumps([r.__dict__ for r in rules]))
        elif args.extract_command == "frl":
            from .ingestion.frl import fetch_acts

            api_url = "https://www.legislation.gov.au/federalregister/json/Acts"
            api_url += f"?searchWithin={args.act}"
            nodes, edges = fetch_acts(api_url)
            args.out.write_text(json.dumps({"nodes": nodes, "edges": edges}))
            payload = json.loads(args.data.read_text()) if args.data else None
            nodes, edges = fetch_acts(args.api_url, data=payload)
            print(json.dumps({"nodes": nodes, "edges": edges}))
        else:
            parser.print_help()
    elif args.command == "check":
        from .rules import Rule
        from .rules.reasoner import check_rules

        data = json.loads(args.rules)
        rules = [Rule(**r) for r in data]
        issues = check_rules(rules)
        print(json.dumps(issues))
    elif args.command == "pdf-fetch":
        from .pdf_ingest import process_pdf

        doc = process_pdf(
            args.path,
            output=args.output,
            jurisdiction=args.jurisdiction,
            citation=args.citation,
            cultural_flags=args.cultural_flags,
        )
        print(doc.to_json())
    elif args.command == "graph" and args.graph_command == "query":
        graph_data = load_graph(args.graph_path)
        if args.start:
            since = (
                datetime.fromisoformat(args.since).date() if args.since else None
            )
            result = traverse_edges(
                graph_data,
                args.start,
                depth=args.depth,
                since=since,
                min_weight=args.min_weight,
            )
        else:
            if args.node_type:
                nodes = search_by_type(graph_data, args.node_type)
            elif args.citation:
                nodes = search_by_citation(graph_data, args.citation)
            elif args.tag:
                nodes = search_by_tag(graph_data, args.tag)
            else:
                nodes = []
            result = {"nodes": nodes, "edges": []}
        print(json.dumps(result))

    elif args.command == "law":
        if args.law_command == "redline":
            from .versioning.section_diff import redline

            old_text = args.old.read_text()
            new_text = args.new.read_text()
            html = redline(old_text, new_text, old_ref=str(args.old), new_ref=str(args.new))
            args.out.write_text(html)
        else:
            parser.print_help()
    elif args.command == "distinguish":
        from .distinguish.engine import (
            compare_cases,
            extract_case_silhouette,
        )
        from .distinguish.factor_packs import distinguish_story

        if args.base and args.candidate:
            base_paras = json.loads(args.base.read_text())
            cand_paras = json.loads(args.candidate.read_text())
            base = extract_case_silhouette(base_paras)
            cand = extract_case_silhouette(cand_paras)
            result = compare_cases(base, cand)
            print(json.dumps(result))
        elif args.case and args.story:
            try:
                result = distinguish_story(args.case, args.story)
            except FileNotFoundError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                raise SystemExit(1)
            print(json.dumps(result))
        else:
            print(
                "distinguish requires --base and --candidate or --case and --story",
                file=sys.stderr,
            )
            raise SystemExit(1)

        from .distinguish.loader import load_case_silhouette
        from .distinguish.engine import compare_story_to_case

        case_sil = load_case_silhouette(args.case)
        story_data = json.loads(args.story.read_text())
        story_tags = story_data.get("facts", {})
        result = compare_story_to_case(story_tags, case_sil)
        # Pretty-print to expose paragraph anchors in output
        print(json.dumps(result, indent=2))

        print(json.dumps(result))
    elif args.command == "proof-tree":
        from .graph import (
            EdgeType,
            GraphEdge,
            GraphNode,
            LegalGraph,
            NodeType,
            expand_proof_tree,
        )

        graph_data = json.loads(args.graph.read_text())
        graph = LegalGraph()
        for n in graph_data.get("nodes", []):
            node = GraphNode(
                type=NodeType(n["type"]),
                identifier=n["id"],
                metadata=n.get("metadata", {}),
                date=date.fromisoformat(n["date"]) if n.get("date") else None,
            )
            graph.add_node(node)
        for e in graph_data.get("edges", []):
            edge = GraphEdge(
                type=EdgeType(e["type"]),
                source=e["source"],
                target=e["target"],
                metadata=e.get("metadata", {}),
                date=date.fromisoformat(e["date"]) if e.get("date") else None,
                weight=e.get("weight", 1.0),
            )
            graph.add_edge(edge)

        if args.as_at:
            as_at = datetime.fromisoformat(args.as_at).date()
        else:
            as_at = date.today()
        tree = expand_proof_tree(args.seed, args.hops, as_at, graph=graph)
        if args.dot:
            print(tree.to_dot())
        else:
            print(json.dumps(tree.to_dict()))

    elif args.command == "concepts":
        if args.concepts_command == "match":
            from .concepts.matcher import ConceptMatcher, load_patterns

            patterns = load_patterns(args.patterns_file)
            matcher = ConceptMatcher(patterns)
            hits = matcher.match(args.text)
            nodes = [
                {"id": cid, "start": span[0], "end": span[1]} for cid, span in hits
            ]
            print(json.dumps(nodes))
        else:
            parser.print_help()

    elif args.command == "polis":
        if args.polis_command == "import":
            from .ingest.polis import fetch_conversation
            from .receipts import build_pack

            seeds = fetch_conversation(args.conversation)
            args.out.mkdir(parents=True, exist_ok=True)
            for seed in seeds:
                pack_dir = args.out / seed["id"]
                build_pack(pack_dir, seed.get("label", ""))
        else:
            parser.print_help()
    elif args.command == "query":
        if args.query_command == "treatment":


        if args.query_command == "case":
            from .api import routes
            from .graph.models import EdgeType, GraphEdge, GraphNode, NodeType
            from .ingestion import hca

            nodes, edges = hca.crawl_year(args.year)
            for n in nodes:
                meta = {k: v for k, v in n.items() if k not in {"id", "type"}}
                routes._graph.add_node(
                    GraphNode(type=NodeType.DOCUMENT, identifier=n["id"], metadata=meta)
                )
            for e in edges:
                routes._graph.add_edge(
                    GraphEdge(type=EdgeType.CITES, source=e["from"], target=e["to"])
                )
            case = next((n for n in nodes if n["id"] == args.id), None)
            if case is None:
                print("{}")
            else:
                cites = [e["to"] for e in edges if e["from"] == args.id]
                result = {
                    "catchwords": case.get("catchwords", []),
                    "citations": cites,
                }
                print(json.dumps(result))
        elif args.query_command == "treatment":
            from .api.routes import fetch_case_treatment

            result = fetch_case_treatment(args.case)
            print(json.dumps(result))
        else:
            if not (args.text or args.graph):
                parser.error("query requires --text or --graph")



        elif args.query_command == "timeline":
            from dataclasses import asdict
            from .reason.timeline import build_timeline, events_to_json, events_to_svg

            if args.graph_file:
                import sys

                if str(args.graph_file) == "-":
                    data = json.load(sys.stdin)
                else:
                    data = json.loads(args.graph_file.read_text())
                nodes = data.get("nodes", [])
                edges = data.get("edges", [])
            else:
                from .api import routes

                nodes = [asdict(n) for n in routes._graph.nodes.values()]
                edges = [asdict(e) for e in routes._graph.edges]

            events = build_timeline(nodes, edges, args.case)
            if args.svg:
                print(events_to_svg(events))
            else:
                print(events_to_json(events))
        else:
            from .pipeline import build_cloud, match_concepts, normalise
            from .pipeline.input_handler import parse_input

            if args.graph:
                data = json.loads(args.graph.read_text())
                raw_query = parse_input(data)
            else:
                raw_query = parse_input(args.text)

            text = normalise(raw_query)
            concepts = match_concepts(text)
            cloud = build_cloud(concepts)
            print(json.dumps({"cloud": cloud}))
    elif args.command == "graph":
        if args.graph_command == "subgraph":
            from .graph.proof_tree import Graph, Node, Edge, build_subgraph, to_dot

            as_at = datetime.fromisoformat(args.as_at) if args.as_at else None

            if args.graph_file:
                import os
                import sys
                import os
                from .graph.proof_tree import Graph, Node, Edge, build_subgraph, to_dot


                if str(args.graph_file) == "-":
                    data = json.load(sys.stdin)
                else:
                    mode = os.stat(args.graph_file).st_mode & 0o777
                    if mode == 0:
                        print("--graph-file unreadable", file=sys.stderr)
                        sys.exit(1)

                    if (args.graph_file.stat().st_mode & 0o444) == 0:
                        import sys as _sys

                        print("--graph-file is unreadable", file=_sys.stderr)
                        raise SystemExit(1)

                    mode = args.graph_file.stat().st_mode & 0o444
                    if mode == 0:
                        print("--graph-file is not readable", file=sys.stderr)
                        sys.exit(1)

                    mode = args.graph_file.stat().st_mode
                    if mode & 0o444 == 0:
                        print(
                            f"error: argument --graph-file: can't open '{args.graph_file}': Permission denied",
                            file=sys.stderr,
                        )
                        sys.exit(2)
                    data = json.loads(args.graph_file.read_text())

                g = Graph()
                for n in data.get("nodes", []):
                    n_date = None
                    if n.get("date"):
                        try:
                            n_date = datetime.fromisoformat(n["date"])
                        except ValueError:
                            pass
                    g.add_node(
                        Node(
                            n["id"],
                            n.get("type", ""),
                            {"label": n.get("title", n["id"] )},
                            n_date,
                        )
                    )
                for e in data.get("edges", []):
                    metadata = {"label": e.get("type")}
                    if e.get("receipt"):
                        metadata["receipt"] = e.get("receipt")
                    e_date = None
                    if e.get("date"):
                        try:
                            e_date = datetime.fromisoformat(e["date"])
                        except ValueError:
                            pass
                    g.add_edge(
                        Edge(
                            e["from"],
                            e["to"],
                            e["type"],
                            metadata,
                            e_date,
                            e.get("weight"),
                        )
                    )
                nodes, edges = build_subgraph(
                    g, args.seeds, hops=args.hops, as_at=as_at
                )
                print(to_dot(nodes, edges))

                dot_output = to_dot(nodes, edges)
                if args.svg:
                    print(dot_to_svg(dot_output))
                else:
                    print(dot_output)
            else:
                from .api.routes import generate_subgraph

                combined_nodes = {}
                combined_edges = {}
                for seed in args.seeds:
                    result = generate_subgraph(seed, args.hops)
                    for n in result.get("nodes", []):
                        nid = n.get("identifier") or n.get("id")
                        combined_nodes[nid] = n
                    for e in result.get("edges", []):
                        key = (e.get("source"), e.get("target"), e.get("type"))
                        combined_edges[key] = e
                merged = {
                    "nodes": list(combined_nodes.values()),
                    "edges": list(combined_edges.values()),
                }
                if args.dot:

                if args.dot or args.svg:
                    g = Graph()
                    for n in merged["nodes"]:
                        nid = n.get("identifier") or n.get("id")
                        label = n.get("metadata", {}).get("label") or n.get(
                            "title", nid
                        )
                        n_date = None
                        if n.get("date"):
                            try:
                                n_date = datetime.fromisoformat(n["date"])
                            except ValueError:
                                pass
                        g.add_node(Node(nid, n.get("type", ""), {"label": label}, n_date))
                    for e in merged["edges"]:
                        src = e.get("source") or e.get("from")
                        tgt = e.get("target") or e.get("to")
                        typ = e.get("type")
                        meta = e.get("metadata", {})
                        label = meta.get("label", typ)
                        metadata = {"label": label}
                        receipt = meta.get("receipt") or e.get("receipt")
                        if receipt:
                            metadata["receipt"] = receipt
                        e_date = None
                        if e.get("date"):
                            try:
                                e_date = datetime.fromisoformat(e["date"])
                            except ValueError:
                                pass
                        g.add_edge(
                            Edge(src, tgt, typ, metadata, e_date, e.get("weight"))
                        )
                    if as_at:
                        nodes, edges = build_subgraph(
                            g, args.seeds, hops=args.hops, as_at=as_at
                        )
                        print(to_dot(nodes, edges))
                    else:
                        print(to_dot(g.nodes, g.edges))
                else:
                    print(json.dumps(merged))

                        dot_output = to_dot(nodes, edges)
                    else:
                        dot_output = to_dot(g.nodes, g.edges)
                    if args.svg:
                        print(dot_to_svg(dot_output))
                    else:
                        print(dot_output)
                else:
                    print(json.dumps(merged))
        else:
            parser.print_help()
    elif args.command == "eval":
        if args.eval_command == "goldset":
            from scripts.eval_goldset import evaluate

            ok = evaluate(threshold=args.threshold)
            if not ok:
                raise SystemExit(1)
        else:
            parser.print_help()
    elif args.command == "tests":
        if args.tests_command == "run":
            from .checklists.run import evaluate

            checklist = json.loads(args.tests_file.read_text())
            story = json.loads(args.story_file.read_text())
            tags = set(story.get("tags", []))
            result = evaluate(checklist, tags)
            print(json.dumps(result))
        else:
            parser.print_help()

    elif args.command == "repro":
        from .repro.ledger import CorrectionLedger
        import os

        ledger = CorrectionLedger()
        if args.repro_command == "log-correction":
            description = args.file.read_text().strip()
            author = os.getenv("USER", "unknown")
            entry = ledger.append(description=description, author=author)
            print(json.dumps(entry.__dict__))
        elif args.repro_command == "list-corrections":
            print(json.dumps(ledger.to_dicts()))

    elif args.command == "harm":
        if args.harm_command == "compute":
            from .harm import compute_harm

            story = json.loads(args.story.read_text())
            result = compute_harm(story)
            print(json.dumps(result))

    elif args.command == "definitions":
        if args.definitions_command == "expand":
            from .definitions.graph import DefinitionGraph, load_default_definitions

        text = normalise(raw_query)
        concepts = match_concepts(text)
        cloud = build_cloud(concepts)
        print(json.dumps({"cloud": cloud}))
    elif args.command == "subgraph":
        from .pipeline import build_cloud, match_concepts, normalise

        text = normalise(args.text)
        concepts = match_concepts(text)
        cloud = build_cloud(concepts)
        result = {"cloud": cloud}
        if args.dot:
            dot_lines = ["digraph G {"]
            for node, count in cloud.items():
                dot_lines.append(f'  "{node}" [label="{node} ({count})"]')
            dot_lines.append("}")
            dot = "\n".join(dot_lines)
            result["dot"] = dot
            args.dot.write_text(dot)
        print(json.dumps(result))
    elif args.command == "treatment":
        from .rules.extractor import extract_rules

        rules = [r.__dict__ for r in extract_rules(args.text)]
        result = {"rules": rules}
        if args.dot:
            dot_lines = ["digraph G {"]
            for i, rule in enumerate(rules):
                label = f"{rule['actor']} {rule['modality']} {rule['action']}"
                dot_lines.append(f'  r{i} [label="{label}"]')
            dot_lines.append("}")
            dot = "\n".join(dot_lines)
            result["dot"] = dot
            args.dot.write_text(dot)
        print(json.dumps(result))
    elif args.command == "provision":
        from .ontology.tagger import tag_text

        provision = tag_text(args.text).to_dict()
        result = {"provision": provision}
        if args.dot:
            dot_lines = ["digraph G {", '  prov [label="Provision"]']
            for p in provision["principles"]:
                dot_lines.append(f'  "{p}" [shape=box]')
                dot_lines.append(f'  prov -> "{p}" [label="principle"]')
            for c in provision["customs"]:
                dot_lines.append(f'  "{c}" [shape=ellipse]')
                dot_lines.append(f'  prov -> "{c}" [label="custom"]')
            dot_lines.append("}")
            dot = "\n".join(dot_lines)
            result["dot"] = dot
            args.dot.write_text(dot)
        print(json.dumps(result))
    elif args.command == "proof-tree":
        from .graph import (
            EdgeType,
            GraphEdge,
            GraphNode,
            LegalGraph,
            NodeType,
            expand_proof_tree,
        )

        graph_data = json.loads(args.graph.read_text())
        graph = LegalGraph()
        for n in graph_data.get("nodes", []):
            node = GraphNode(
                type=NodeType(n["type"]),
                identifier=n["id"],
                metadata=n.get("metadata", {}),
                date=date.fromisoformat(n["date"]) if n.get("date") else None,
            )
            graph.add_node(node)
        for e in graph_data.get("edges", []):
            edge = GraphEdge(
                type=EdgeType(e["type"]),
                source=e["source"],
                target=e["target"],
                metadata=e.get("metadata", {}),
                date=date.fromisoformat(e["date"]) if e.get("date") else None,
                weight=e.get("weight", 1.0),
            )
            graph.add_edge(edge)

        if args.as_at:
            as_at = datetime.fromisoformat(args.as_at).date()
        else:
            as_at = date.today()
        tree = expand_proof_tree(args.seed, args.hops, as_at, graph=graph)
        if args.dot:
            print(tree.to_dot())
        else:
            print(json.dumps(tree.to_dict()))

    elif args.command == "tests-run":
        completed = subprocess.run(["pytest", "-q"], capture_output=True, text=True)
        output = completed.stdout + completed.stderr
        result = {"exit_code": completed.returncode, "output": output}
        if args.dot:
            label = "pass" if completed.returncode == 0 else "fail"
            dot = f"digraph G {{ result [label=\"{label}\"] }}"
            result["dot"] = dot
            args.dot.write_text(dot)
        print(json.dumps(result))
    elif args.command == "concepts":
        if args.concepts_command == "match":
            from .concepts import ConceptMatcher

            matcher = ConceptMatcher()
            hits = matcher.match(args.text)
            print(json.dumps([h.__dict__ for h in hits]))
        else:
            concepts_parser.print_help()
    elif args.command == "tests":
        if args.tests_command == "run":
            from .tests.evaluator import evaluate

            template_data = json.loads(args.template.read_text())
            facts_data = json.loads(args.facts.read_text())
            table = evaluate(template_data, facts_data)
            print(json.dumps(table.to_json()))
        else:
            tests_parser.print_help()

    elif args.command == "graph" and args.graph_command == "subgraph":
        from .sample_data import build_subgraph, subgraph_to_dot

        if args.limit < 1 or args.offset < 0:
            raise ValueError("limit must be positive and offset non-negative")
        data = build_subgraph(args.node, args.limit, args.offset)
        if args.dot:
            print(subgraph_to_dot(data))
        else:
            print(json.dumps(data))
    elif args.command == "treatment":
        from .sample_data import build_subgraph, subgraph_to_dot, treatments_for

        if args.limit < 1 or args.offset < 0:
            raise ValueError("limit must be positive and offset non-negative")
        edges = treatments_for(args.doc, args.limit, args.offset)
        if args.dot:
            node_ids = {e["source"] for e in edges} | {e["target"] for e in edges}
            graph = build_subgraph(list(node_ids), args.limit, args.offset)
            graph["edges"] = edges
            print(subgraph_to_dot(graph))
        else:
            print(json.dumps(edges))
    elif args.command == "provision":
        from .sample_data import get_provision

        prov = get_provision(args.doc, args.id)
        if prov is None:
            print("Not found")
        else:
            print(json.dumps(prov))


    elif args.command == "search":
        from .storage import TextIndex

        index = TextIndex(args.db)
        results = index.search(args.query)
        print(json.dumps(results))
        index.close()

    elif args.command == "concepts":
        if args.concepts_command == "match":
            from .concepts.matcher import MATCHER

            hits = MATCHER.match(args.text)
            print(json.dumps([h.__dict__ for h in hits]))
        else:
            concepts_parser.print_help()

    elif args.command == "tests" and args.tests_command == "run":
        _cmd_tests_run(args)

    elif args.command == "tests":
        if args.tests_command == "run":
            from .tests import TEMPLATE_REGISTRY, evaluate

            template = TEMPLATE_REGISTRY.get(args.tests)
            if template is None:
                raise SystemExit(f"Unknown test template '{args.tests}'")
            data = json.loads(args.story.read_text())
            result = evaluate(template, data)
            print(json.dumps(result.to_dict()))
        else:
            tests_parser.print_help()

            defs = load_default_definitions()
            graph = DefinitionGraph(defs)
            scoped = graph.expand(args.term, depth=args.depth)
            print(json.dumps(scoped))
        else:
            parser.print_help()
    elif args.command == "cases":
        if args.cases_command == "treatment":
            from .api.routes import fetch_case_treatment

            result = fetch_case_treatment(args.case_id)
            print(json.dumps(result))
        else:
            parser.print_help()
    elif args.command == "repro":
        if args.repro_command == "adversarial":
            from .repro.adversarial import build_bundle

            build_bundle(args.topic, args.output)

    elif args.command == "tools":
        if args.tools_command == "counter-brief":
            from .tools.counter_brief import generate_counter_brief

            result = generate_counter_brief(args.file)
            print(json.dumps(result))

    elif args.command == "publish":
        from .publish.mirror import generate_site

        generate_site(args.seed, args.out)
 

    elif args.command == "receipts":
        if args.receipts_command == "diff":
            from .text.similarity import minhash, simhash

            old_text = Path(args.old).read_text(encoding="utf-8")
            new_text = Path(args.new).read_text(encoding="utf-8")
            if old_text == new_text:
                print("identical")
            elif minhash(old_text) == minhash(new_text):
                print("cosmetic")
            else:
                print("substantive")

    elif args.command == "intake":
        if args.intake_command == "parse":
            from .intake.email_parser import fetch_messages, parse_email
            from .intake.stub_builder import build_stub

            messages = fetch_messages(str(args.mailbox))
            for msg in messages:
                data = parse_email(msg)
                build_stub(data, args.out)
        else:
            parser.print_help()
    elif args.command == "tools":
        if args.tools_command == "claim-builder":
            from .tools.claim_builder import build_claim

            build_claim(args.dir)
        else:
            parser.print_help()
 
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
