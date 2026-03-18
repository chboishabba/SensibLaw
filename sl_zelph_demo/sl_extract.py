import json
import sys
from pathlib import Path

# This script is a deterministic mock for the SL extractor.
# In the real SL architecture, the document parser -> fact lexer would map
# the deterministic spans into this exact structure.
# Here we emit it deterministically to prove the downstream Zelph bridge correctness.

SL_FACTS = [
    {
        "id": "f1",
        "type": "event_occurred",
        "event_id": "slip_event",
        "attributes": {"subject": "Alice", "location": "supermarket", "cause": "wet_floor"},
        "provenance": {"source": "sentence_1"},
        "confidence": "asserted"
    },
    {
        "id": "f2",
        "type": "condition",
        "condition_id": "wet_floor",
        "attributes": {"location": "supermarket", "time": "t0"},
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
        "attributes": {"location": "supermarket", "time": "t0"},
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

def main():
    if len(sys.argv) < 2:
        print("Usage: python sl_extract.py <input.txt>")
        sys.exit(1)
        
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"File not found: {input_file}")
        sys.exit(1)

    # In a full run, we would parse input_file here.
    # We output the SL native JSON format
    output_path = input_file.parent / "sl_output.json"
    with open(output_path, "w") as f:
        json.dump({"facts": SL_FACTS}, f, indent=2)
    print(f"Deterministically extracted structured facts to {output_path}")

if __name__ == "__main__":
    main()
