from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from src.ingestion.span_role_hypotheses import build_span_role_hypotheses
from src.ingestion.span_signal_hypotheses import build_span_signal_hypotheses
from src.models.document import Document, DocumentMetadata


ROOT = Path(__file__).resolve().parents[1]


def test_regex_derived_rows_are_lexical_hints_only() -> None:
    doc = Document(
        DocumentMetadata(jurisdiction="AU", citation="Fixture Act", date=date(2026, 6, 5), title="Fixture Act"),
        'In this Act, "Employee" means a person.\n• NOISY HEADING\nText ???',
    )

    records = [item.to_lexical_hint_record() for item in build_span_role_hypotheses(doc)]
    records.extend(item.to_lexical_hint_record() for item in build_span_signal_hypotheses(doc.body))

    assert records
    for record in records:
        assert record["schema"] == "lexical_hint_v1"
        assert record["pnf_candidates"] == []
        assert record["non_authoritative"] is True
        assert record["bounded"] is True
        assert "predicate" not in record
        assert "structural_signature" not in record


def test_lexical_regex_modules_do_not_construct_pnf_directly() -> None:
    lexical_modules = [
        ROOT / "src" / "ingestion" / "span_role_hypotheses.py",
        ROOT / "src" / "ingestion" / "span_signal_hypotheses.py",
    ]

    assert _regex_pnf_offenders(lexical_modules) == []


def test_only_known_transition_target_mixes_regex_and_pnf_construction() -> None:
    offenders = _regex_pnf_offenders(sorted((ROOT / "src").rglob("*.py")))

    assert offenders == [
        "src/sensiblaw/interfaces/shared_reducer.py calls PredicateAtom",
        "src/sensiblaw/interfaces/shared_reducer.py calls collect_canonical_relational_bundle",
        "src/sensiblaw/interfaces/shared_reducer.py imports src.text.residual_lattice",
        "src/sensiblaw/interfaces/shared_reducer.py imports text.residual_lattice",
    ]


def _regex_pnf_offenders(paths: list[Path]) -> list[str]:
    forbidden_import_names = {"PredicatePNF", "PredicateAtom", "pnf_candidate"}
    forbidden_call_names = forbidden_import_names | {
        "build_predicate_index",
        "collect_canonical_relational_bundle",
    }
    offenders: list[str] = []

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports_regex = any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and (
                any(alias.name == "re" for alias in getattr(node, "names", []))
                or (isinstance(node, ast.ImportFrom) and node.module == "re")
            )
            for node in ast.walk(tree)
        )
        if not imports_regex:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(alias.name in forbidden_import_names for alias in node.names):
                offenders.append(f"{path.relative_to(ROOT)} imports {node.module}")
            if isinstance(node, ast.Import) and any(alias.name.endswith(".residual_lattice") for alias in node.names):
                offenders.append(f"{path.relative_to(ROOT)} imports residual_lattice")
            if isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in forbidden_call_names:
                    offenders.append(f"{path.relative_to(ROOT)} calls {name}")

    return sorted(set(offenders))


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None
