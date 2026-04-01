#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.storage.repo_roots import relative_repo_path, repo_root, sensiblaw_root

REPO_ROOT = repo_root()
SENSIBLAW_ROOT = sensiblaw_root()
ARTIFACT_VERSION = "gwb_corpus_scorecard_v1"
DEFAULT_OUTPUT_DIR = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / ARTIFACT_VERSION
DEFAULT_HANDOFF_SCORECARD_PATH = SENSIBLAW_ROOT / "tests" / "fixtures" / "zelph" / "gwb_public_handoff_v1" / "gwb_public_handoff_v1.scorecard.json"
DEFAULT_PUBLIC_BIOS_PACK_PATH = SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "gwb_public_bios_v1.json"
DEFAULT_PUBLIC_BIOS_MANIFEST_PATH = SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "manifest.json"
DEFAULT_PUBLIC_BIOS_TIMELINE_PATH = SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "timeline.json"
DEFAULT_PUBLIC_BIOS_GRAPH_PATH = SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "public_bios_v1" / "timeline_graph.json"
DEFAULT_CORPUS_TIMELINE_PATH = SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "corpus_v1" / "wiki_timeline_gwb_corpus_v1.json"
DEFAULT_CORPUS_AAO_PATH = SENSIBLAW_ROOT / "demo" / "ingest" / "gwb" / "corpus_v1" / "wiki_timeline_gwb_corpus_v1_aoo.json"
DEFAULT_BOOK_ROOT = SENSIBLAW_ROOT / "demo" / "ingest" / "gwb"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_slice(
    *,
    handoff_scorecard_path: Path,
    public_bios_pack_path: Path,
    public_bios_manifest_path: Path,
    public_bios_timeline_path: Path,
    public_bios_graph_path: Path,
    corpus_timeline_path: Path,
    corpus_aao_path: Path,
    book_root: Path,
) -> dict[str, Any]:
    handoff_scorecard = _read_json(handoff_scorecard_path)
    public_bios_pack = _read_json(public_bios_pack_path)
    public_bios_manifest = _read_json(public_bios_manifest_path)
    public_bios_timeline = _read_json(public_bios_timeline_path)
    public_bios_graph = _read_json(public_bios_graph_path)
    corpus_timeline = _read_json(corpus_timeline_path)
    corpus_aao = _read_json(corpus_aao_path)

    local_book_files = sorted(
        path for path in book_root.iterdir() if path.is_file() and path.suffix.lower() in {".epub", ".pdf"}
    )
    public_bios_source = (public_bios_pack.get("sources") or [{}])[0]
    source_family_inventory = [
        {
            "family": "checked_handoff",
            "path": str(handoff_scorecard_path.relative_to(REPO_ROOT)),
            "promoted_relation_count": int(handoff_scorecard.get("promoted_relation_count") or 0),
            "matched_seed_lane_count": int(handoff_scorecard.get("matched_seed_lane_count") or 0),
            "ambiguous_event_count": int(handoff_scorecard.get("ambiguous_event_count") or 0),
        },
        {
            "family": "public_bios_pack",
            "path": str(public_bios_pack_path.relative_to(REPO_ROOT)),
            "seed_url_count": len(public_bios_source.get("seed_urls", [])),
            "seed_path_count": len(public_bios_source.get("seed_paths", [])),
            "manifest_document_count": len(public_bios_manifest.get("documents", [])),
            "timeline_event_count": len(public_bios_timeline.get("events", [])),
            "graph_node_count": len(public_bios_graph.get("nodes", [])),
            "graph_edge_count": len(public_bios_graph.get("edges", [])),
        },
        {
            "family": "corpus_timeline",
            "path": str(corpus_timeline_path.relative_to(REPO_ROOT)),
            "timeline_event_count": len(corpus_timeline.get("events", [])),
            "aao_event_count": len(corpus_aao.get("events", [])),
        },
        {
            "family": "local_books",
            "path": str(book_root.relative_to(REPO_ROOT)),
            "file_count": len(local_book_files),
            "files": [path.name for path in local_book_files],
        },
    ]

    return {
        "version": ARTIFACT_VERSION,
        "fixture_kind": "source_family_inventory_scorecard",
        "summary": {
            "source_family_count": len(source_family_inventory),
            "checked_handoff_promoted_relation_count": int(handoff_scorecard.get("promoted_relation_count") or 0),
            "checked_handoff_matched_seed_lane_count": int(handoff_scorecard.get("matched_seed_lane_count") or 0),
            "public_bios_manifest_document_count": len(public_bios_manifest.get("documents", [])),
            "public_bios_timeline_event_count": len(public_bios_timeline.get("events", [])),
            "public_bios_graph_node_count": len(public_bios_graph.get("nodes", [])),
            "public_bios_graph_edge_count": len(public_bios_graph.get("edges", [])),
            "corpus_timeline_event_count": len(corpus_timeline.get("events", [])),
            "corpus_aao_event_count": len(corpus_aao.get("events", [])),
            "local_book_file_count": len(local_book_files),
        },
        "source_family_inventory": source_family_inventory,
    }


def _build_summary_text(slice_payload: dict[str, Any]) -> str:
    summary = slice_payload["summary"]
    lines = [
        "# GWB Corpus Scorecard Summary",
        "",
        "This artifact answers a different question from the bounded GWB Zelph",
        "handoff. Instead of only counting promoted relations in the checked",
        "slice, it inventories the broader in-repo source families that the GWB",
        "lane can already draw on.",
        "",
        "## Current source-family inventory",
        "",
        f"- Source families counted: {summary['source_family_count']}",
        f"- Checked handoff promoted relations: {summary['checked_handoff_promoted_relation_count']}",
        f"- Checked handoff matched seed lanes: {summary['checked_handoff_matched_seed_lane_count']}",
        f"- Public-bios manifest documents: {summary['public_bios_manifest_document_count']}",
        f"- Public-bios timeline events: {summary['public_bios_timeline_event_count']}",
        f"- Public-bios graph nodes/edges: {summary['public_bios_graph_node_count']}/{summary['public_bios_graph_edge_count']}",
        f"- Corpus timeline events: {summary['corpus_timeline_event_count']}",
        f"- Corpus AAO events: {summary['corpus_aao_event_count']}",
        f"- Local demo/book files: {summary['local_book_file_count']}",
        "",
        "## Source families",
        "",
    ]
    for row in slice_payload["source_family_inventory"]:
        if row["family"] == "local_books":
            lines.append(f"- {row['family']}: {row['file_count']} local files.")
            continue
        metrics = ", ".join(
            f"{key}={value}"
            for key, value in row.items()
            if key not in {"family", "path"} and not isinstance(value, list)
        )
        lines.append(f"- {row['family']}: {metrics}.")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- The checked handoff remains useful for downstream Zelph reasoning.",
            "- This corpus scorecard is the companion that shows the source-family",
            "  breadth already present in-repo beyond that handpicked slice.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_scorecard(slice_payload: dict[str, Any]) -> dict[str, Any]:
    summary = slice_payload["summary"]
    return {
        "destination": "complete_gwb_topic_understanding",
        "current_stage": "source_family_inventory_checkpoint",
        "source_family_count": summary["source_family_count"],
        "checked_handoff_promoted_relation_count": summary["checked_handoff_promoted_relation_count"],
        "checked_handoff_matched_seed_lane_count": summary["checked_handoff_matched_seed_lane_count"],
        "public_bios_manifest_document_count": summary["public_bios_manifest_document_count"],
        "public_bios_timeline_event_count": summary["public_bios_timeline_event_count"],
        "public_bios_graph_node_count": summary["public_bios_graph_node_count"],
        "public_bios_graph_edge_count": summary["public_bios_graph_edge_count"],
        "corpus_timeline_event_count": summary["corpus_timeline_event_count"],
        "corpus_aao_event_count": summary["corpus_aao_event_count"],
        "local_book_file_count": summary["local_book_file_count"],
    }


def build_corpus_scorecard(output_dir: Path) -> dict[str, Any]:
    slice_payload = _build_slice(
        handoff_scorecard_path=DEFAULT_HANDOFF_SCORECARD_PATH,
        public_bios_pack_path=DEFAULT_PUBLIC_BIOS_PACK_PATH,
        public_bios_manifest_path=DEFAULT_PUBLIC_BIOS_MANIFEST_PATH,
        public_bios_timeline_path=DEFAULT_PUBLIC_BIOS_TIMELINE_PATH,
        public_bios_graph_path=DEFAULT_PUBLIC_BIOS_GRAPH_PATH,
        corpus_timeline_path=DEFAULT_CORPUS_TIMELINE_PATH,
        corpus_aao_path=DEFAULT_CORPUS_AAO_PATH,
        book_root=DEFAULT_BOOK_ROOT,
    )
    summary_text = _build_summary_text(slice_payload)
    scorecard_payload = _build_scorecard(slice_payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "slice_path": output_dir / f"{ARTIFACT_VERSION}.json",
        "summary_path": output_dir / f"{ARTIFACT_VERSION}.summary.md",
    }
    paths["slice_path"].write_text(json.dumps(scorecard_payload | {"slice": slice_payload}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["summary_path"].write_text(summary_text + "\n", encoding="utf-8")
    return {
        "scorecard": scorecard_payload,
        **{k: str(v) for k, v in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the broader GWB corpus scorecard from in-repo source-family artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write the GWB corpus scorecard into.")
    args = parser.parse_args()
    payload = build_corpus_scorecard(Path(args.output_dir).resolve())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
