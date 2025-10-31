import spacy
from spacy.tokens import Doc
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REMOVED_ROOT = False
REMOVED_EMPTY = False
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
    REMOVED_ROOT = True
if "" in sys.path:
    sys.path.remove("")
    REMOVED_EMPTY = True

if REMOVED_EMPTY:
    sys.path.insert(0, "")
if REMOVED_ROOT:
    sys.path.insert(0, str(ROOT))

SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nlp.rules import RuleMatcher


def test_modality_matcher_detects_normative_and_offence_phrases():
    matcher = RuleMatcher(spacy.blank("en"))

    text = (
        "A person must not sell liquor. "
        "A corporation commits the offence of fraud if it falsifies records."
    )

    result = matcher.extract(text)

    assert "must not" in result.modalities
    assert "commits the offence of" in result.modalities


def test_reference_and_penalty_patterns_capture_expected_spans():
    matcher = RuleMatcher(spacy.blank("en"))

    text = "See s 5B of this Act. Maximum penalty: 50 penalty units."

    result = matcher.extract(text)

    assert result.references == ["s 5B", "this Act"]
    assert "50 penalty units" in result.penalties


def test_dependency_matcher_expands_conditional_clause():
    nlp = spacy.blank("en")
    matcher = RuleMatcher(nlp)

    words = [
        "A",
        "person",
        "must",
        "not",
        "enter",
        "the",
        "area",
        "if",
        "they",
        "are",
        "trespassing",
        ".",
    ]
    heads = [1, 4, 4, 4, 4, 6, 4, 10, 10, 10, 4, 4]
    deps = [
        "det",
        "nsubj",
        "aux",
        "neg",
        "ROOT",
        "det",
        "dobj",
        "mark",
        "nsubj",
        "aux",
        "advcl",
        "punct",
    ]
    spaces = [True] * (len(words) - 1) + [False]

    doc = Doc(nlp.vocab, words=words, spaces=spaces, heads=heads, deps=deps)

    result = matcher.extract_from_doc(doc)

    assert "if they are trespassing" in result.conditions
