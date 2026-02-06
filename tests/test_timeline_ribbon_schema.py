from __future__ import annotations

import json
from pathlib import Path

import jsonschema


def test_timeline_ribbon_schema_accepts_minimal_example():
    schema_path = Path("schemas/timeline.ribbon.v1.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = {
        "spine": {"domain": {"type": "continuous", "start": 0.0, "end": 10.0}},
        "lens": {"id": "time", "name": "Time", "units": "seconds", "total_mass": 10.0},
        "segments": [
            {"id": "seg-1", "t_start": 0.0, "t_end": 5.0, "mass": 5.0, "width_norm": 0.5},
            {"id": "seg-2", "t_start": 5.0, "t_end": 10.0, "mass": 5.0, "width_norm": 0.5},
        ],
        "threads": [
            {"id": "th-1", "anchor_t": 2.5, "segment_id": "seg-1", "kind": "evidence"}
        ],
    }
    jsonschema.validate(payload, schema)
