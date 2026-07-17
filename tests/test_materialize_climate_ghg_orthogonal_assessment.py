from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.materialize_climate_ghg_orthogonal_assessment import (
    _target_collision_states,
    materialize,
)


REPLAY = Path(
    "data/ontology/wikidata_migration_packs/p5991_p14143_company_direct_replay_20260717"
)


def test_target_collision_evidence_absent_present_and_unresolved() -> None:
    pack = {
        "candidates": [
            {"candidate_id": "c1", "source_statement_id": "s1"},
            {"candidate_id": "c2", "source_statement_id": "s2"},
            {"candidate_id": "c3", "source_statement_id": "s3"},
        ]
    }
    coverage = {
        "coverage": {
            "candidate_rows": [
                {
                    "candidate_ref": "c1",
                    "detector_results": [
                        {
                            "predicate_results": [
                                {
                                    "predicate_ref": "entity.target-property-absent",
                                    "state": "satisfied",
                                    "observed": "absent",
                                }
                            ]
                        }
                    ],
                },
                {
                    "candidate_ref": "c2",
                    "detector_results": [
                        {
                            "predicate_results": [
                                {
                                    "predicate_ref": "entity.target-property-absent",
                                    "state": "failed",
                                }
                            ]
                        }
                    ],
                },
                {
                    "candidate_ref": "c3",
                    "detector_results": [
                        {
                            "predicate_results": [
                                {
                                    "predicate_ref": "entity.target-property-absent",
                                    "state": "abstained",
                                }
                            ]
                        }
                    ],
                },
            ]
        }
    }
    assert _target_collision_states(pack, coverage) == {
        "s1": "absent",
        "s2": "present",
        "s3": "unresolved",
    }


def test_pinned_materialization_is_atomic_and_existing_output_is_immutable(
    tmp_path: Path,
) -> None:
    output = tmp_path / "orthogonal"
    assert materialize(replay_dir=REPLAY, output_dir=output) == output.resolve()
    before = {
        path.name: path.read_bytes() for path in output.iterdir() if path.is_file()
    }
    assert materialize(replay_dir=REPLAY, output_dir=output) == output.resolve()
    assert before == {
        path.name: path.read_bytes() for path in output.iterdir() if path.is_file()
    }
    assessment = json.loads((output / "orthogonal_assessment.json").read_text())
    assert assessment["summary"] == {"family_count": 232, "statement_count": 3562}

    (output / "orthogonal_coverage_report.json").write_text("{}\n")
    with pytest.raises(FileExistsError, match="choose a new"):
        materialize(replay_dir=REPLAY, output_dir=output)
