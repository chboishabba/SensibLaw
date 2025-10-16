"""Shared constants for the SensibLaw Streamlit console."""

from __future__ import annotations

from typing import Dict, List, Tuple

SAMPLE_CASES: Dict[str, str] = {"GLJ Permanent Stay": "glj"}

SAMPLE_STORY_FACTS = {
    "facts": {
        "delay": True,
        "abuse_of_process": True,
        "fair_trial_possible": False,
    }
}

SAMPLE_FRL_PAYLOAD = {
    "results": [
        {
            "id": "Act1",
            "title": "Sample Act",
            "sections": [
                {
                    "number": "1",
                    "title": "Definitions",
                    "body": '"Dog" means a domesticated animal.',
                },
                {
                    "number": "2",
                    "title": "Care",
                    "body": "A person must care for their dog. See section 1.",
                },
            ],
        }
    ]
}

SAMPLE_GRAPH_CASES = {
    "Case#Mabo1992": {
        "title": "Mabo v Queensland (No 2)",
        "court": "HCA",
        "consent_required": False,
    },
    "Case#Wik1996": {
        "title": "Wik Peoples v Queensland",
        "court": "HCA",
        "consent_required": False,
    },
    "Case#Ward2002": {
        "title": "Western Australia v Ward",
        "court": "HCA",
        "consent_required": True,
        "cultural_flags": ["sacred_information"],
    },
}

SAMPLE_GRAPH_EDGES: List[Tuple[str, str, str, float]] = [
    ("Case#Mabo1992", "Case#Wik1996", "followed", 3.0),
    ("Case#Mabo1992", "Case#Ward2002", "distinguished", 1.0),
    ("Case#Wik1996", "Case#Ward2002", "followed", 2.0),
]

SAMPLE_CASE_TREATMENT_METADATA = {
    "followed": {"court": "HCA"},
    "distinguished": {"court": "FCA"},
}

DEFAULT_DB_NAME = "sensiblaw_documents.sqlite"

__all__ = [
    "SAMPLE_CASES",
    "SAMPLE_STORY_FACTS",
    "SAMPLE_FRL_PAYLOAD",
    "SAMPLE_GRAPH_CASES",
    "SAMPLE_GRAPH_EDGES",
    "SAMPLE_CASE_TREATMENT_METADATA",
    "DEFAULT_DB_NAME",
]
