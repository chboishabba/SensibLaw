from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.pdf_ingest import process_pdf
from src.models.provision import RuleReference

# Ensure src/ is importable during collection (before fixtures run).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(autouse=True)
def prefer_venv_python(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure subprocesses use the project venv and see the src package.

    Many CLI tests shell out with a literal ``python -m src.cli ...``. This fixture
    prefixes PATH with the repo's .venv/bin and sets PYTHONPATH to ``src`` so those
    subprocesses run in the same environment as pytest.
    """

    repo_root = Path(__file__).resolve().parents[1]
    venv_bin = repo_root.parent / ".venv" / "bin"
    path = os.environ.get("PATH", "")
    if venv_bin.exists():
        monkeypatch.setenv("PATH", f"{venv_bin}:{path}")
    monkeypatch.setenv("PYTHONPATH", str(repo_root / "src"))
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))


@dataclass(frozen=True)
class _SimpleRef:
    work: str | None
    section: str | None
    pinpoint: str | None
    citation_text: str | None
    source: str | None = None


def iter_refs(doc):
    """Yield all RuleReference-like objects from a document."""

    def _coerce(ref):
        if isinstance(ref, RuleReference):
            return ref
        if isinstance(ref, (tuple, list)):
            work, section, pinpoint, citation_text, source, *_ = list(ref) + [None] * 5
            return _SimpleRef(work, section, pinpoint, citation_text, source)
        return None

    def _walk(provisions):
        for prov in provisions or []:
            for ref in getattr(prov, "references", []) or []:
                coerced = _coerce(ref)
                if coerced:
                    yield coerced
            for atom in getattr(prov, "rule_atoms", []) or []:
                for ref in getattr(atom, "references", []) or []:
                    coerced = _coerce(ref)
                    if coerced:
                        yield coerced
            yield from _walk(getattr(prov, "children", []) or [])

    yield from _walk(getattr(doc, "provisions", []) or [])


@pytest.fixture(scope="session")
def native_title_nsw_doc():
    pdf = Path("Native Title (New South Wales) Act 1994 (NSW).pdf")
    if not pdf.exists():
        pytest.skip("native title NSW PDF fixture missing")
    doc, _ = process_pdf(pdf, db_path="")
    return doc
