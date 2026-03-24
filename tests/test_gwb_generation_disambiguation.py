from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "SensibLaw" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_gwb_zelph_handoff import _build_reports


def test_father_era_bush_surface_abstains_in_corpus() -> None:
    payload = json.loads(
        (REPO_ROOT / "SensibLaw" / "demo" / "ingest" / "gwb" / "corpus_v1" / "wiki_timeline_gwb_corpus_v1.json").read_text(
            encoding="utf-8"
        )
    )
    _, semantic = _build_reports(timeline_payload=payload)
    event = next(row for row in semantic["per_event"] if row["event_id"] == "ev:0089")
    mentions = list(event.get("mentions", []))
    assert any(
        mention["surface_text"] == "Bush"
        and mention["resolution_status"] == "abstained"
        and mention["resolution_rule"] == "generation_disambiguation_required_v1"
        for mention in mentions
    )
    assert not any(
        mention["surface_text"] == "Bush"
        and mention["resolution_status"] == "resolved"
        and (mention.get("resolved_entity") or {}).get("canonical_key") == "actor:george_w_bush"
        for mention in mentions
    )
