"""Factor cue definitions for distinguishing cases.

Currently contains minimal heuristics for the GLJ permanent stay example.
Each factor ID maps to a regular expression that is searched for within
case paragraphs when comparing a story against a base case.
"""

from __future__ import annotations

from typing import Dict

# Mapping of factor identifiers to regular expression patterns (case-insensitive).
GLJ_PERMANENT_STAY_CUES: Dict[str, str] = {
    # Extent and impact of any prosecutorial delay
    "delay": r"delay",
    # Prejudice resulting from the delay
    "prejudice": r"prejudice",
    # References to evidence being lost or unavailable
    "lost_evidence": r"lost\s+evidence|evidence\s+.*lost",
    # Indicators that continuing would be an abuse of process
    "abuse_indicators": r"abuse",
    # Specific cue used in CLI tests for the GLJ example
    "abuse_of_process": r"held\s*:\s*yes",
}
