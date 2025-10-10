import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "src.storage.versioned_store" not in sys.modules:
    versioned_store_stub = types.ModuleType("src.storage.versioned_store")
    versioned_store_stub.VersionedStore = None
    sys.modules["src.storage.versioned_store"] = versioned_store_stub

from src.pdf_ingest import GlossaryRegistry, _rules_to_atoms, build_document  # noqa: E402


MULTI_LEVEL_STATUTE_WITH_DEFINITIONS = """Part 1 Preliminary Matters
Division 1 Introductory
1 Definitions
"Authority" includes a board established under this Act.
"Minister" means the person holding office as Minister for Justice.

2 Application of Act
The Minister must not delay action if urgent circumstances exist.
"""


class RecordingRegistry:
    def __init__(self):
        self.entries = []

    def register_definition(self, term, definition, metadata=None):
        term_key = term.lower()
        for index, (existing_term, _, _) in enumerate(self.entries):
            if existing_term.lower() == term_key:
                self.entries[index] = (term, definition, metadata)
                break
        else:
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


class DummyGlossEntry:
    def __init__(self, phrase: str, text: str, metadata=None):
        self.phrase = phrase
        self.text = text
        self.metadata = metadata


def test_scope_metadata_preserved_when_rules_register_terms(monkeypatch):
    registry = GlossaryRegistry()

    expected_scope = [
        {"node_type": "part", "identifier": "1", "heading": "Preliminary Matters"},
        {"node_type": "division", "identifier": "1", "heading": "Introductory"},
        {"node_type": "section", "identifier": "1", "heading": "Definitions"},
    ]

    registry.register_definition(
        "Authority",
        "a board established under this Act.",
        {"scope": expected_scope},
    )

    calls = []

    def fake_lookup(term: str):
        cleaned = term.strip().strip('"“”')
        calls.append(cleaned)
        if "Authority" in cleaned:
            return DummyGlossEntry(
                "Authority",
                "a board established under this Act.",
                {"source": "curated"},
            )
        return None

    monkeypatch.setattr("src.pdf_ingest.lookup_gloss", fake_lookup)

    class DummyRule:
        actor = "Authority"
        party = "Authority"
        who_text = "Authority"
        modality = "must"
        action = "comply"
        conditions = None
        scope = None
        elements = {"subject": ["Authority"]}

    try:
        _rules_to_atoms([DummyRule()], glossary_registry=registry)

        entry = registry.resolve("Authority")
        assert entry is not None, "expected registry entry for 'Authority'"
        assert entry.metadata is not None, "missing metadata for term 'Authority'"
        assert entry.metadata.get("scope") == expected_scope
        assert entry.metadata.get("source") == "curated"
        assert any("Authority" in call for call in calls)
    finally:
        registry.close()
