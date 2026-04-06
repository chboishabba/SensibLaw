import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.media_adapter import TextDocumentMediaAdapter
from src.policy.normative_policy_profile import build_normative_policy_extract


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "normative"


def test_build_normative_policy_extract_emits_statement_and_queries():
    adapter = TextDocumentMediaAdapter(source_artifact_ref="iso-excerpt-pack")
    canonical = adapter.adapt(
        "<p>4 The organisation must document the process if section 15 applies.</p>"
    )
    segment_id = canonical.segments[0].segment_id
    unit_id = f"{segment_id}:unit:0"

    extract = build_normative_policy_extract(
        canonical,
        ingest_receipt={"source_artifact_ref": "iso-excerpt-pack"},
    )

    assert extract["schema_version"] == "sl.normative_policy_extract.v0_1"
    assert extract["parse_profile"] == "normative_policy"
    assert extract["text_id"] == canonical.text_id
    assert extract["policy_statements"] == [
        {
            "statement_id": f"{canonical.text_id}:policy_statement:4",
            "text": "4 The organisation must document the process if section 15 applies.",
            "heading": "The organisation must document the process if section 15 applies.",
            "section_number": "4",
            "modality": "must",
            "conditions": ["if"],
            "references": [
                {
                    "work": "this_act",
                    "section": "section",
                    "pinpoint": "15",
                    "citation_text": "section 15",
                    "glossary_id": None,
                }
            ],
            "text_ref": {
                "text_id": canonical.text_id,
                "segment_id": segment_id,
                "unit_id": unit_id,
                "envelope_id": extract["envelope_id"],
            },
        }
    ]
    assert extract["ir_queries"] == [
        {
            "query_id": f"{canonical.text_id}:ir_query:modality",
            "query_kind": "modality_check",
            "prompt": "What obligation or permission is stated in: 4 The organisation must document the process if section 15 applies.",
            "statement_id": f"{canonical.text_id}:policy_statement:4",
            "text_ref": {
                "text_id": canonical.text_id,
                "segment_id": segment_id,
                "unit_id": unit_id,
                "envelope_id": extract["envelope_id"],
            },
        },
        {
            "query_id": f"{canonical.text_id}:ir_query:reference:0",
            "query_kind": "reference_lookup",
            "prompt": "Resolve the cited reference 'section 15'.",
            "reference": {
                "work": "this_act",
                "section": "section",
                "pinpoint": "15",
                "citation_text": "section 15",
                "glossary_id": None,
            },
            "text_ref": {
                "text_id": canonical.text_id,
                "segment_id": segment_id,
                "unit_id": unit_id,
                "envelope_id": extract["envelope_id"],
            },
        },
    ]


def test_build_normative_policy_extract_accepts_real_iso_excerpt_pack_fixture():
    payload = json.loads((FIXTURES / "iso_42001_excerpt_pack_v1.json").read_text())
    adapter = TextDocumentMediaAdapter(source_artifact_ref="iso-42001-pack")
    canonical = adapter.adapt(payload)

    extract = build_normative_policy_extract(
        canonical,
        ingest_receipt={"source_artifact_ref": "iso-42001-pack"},
    )

    assert canonical.provenance["document_ref"] == "iso_42001"
    assert canonical.provenance["source_subtype"] == "excerpt_pack"
    assert canonical.provenance["clause_refs"] == ["4"]
    assert extract["parse_profile"] == "normative_policy"
    assert len(extract["policy_statements"]) == 1
    assert extract["policy_statements"][0]["modality"] == "must"
    assert extract["policy_statements"][0]["section_number"] == "4"
    assert extract["ir_queries"]


def test_build_normative_policy_extract_accepts_second_real_iso_excerpt_pack_fixture():
    payload = json.loads((FIXTURES / "iso_42001_excerpt_pack_v2.json").read_text())
    adapter = TextDocumentMediaAdapter(source_artifact_ref="iso-42001-pack-v2")
    canonical = adapter.adapt(payload)

    extract = build_normative_policy_extract(
        canonical,
        ingest_receipt={"source_artifact_ref": "iso-42001-pack-v2"},
    )

    assert canonical.provenance["document_ref"] == "iso_42001"
    assert canonical.provenance["source_subtype"] == "excerpt_pack"
    assert canonical.provenance["clause_refs"] == ["5"]
    assert extract["parse_profile"] == "normative_policy"
    assert extract["policy_statements"] == [
        {
            "statement_id": f"{canonical.text_id}:policy_statement:5",
            "text": "5 The organisation shall maintain records subject to section 9.",
            "heading": "The organisation shall maintain records subject to section 9.",
            "section_number": "5",
            "modality": "shall",
            "conditions": ["subject to"],
            "references": [
                {
                    "work": "this_act",
                    "section": "section",
                    "pinpoint": "9",
                    "citation_text": "section 9",
                    "glossary_id": None,
                }
            ],
            "text_ref": {
                "text_id": canonical.text_id,
                "segment_id": canonical.segments[0].segment_id,
                "unit_id": f"{canonical.segments[0].segment_id}:unit:0",
                "envelope_id": extract["envelope_id"],
            },
        }
    ]
    assert extract["ir_queries"] == [
        {
            "query_id": f"{canonical.text_id}:ir_query:modality",
            "query_kind": "modality_check",
            "prompt": "What obligation or permission is stated in: 5 The organisation shall maintain records subject to section 9.",
            "statement_id": f"{canonical.text_id}:policy_statement:5",
            "text_ref": {
                "text_id": canonical.text_id,
                "segment_id": canonical.segments[0].segment_id,
                "unit_id": f"{canonical.segments[0].segment_id}:unit:0",
                "envelope_id": extract["envelope_id"],
            },
        },
        {
            "query_id": f"{canonical.text_id}:ir_query:reference:0",
            "query_kind": "reference_lookup",
            "prompt": "Resolve the cited reference 'section 9'.",
            "reference": {
                "work": "this_act",
                "section": "section",
                "pinpoint": "9",
                "citation_text": "section 9",
                "glossary_id": None,
            },
            "text_ref": {
                "text_id": canonical.text_id,
                "segment_id": canonical.segments[0].segment_id,
                "unit_id": f"{canonical.segments[0].segment_id}:unit:0",
                "envelope_id": extract["envelope_id"],
            },
        },
    ]
