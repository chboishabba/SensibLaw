from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def slug_artifact_name(text: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(text or "").strip())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("._") or "artifact"


def read_json_file(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_out_dir_for_pack(pack_path: Path) -> Path:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack_id = str(pack.get("pack_id") or pack_path.stem or "wiki_revision_monitor").strip()
    return Path("SensibLaw/demo/ingest/wiki_revision_monitor") / slug_artifact_name(pack_id)


def revision_artifact_paths(*, out_dir: Path, article_id: str, revid: int | None) -> dict[str, Path]:
    revid_text = str(revid) if revid is not None else "none"
    base = f"{slug_artifact_name(article_id)}__revid_{revid_text}"
    return {
        "snapshot": out_dir / "snapshots" / f"{base}.json",
        "timeline": out_dir / "timeline" / f"{base}.json",
        "aoo": out_dir / "aoo" / f"{base}.json",
    }


def pair_artifact_paths(
    *,
    out_dir: Path,
    article_id: str,
    pair_kind: str,
    older_revid: int | None,
    newer_revid: int | None,
) -> dict[str, Path]:
    base = f"{slug_artifact_name(article_id)}__{slug_artifact_name(pair_kind)}__{older_revid or 'none'}__{newer_revid or 'none'}"
    return {
        "older_snapshot": out_dir / "pair_snapshots" / f"{base}__older.json",
        "newer_snapshot": out_dir / "pair_snapshots" / f"{base}__newer.json",
        "older_timeline": out_dir / "timeline" / f"{base}__older.json",
        "newer_timeline": out_dir / "timeline" / f"{base}__newer.json",
        "older_aoo": out_dir / "aoo" / f"{base}__older.json",
        "newer_aoo": out_dir / "aoo" / f"{base}__newer.json",
        "pair_report": out_dir / "pair_reports" / f"{base}.json",
    }


def graph_artifact_path(*, out_dir: Path, article_id: str, run_id: str) -> Path:
    return out_dir / "contested_graphs" / f"{slug_artifact_name(article_id)}__{slug_artifact_name(run_id)}.json"
