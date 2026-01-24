from __future__ import annotations

from pathlib import Path
from typing import Iterable

from hypothesis import HealthCheck, settings
import pytest

from src.pdf_ingest import build_document, extract_pdf_text


@pytest.fixture(scope="session")
def native_title_nsw_pdf() -> Path:
    return Path("Native Title (New South Wales) Act 1994 (NSW).pdf")


@pytest.fixture(scope="session")
def native_title_nsw_doc(native_title_nsw_pdf: Path):
    pages = list(extract_pdf_text(native_title_nsw_pdf))
    return build_document(pages, native_title_nsw_pdf)


def _iter_provisions(provisions: Iterable) -> Iterable:
    for provision in provisions:
        yield provision
        children = getattr(provision, "children", None) or []
        yield from _iter_provisions(children)


def iter_refs(doc) -> Iterable:
    """Yield reference-like objects tolerant of dict/tuple/obj shapes."""

    for provision in _iter_provisions(getattr(doc, "provisions", []) or []):
        for ref in getattr(provision, "references", []) or []:
            if hasattr(ref, "work"):
                yield ref
            elif isinstance(ref, (list, tuple)):
                work = ref[0] if ref else None
                section = ref[1] if len(ref) > 1 else None
                pinpoint = ref[2] if len(ref) > 2 else None
                yield type("R", (), {"work": work, "section": section, "pinpoint": pinpoint, "source": None})()
            elif isinstance(ref, dict):
                yield type("R", (), ref)()

settings.register_profile(
    "ci",
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile("ci")
