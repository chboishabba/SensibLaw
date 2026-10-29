from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CERTIFIER = ROOT / "scripts" / "certify_e0d_anaphor_delta_projection.py"
MIGRATION = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "180_relation_valued_anaphor_delta_projection.sql"
)


def _assignment(name: str) -> object:
    tree = ast.parse(CERTIFIER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"missing assignment {name}")


def test_e0d_certifier_names_golden_agda_owner_chain() -> None:
    owners = _assignment("FORMAL_OWNER_REFS")
    assert owners == (
        "DASHI.Cognition.PNF.SetwiseGroupedFibreProjectionExact.DeltaFedProjection",
        "DASHI.Cognition.PNF.AffectedBoundaryLocalReductionExact.AffectedLocalReducer",
        "DASHI.Cognition.PNF.SentenceAnaphorSetwiseProjectionExact.SentenceAnaphorProjectionZKPFrame",
    )


def test_e0d_certifier_carries_complete_zkp_frame() -> None:
    frame = _assignment("ZKP_FRAME")
    assert set(frame) == {"O", "R", "C", "S", "L", "P", "G", "F"}
    assert "authority" in frame["O"]
    assert "set-based" in frame["R"]
    assert "self-update" in frame["C"]
    assert "affected" in frame["S"]
    assert "witness identity" in frame["L"]
    assert "resolution" in frame["P"]
    assert "rescanned" in frame["G"]
    assert "remain open" in frame["F"]


def test_migration_180_realizes_relation_delta_and_nonpromotion_boundaries() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "project_numeric_sentence_anaphor_delta" in sql
    assert "REFERENCING OLD TABLE AS prior_region NEW TABLE AS updated_region" in sql
    assert "pg_temp.semantic_pnf_anaphor_delta_source" in sql
    assert "lexical_symbol_id,surface_lexical_symbol_id" in sql
    assert "1,NULL," in sql
    assert "state=LEAST(execution.semantic_pnf_demand.state,1)" in sql
    assert "WITH affected_interface AS MATERIALIZED" in sql
    assert "UPDATE execution.semantic_pnf_demand AS" not in sql
