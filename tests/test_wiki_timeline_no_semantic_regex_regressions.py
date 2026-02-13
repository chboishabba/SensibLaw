from __future__ import annotations

import re
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wiki_timeline_aoo_extract.py"


def _source() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_reported_subject_regex_injector_not_present() -> None:
    src = _source()
    assert "REPORTED_SUBJECT_RE" not in src
    assert "reported_subject_re" not in src.lower()


def test_reported_cautioned_sentence_family_regex_branch_not_present() -> None:
    src = _source()
    assert not re.search(r're\.search\(r"[^"\n]*\\breported\\b[^"\n]*",\s*parse_text', src)
    assert not re.search(r're\.search\(r"[^"\n]*\\bcautioned\\b[^"\n]*",\s*parse_text', src)


def test_dependency_chain_path_is_present() -> None:
    src = _source()
    assert "DEFAULT_COMMUNICATION_CHAIN_CONFIG" in src
    assert "_extract_communication_chain_steps" in src
    assert "_profile_communication_chain_config" in src
