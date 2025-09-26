import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.pdf_ingest.fixtures import (  # noqa: E402
    MULTI_LEVEL_STATUTE_WITH_DEFINITIONS,
)
from src.pdf_ingest import build_document  # noqa: E402


class RecordingRegistry:
    def __init__(self):
        self.entries = []

    def register_definition(self, term, definition, metadata=None):
        self.entries.append((term, definition, metadata))
        return None

    def resolve(self, term):
        return None

    def resolve_by_definition(self, definition):
        return None


def test_definition_metadata_scope_includes_hierarchy():
    lines = MULTI_LEVEL_STATUTE_WITH_DEFINITIONS.splitlines()
    pages = [
        {
            "page": 1,
            "heading": lines[0],
            "text": "\n".join(lines[1:]),
        }
    ]

    registry = RecordingRegistry()

    build_document(
        pages,
        Path("multi-level-definitions.pdf"),
        glossary_registry=registry,
    )

    assert registry.entries, "expected glossary definitions to be registered"
    assert len(registry.entries) == 2

    metadata_by_term = {term: metadata for term, _, metadata in registry.entries}

    expected_scope = [
        {"node_type": "part", "identifier": "1", "heading": "Preliminary Matters"},
        {"node_type": "division", "identifier": "1", "heading": "Introductory"},
        {"node_type": "section", "identifier": "1", "heading": "Definitions"},
    ]

    for term in ("Authority", "Minister"):
        metadata = metadata_by_term.get(term)
        assert metadata is not None, f"missing metadata for term {term!r}"
        scope = metadata.get("scope")
        assert scope == expected_scope
        assert scope is not expected_scope
