from pathlib import Path


ALLOWED = {
    Path("src/text/tokenize_simple.py"),
    Path("src/reports/research_health.py"),
}


def test_tokenize_simple_not_imported_outside_metrics():
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"

    offenders = []
    for path in src_root.rglob("*.py"):
        rel = path.relative_to(repo_root)
        if rel in ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        if "tokenize_simple" in text:
            offenders.append(str(rel))

    assert offenders == [], f"tokenize_simple should not creep beyond metrics modules: {offenders}"
