from datetime import date, datetime
import json

from src.models.document import Document, DocumentMetadata
from src.models.provision import Atom, Provision


def test_document_serialization_round_trip():
    metadata = DocumentMetadata(
        jurisdiction="AU",
        citation="123 ABC",
        date=date(2024, 1, 1),
        court="HCA",
        lpo_tags=["tag1"],
        cco_tags=["tag2"],
        cultural_flags=["flag"],
        canonical_id="canon-1",
        provenance="original source",
        jurisdiction_codes=["AU"],
        ontology_tags={"topic": ["law"]},
        source_url="http://example.com",
        retrieved_at=datetime(2024, 1, 2, 3, 4, 5),
        checksum="checksum",
        licence="CC0",
    )
    atom = Atom(
        type="ontology",
        role="principle",
        party="legislature",
        who_text="The legislature",
        text="principle",
        refs=["ref1"],
        gloss="A guiding principle",
        gloss_metadata={"source": "example"},
        glossary_id=7,
    )
    provision = Provision(
        text="Sample provision",
        identifier="p1",
        principles=["principle"],
        customs=["custom"],
        atoms=[atom],
    )
    document = Document(metadata=metadata, body="Body text", provisions=[provision])

    # Dictionary round trip
    doc_dict = document.to_dict()
    assert doc_dict["metadata"]["date"] == metadata.date.isoformat()
    assert doc_dict["metadata"]["retrieved_at"] == metadata.retrieved_at.isoformat()
    assert Document.from_dict(doc_dict).to_dict() == doc_dict

    # JSON round trip
    json_data = document.to_json()
    assert json.loads(json_data) == doc_dict
    assert Document.from_json(json_data) == document
    round_trip = Document.from_json(json_data)
    assert round_trip.provisions[0].atoms[0] == atom
