from __future__ import annotations

from pathlib import Path


def test_runtime_consumers_retain_shared_reducer_integration_boundary() -> None:
    suite_root = Path(__file__).resolve().parents[1]
    project_root = suite_root.parent

    forbidden_imports = (
        "from src.text.structure_index import collect_structure_occurrences",
        "from src.text.structure_index import ",
        "from src.text.operational_structure import",
    )

    consumer_roots = [
        suite_root / "src" / "reporting",
        suite_root / "scripts",
        project_root / "StatiBaker" / "sb",
        project_root / "StatiBaker" / "scripts",
        project_root / "tircorder-JOBBIE",
    ]

    offender_paths: list[str] = []
    for root in consumer_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "venv" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if any(marker in text for marker in forbidden_imports):
                offender_paths.append(str(path.relative_to(project_root)))

    assert offender_paths == [], f"Found non-shared reducer imports: {offender_paths}"
