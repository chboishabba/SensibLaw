import json
import sys
from pathlib import Path

# This mock represents the pipeline:
# 1. SL extracts the text facts.
# 2. SL matches "Woolworths" to a known entity and looks up its Wikidata Q-ID (Q327333).
# 3. We pull the "instance of" (P31) property from Wikidata: Q180846 (supermarket).

SL_FACTS = [
    {
        "id": "f1",
        "type": "event_occurred",
        "event_id": "slip_event",
        "attributes": {"subject": "Alice", "location": "woolworths", "cause": "wet_floor"},
        "provenance": {"source": "sentence_1"},
        "confidence": "asserted"
    },
    {
        "id": "f2",
        "type": "condition",
        "condition_id": "wet_floor",
        "attributes": {"location": "woolworths", "time": "t0"},
        "provenance": {"source": "sentence_2"},
        "confidence": "asserted"
    },
    {
        "id": "f3",
        "type": "event_occurred",
        "event_id": "mop_event",
        "attributes": {"agent": "Bob", "time": "t0 - 10min"},
        "provenance": {"source": "sentence_2"},
        "confidence": "asserted"
    },
    {
        "id": "f4",
        "type": "not_condition",
        "condition_id": "displayed_warning_sign",
        "attributes": {"location": "woolworths", "time": "t0"},
        "provenance": {"source": "sentence_3"},
        "confidence": "asserted"
    },
    {
        "id": "f5",
        "type": "knowledge",
        "attributes": {"agent": "Bob", "knows_about": "wet_floor", "time": "t0"},
        "provenance": {"source": "sentence_4"},
        "confidence": "asserted"
    },
    {
        "id": "f6",
        "type": "event_occurred",
        "event_id": "injury_event",
        "attributes": {"victim": "Alice", "injury_type": "broken_wrist", "caused_by": "slip_event"},
        "provenance": {"source": "sentence_5"},
        "confidence": "asserted"
    }
]

WIKIDATA_ENRICHMENT = [
    {
        "entity": "woolworths",
        "wikidata_id": "Q327",
        "properties": [
            {"property_id": "wdt:P31", "property_label": "instance_of", "value_id": "wd:Q180846", "value_label": "supermarket"}
        ],
        "provenance": {"source": "wikidata_sparql_lookup"}
    }
]

def main():
    if len(sys.argv) < 2:
        print("Usage: python wikidata_extract.py <input.txt>")
        sys.exit(1)
        
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"File not found: {input_file}")
        sys.exit(1)

    output_path = input_file.parent / "wikidata_sl_output.json"
    with open(output_path, "w") as f:
        json.dump({"facts": SL_FACTS, "wikidata_enrichment": WIKIDATA_ENRICHMENT}, f, indent=2)
    print(f"Deterministically extracted structured facts + Wikidata enrichment to {output_path}")

if __name__ == "__main__":
    main()
