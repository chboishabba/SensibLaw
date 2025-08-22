from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def _slug(parties: List[str]) -> str:
    if not parties:
        return "case"
    return "-".join(p.lower().replace(" ", "_") for p in parties)


def build_stub(data: Dict[str, str], out_dir: Path) -> Path:
    """Write a draft case record to ``out_dir``.

    The filename is derived from the parties to allow deterministic output.
    The record minimally contains the parties, jurisdiction and summary.
    """

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    filename = f"{_slug(data.get('parties', []))}.json"
    path = out / filename
    payload = {
        "parties": data.get("parties", []),
        "jurisdiction": data.get("jurisdiction"),
        "summary": data.get("summary"),
    }
    path.write_text(json.dumps(payload, indent=2))
    return path
