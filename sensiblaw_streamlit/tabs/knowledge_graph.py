"""Knowledge Graph tab for the SensibLaw Streamlit console."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from sensiblaw_streamlit.constants import (
    DEFAULT_DB_NAME,
    SAMPLE_CASE_TREATMENT_METADATA,
    SAMPLE_GRAPH_CASES,
    SAMPLE_GRAPH_EDGES,
)
from sensiblaw_streamlit.shared import (
    ROOT,
    _build_knowledge_graph_dot,
    _build_principle_graph_dot,
    _download_json,
    _render_dot,
    _render_table,
)

from src.api.routes import (
    HTTPException,
    _graph as ROUTES_GRAPH,
    execute_tests,
    fetch_case_treatment,
    fetch_provision_atoms,
    generate_subgraph,
)
from src.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from src.tests.templates import TEMPLATE_REGISTRY


def _seed_sample_graph() -> None:
    """Populate the FastAPI routes graph with demonstration data."""

    if ROUTES_GRAPH.nodes:
        return

    for identifier, meta in SAMPLE_GRAPH_CASES.items():
        ROUTES_GRAPH.add_node(
            GraphNode(
                type=NodeType.CASE,
                identifier=identifier,
                metadata={"title": meta["title"]},
                cultural_flags=meta.get("cultural_flags"),
                consent_required=meta.get("consent_required", False),
            )
        )

    for source, target, relation, weight in SAMPLE_GRAPH_EDGES:
        metadata = {
            "relation": relation,
            "court": SAMPLE_CASE_TREATMENT_METADATA.get(relation, {}).get(
                "court", "HCA"
            ),
        }
        edge = GraphEdge(
            type=EdgeType.CITES,
            source=source,
            target=target,
            metadata=metadata,
            weight=weight,
        )
        try:
            ROUTES_GRAPH.add_edge(edge)
        except ValueError:
            continue


def _escape_markdown(text: str) -> str:
    """Escape Markdown control characters for safe rendering."""

    if not isinstance(text, str):
        return str(text)
    return re.sub(r"([\\`*_{}\[\]()#+\-!])", r"\\\\\1", text)


def _format_proof(proof: Dict[str, Any]) -> str:
    """Build a human friendly summary of the proof payload."""

    if not proof:
        return "status unknown"

    status = _escape_markdown(str(proof.get("status", "unknown"))).capitalize()
    details: List[str] = []

    confidence = proof.get("confidence")
    if isinstance(confidence, (int, float)):
        if 0 <= confidence <= 1:
            details.append(f"confidence {confidence:.0%}")
        else:
            details.append(f"confidence {confidence}")

    evidence_count = proof.get("evidenceCount")
    if isinstance(evidence_count, (int, float)):
        suffix = "s" if evidence_count != 1 else ""
        details.append(f"{int(evidence_count)} evidence source{suffix}")

    if details:
        return f"{status} ({', '.join(details)})"
    return status


def _build_atom_lines(atom: Dict[str, Any], depth: int = 0) -> List[str]:
    """Recursively render provision atoms into a Markdown bullet list."""

    indent = "  " * depth
    label = _escape_markdown(atom.get("label") or atom.get("id") or "Unnamed atom")
    role = atom.get("role")
    role_segment = f"*{_escape_markdown(role)}*" if role else None
    proof_segment = _format_proof(atom.get("proof", {}))

    meta_segments = [segment for segment in (role_segment, proof_segment) if segment]
    headline = f"{indent}- **{label}**"
    if meta_segments:
        headline += " — " + ", ".join(meta_segments)

    lines = [headline]

    notes = atom.get("notes")
    if notes:
        lines.append(f"{indent}  _Notes_: {_escape_markdown(str(notes))}")

    principle = atom.get("principle") or {}
    principle_title = principle.get("title")
    principle_summary = principle.get("summary")
    if principle_title or principle_summary:
        summary_parts = []
        if principle_title:
            summary_parts.append(f"**{_escape_markdown(str(principle_title))}**")
        if principle_summary:
            summary_parts.append(_escape_markdown(str(principle_summary)))
        lines.append(f"{indent}  _Principle_: {' — '.join(summary_parts)}")

    principle_tags = principle.get("tags")
    if principle_tags:
        escaped_tags = ", ".join(_escape_markdown(str(tag)) for tag in principle_tags)
        lines.append(f"{indent}  _Tags_: {escaped_tags}")

    principle_citation = principle.get("citation")
    if principle_citation:
        lines.append(
            f"{indent}  _Citation_: `{_escape_markdown(str(principle_citation))}`"
        )

    for child in atom.get("children", []) or []:
        lines.extend(_build_atom_lines(child, depth + 1))

    return lines


def _render_provision_atoms(provision: Dict[str, Any]) -> None:
    """Render provision atoms in a readable outline with the raw JSON in an expander."""

    title = provision.get("title")
    provision_id = provision.get("provision_id")
    if title:
        st.markdown(f"**{_escape_markdown(str(title))}**")
    if provision_id:
        st.caption(_escape_markdown(str(provision_id)))

    atoms = provision.get("atoms", [])
    if not atoms:
        st.info("No atoms available for this provision.")
        return

    atom_lines: List[str] = []
    for atom in atoms:
        atom_lines.extend(_build_atom_lines(atom))

    st.markdown("\n".join(atom_lines))

    with st.expander("Show raw JSON response", expanded=False):
        st.json(provision)


def _available_case_identifiers() -> List[str]:
    """Return sorted case identifiers currently present in the graph."""

    identifiers = [
        identifier
        for identifier, node in ROUTES_GRAPH.nodes.items()
        if getattr(node, "type", None) in (NodeType.CASE, NodeType.DOCUMENT)
    ]
    identifiers.sort()
    return identifiers


def _available_store_identifiers(db_path: Path) -> List[str]:
    """Return sorted case identifiers available in the SQLite store at ``db_path``."""

    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return []

    try:
        try:
            rows = conn.execute("SELECT id, type, data FROM nodes").fetchall()
        except sqlite3.Error:
            return []
    finally:
        conn.close()

    identifiers: List[str] = []
    for row in rows:
        node_type = (row["type"] or "").upper()
        if node_type not in ("CASE", "DOCUMENT"):
            continue
        payload: Dict[str, Any] = {}
        row_data = row["data"]
        if row_data:
            try:
                payload = json.loads(row_data)
            except json.JSONDecodeError:
                payload = {}
        identifier = (
            payload.get("identifier")
            or payload.get("id")
            or payload.get("citation")
            or payload.get("title")
            or f"{row['type']}#{row['id']}"
        )
        identifiers.append(str(identifier))

    return sorted(dict.fromkeys(identifiers))


def _load_graph_from_store(db_path: Path) -> Tuple[int, int, Optional[str]]:
    """Populate ``ROUTES_GRAPH`` using ingested data from ``db_path``."""

    if not db_path.exists():
        raise FileNotFoundError(f"No SQLite database found at {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    primary_seed: Optional[str] = None

    try:
        storage_nodes = conn.execute("SELECT id, type, data FROM nodes").fetchall()
        if storage_nodes:
            id_to_identifier: Dict[int, str] = {}
            for row in storage_nodes:
                payload: Dict[str, Any] = {}
                if row["data"]:
                    try:
                        payload = json.loads(row["data"])
                    except json.JSONDecodeError:
                        payload = {}
                identifier_value = (
                    payload.get("identifier")
                    or payload.get("id")
                    or payload.get("citation")
                    or payload.get("title")
                    or f"{row['type']}#{row['id']}"
                )
                identifier = str(identifier_value)
                id_to_identifier[row["id"]] = identifier
                try:
                    node_type = NodeType[row["type"].upper()]
                except KeyError:
                    try:
                        node_type = NodeType[row["type"]]
                    except KeyError:
                        node_type = NodeType.DOCUMENT

                metadata_payload = payload.get("metadata")
                if not isinstance(metadata_payload, dict):
                    metadata_payload = {
                        k: v
                        for k, v in payload.items()
                        if k not in {"identifier", "id", "date", "metadata"}
                    }
                node_metadata = {
                    k: v for k, v in (metadata_payload or {}).items() if v is not None
                }

                node_date: Optional[date] = None
                date_value = payload.get("date")
                if isinstance(date_value, str):
                    try:
                        node_date = date.fromisoformat(date_value)
                    except ValueError:
                        node_date = None

                cultural_flags = payload.get("cultural_flags")
                consent_required = bool(payload.get("consent_required"))
                node = GraphNode(
                    type=node_type,
                    identifier=identifier,
                    metadata=node_metadata,
                    date=node_date,
                    cultural_flags=list(cultural_flags)
                    if isinstance(cultural_flags, (list, tuple))
                    else None,
                    consent_required=consent_required,
                )
                nodes.append(node)
                if primary_seed is None:
                    primary_seed = identifier

            storage_edges = conn.execute(
                "SELECT source, target, type, data FROM edges"
            ).fetchall()
            for row in storage_edges:
                source_identifier = id_to_identifier.get(row["source"])
                target_identifier = id_to_identifier.get(row["target"])
                if not source_identifier or not target_identifier:
                    continue
                try:
                    edge_type = EdgeType[row["type"].upper()]
                except KeyError:
                    try:
                        edge_type = EdgeType[row["type"]]
                    except KeyError:
                        continue
                edge_metadata: Dict[str, Any] = {}
                if row["data"]:
                    try:
                        edge_metadata = json.loads(row["data"])
                    except json.JSONDecodeError:
                        edge_metadata = {}
                edges.append(
                    GraphEdge(
                        type=edge_type,
                        source=source_identifier,
                        target=target_identifier,
                        metadata=edge_metadata,
                    )
                )
        else:
            doc_rows = conn.execute(
                """
                SELECT d.id AS doc_id,
                       latest.rev_id AS rev_id,
                       r.metadata AS metadata
                FROM documents AS d
                JOIN (
                    SELECT doc_id, MAX(rev_id) AS rev_id
                    FROM revisions
                    GROUP BY doc_id
                ) AS latest
                    ON latest.doc_id = d.id
                JOIN revisions AS r
                    ON r.doc_id = latest.doc_id
                   AND r.rev_id = latest.rev_id
                """
            ).fetchall()
            if not doc_rows:
                raise ValueError(
                    "No ingested documents found in the selected store."
                )

            doc_identifiers: Dict[Tuple[int, int], str] = {}
            for row in doc_rows:
                metadata_payload: Dict[str, Any] = {}
                if row["metadata"]:
                    try:
                        metadata_payload = json.loads(row["metadata"])
                    except json.JSONDecodeError:
                        metadata_payload = {}

                identifier_value = (
                    metadata_payload.get("canonical_id")
                    or metadata_payload.get("citation")
                    or f"Document#{row['doc_id']}"
                )
                identifier = str(identifier_value)

                node_type = (
                    NodeType.CASE
                    if metadata_payload.get("court")
                    else NodeType.DOCUMENT
                )
                node_metadata = {
                    "title": metadata_payload.get("title")
                    or metadata_payload.get("citation"),
                    "citation": metadata_payload.get("citation"),
                    "jurisdiction": metadata_payload.get("jurisdiction"),
                    "court": metadata_payload.get("court"),
                    "source_url": metadata_payload.get("source_url"),
                }
                if metadata_payload.get("lpo_tags"):
                    node_metadata["lpo_tags"] = metadata_payload["lpo_tags"]
                if metadata_payload.get("cco_tags"):
                    node_metadata["cco_tags"] = metadata_payload["cco_tags"]

                node_date: Optional[date] = None
                date_value = metadata_payload.get("date")
                if isinstance(date_value, str):
                    try:
                        node_date = date.fromisoformat(date_value)
                    except ValueError:
                        node_date = None

                cultural_flags = metadata_payload.get("cultural_flags")
                consent_required = bool(
                    metadata_payload.get("cultural_consent_required")
                )
                node = GraphNode(
                    type=node_type,
                    identifier=identifier,
                    metadata={k: v for k, v in node_metadata.items() if v},
                    date=node_date,
                    cultural_flags=list(cultural_flags)
                    if isinstance(cultural_flags, (list, tuple))
                    else None,
                    consent_required=consent_required,
                )
                nodes.append(node)
                doc_identifiers[(row["doc_id"], row["rev_id"])] = identifier
                if primary_seed is None:
                    primary_seed = identifier

            provision_rows = conn.execute(
                """
                SELECT doc_id,
                       rev_id,
                       provision_id,
                       identifier,
                       heading,
                       node_type
                FROM provisions
                """
            ).fetchall()

            seen_provisions: set[str] = set()
            seen_edges: set[Tuple[str, str, EdgeType]] = set()
            for row in provision_rows:
                doc_identifier = doc_identifiers.get((row["doc_id"], row["rev_id"]))
                if not doc_identifier:
                    continue

                local_identifier = (
                    row["identifier"]
                    or row["heading"]
                    or f"p{row['provision_id']}"
                )
                provision_identifier = f"{doc_identifier}::{local_identifier}"

                if provision_identifier not in seen_provisions:
                    provision_metadata = {
                        "heading": row["heading"],
                        "identifier": row["identifier"],
                        "node_type": row["node_type"],
                    }
                    nodes.append(
                        GraphNode(
                            type=NodeType.PROVISION,
                            identifier=provision_identifier,
                            metadata={
                                k: v for k, v in provision_metadata.items() if v
                            },
                        )
                    )
                    seen_provisions.add(provision_identifier)

                edge_key = (
                    provision_identifier,
                    doc_identifier,
                    EdgeType.INTERPRETED_BY,
                )
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edges.append(
                    GraphEdge(
                        type=EdgeType.INTERPRETED_BY,
                        source=provision_identifier,
                        target=doc_identifier,
                        metadata={
                            k: v
                            for k, v in {
                                "relation": "interprets",
                                "heading": row["heading"],
                                "identifier": row["identifier"],
                            }.items()
                            if v
                        },
                    )
                )
    finally:
        conn.close()

    if not nodes:
        raise ValueError("No graph data could be loaded from the selected store.")

    ROUTES_GRAPH.nodes.clear()
    ROUTES_GRAPH.edges.clear()

    for node in nodes:
        ROUTES_GRAPH.add_node(node)

    for edge in edges:
        try:
            ROUTES_GRAPH.add_edge(edge)
        except ValueError:
            continue

    return len(ROUTES_GRAPH.nodes), len(ROUTES_GRAPH.edges), primary_seed


def render() -> None:
    st.subheader("Knowledge Graph")
    st.write(
        "Generate subgraphs, execute legal tests, inspect case treatments, and fetch provision atoms."
    )

    default_store = st.session_state.get(
        "kg_graph_store_path", str(ROOT / "ui" / DEFAULT_DB_NAME)
    )
    store_input = st.text_input(
        "Ingested graph store",
        value=default_store,
        key="kg_graph_store_path",
        help=(
            "SQLite database containing ingested cases, provisions, and treatments."
        ),
    )
    graph_store_path = Path(store_input).expanduser()

    load_ingested_col, load_sample_col = st.columns(2)
    with load_ingested_col:
        if st.button(
            "Load ingested graph data",
            key="kg_load_ingested_graph",
            help="Populate the in-memory graph from the selected SQLite store.",
        ):
            try:
                node_count, edge_count, primary_seed = _load_graph_from_store(
                    graph_store_path
                )
            except FileNotFoundError as exc:
                st.error(str(exc))
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(
                    f"Loaded {node_count} nodes and {edge_count} edges from {graph_store_path}."
                )
                if primary_seed:
                    st.session_state["kg_subgraph_seed_input"] = primary_seed
                    st.session_state["kg_case_id_input"] = primary_seed
                    st.session_state["kg_subgraph_seed_select"] = primary_seed

    with load_sample_col:
        if st.button(
            "Load sample graph data",
            help="Populate the in-memory graph with demo cases",
        ):
            _seed_sample_graph()
            st.success("Sample graph seeded.")

    if not ROUTES_GRAPH.nodes:
        st.info(
            "The in-memory graph is empty. Load the sample dataset above or ingest"
            " your own nodes before running queries."
        )

    st.markdown("### Generate subgraph")
    graph_seed_ids = _available_case_identifiers()
    store_seed_ids = _available_store_identifiers(graph_store_path)
    combined_seed_ids = sorted(
        dict.fromkeys((*store_seed_ids, *graph_seed_ids))
    )
    with st.form("subgraph_form"):
        seed_default = st.session_state.get("kg_subgraph_seed_input")
        if not seed_default:
            if ROUTES_GRAPH.nodes:
                seed_default = next(iter(ROUTES_GRAPH.nodes.keys()))
            elif combined_seed_ids:
                seed_default = combined_seed_ids[0]
            else:
                seed_default = "Case#Mabo1992"

        select_options: List[str] = []
        manual_entry = False
        if combined_seed_ids:
            select_options = ["Manual entry", *combined_seed_ids]
            default_index = 0
            if seed_default in combined_seed_ids:
                default_index = combined_seed_ids.index(seed_default) + 1
            seed_selection = st.selectbox(
                "Seed node",
                options=select_options,
                index=default_index,
                key="kg_subgraph_seed_select",
                help="Pick from case identifiers stored in the knowledge graph database.",
            )
            manual_entry = seed_selection == "Manual entry"
        else:
            manual_entry = True
            seed_selection = None

        if manual_entry:
            seed = st.text_input(
                "Seed node (manual entry)",
                value=seed_default,
                key="kg_subgraph_seed_input",
                help="Identifier for the node to start the subgraph generation from.",
            )
        else:
            seed = seed_selection
            st.session_state["kg_subgraph_seed_input"] = seed
        hops = st.slider("Maximum hops", min_value=1, max_value=5, value=2)
        consent = st.checkbox("Include consent gated nodes", value=False)
        submit = st.form_submit_button("Generate")

    if submit:
        try:
            with st.spinner("Generating subgraph"):
                payload = generate_subgraph(seed, hops, consent=consent)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            st.success("Subgraph generated.")
            dot = _build_knowledge_graph_dot(payload)
            if dot:
                _render_dot(dot, key="knowledge_subgraph")
            else:
                st.info(
                    "Graphviz is not available. Install the optional dependency to see"
                    " the visualisation."
                )
            st.json(payload)
            _download_json("Download subgraph", payload, "subgraph.json")

    st.markdown("### Execute legal tests")
    template_ids = list(TEMPLATE_REGISTRY.keys())
    with st.form("tests_form"):
        selected_ids = st.multiselect(
            "Test templates", template_ids, default=template_ids[:1]
        )
        default_story = json.dumps(
            {"facts": {fid: True for fid in ("delay",)}}, indent=2
        )
        story_json = st.text_area(
            "Story facts JSON",
            value=st.session_state.get("story_json", default_story),
            height=160,
        )
        st.session_state["story_json"] = story_json
        tests_submit = st.form_submit_button("Run tests")

    if tests_submit:
        try:
            story_payload = json.loads(story_json or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            facts = story_payload.get("facts", story_payload)
            with st.spinner("Evaluating templates"):
                try:
                    result = execute_tests(selected_ids, facts)
                except HTTPException as exc:
                    st.error(f"{exc.detail} (HTTP {exc.status_code})")
                else:
                    st.json(result)
                    _download_json("Download test results", result, "tests.json")

    st.markdown("### Case treatment summary")
    available_case_ids = _available_case_identifiers()

    selected_case_id: Optional[str] = None
    if available_case_ids:
        selected_case_id = st.selectbox(
            "Available cases",
            options=available_case_ids,
            key="kg_case_id_select",
            help="Select from cases loaded into the in-memory graph.",
        )
    else:
        st.info(
            "No cases are available yet. Load the sample graph or ingest data to enable"
            " treatment summaries."
        )

    if "kg_case_id_input" not in st.session_state:
        st.session_state["kg_case_id_input"] = selected_case_id or "Case#Mabo1992"

    previous_selection = st.session_state.get("kg_case_id_select_prev")
    if (
        selected_case_id
        and selected_case_id != previous_selection
        and st.session_state.get("kg_case_id_input") in (None, "", previous_selection)
    ):
        st.session_state["kg_case_id_input"] = selected_case_id
    st.session_state["kg_case_id_select_prev"] = selected_case_id

    case_id = st.text_input(
        "Case identifier",
        key="kg_case_id_input",
        help="Enter the identifier for a case stored in the knowledge graph.",
    )
    treatment_submit = st.button("Fetch treatment", key="kg_fetch_treatment")

    if treatment_submit:
        try:
            with st.spinner("Fetching treatment"):
                data = fetch_case_treatment(case_id)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            st.json(data)
            _render_table(data.get("treatments", []), key="treatments")

    st.markdown("### Provision atoms")
    with st.form("provision_form"):
        provision_id = st.text_input(
            "Provision identifier",
            value="Provision#NTA:s223",
        )
        provision_submit = st.form_submit_button("Fetch provision atoms")

    if provision_submit:
        try:
            with st.spinner("Retrieving provision atoms"):
                provision = fetch_provision_atoms(provision_id)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            _render_provision_atoms(provision)
            _download_json(
                "Download provision atoms", provision, "provision_atoms.json"
            )
            dot = _build_principle_graph_dot(provision)
            if dot:
                st.markdown("#### Principle relationship map")
                _render_dot(dot, key="principle_graph")
            else:
                st.info(
                    "Graphviz is not installed. Install the optional dependency to view the principle map."
                )


__all__ = ["render"]
