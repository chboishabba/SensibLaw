from __future__ import annotations

import pytest

from src.policy.numeric_cue_automaton import NumericCueAutomaton
from src.policy.relative_octant_codec import pack_octants, unpack_octants
from src.policy.world_identifier import WorldProvider, parse_wikidata_qid


def test_numeric_cue_automaton_handles_overlaps_without_text_or_regex() -> None:
    automaton = NumericCueAutomaton({10: (1, 2), 20: (2, 3), 30: (1, 2, 3)})
    result = automaton.scan((1, 2, 3, 99, 1, 2))
    assert [(match.pattern_id, match.end_ordinal) for match in result.matches] == [
        (10, 1),
        (30, 2),
        (20, 2),
        (10, 5),
    ]
    assert result.receipt.work_units == result.receipt.input_symbols + result.receipt.match_count
    result.receipt.assert_within_contract()


def test_numeric_cue_automaton_rejects_non_numeric_negative_symbol_ids() -> None:
    automaton = NumericCueAutomaton({1: (1, 2)})
    with pytest.raises(ValueError, match="non-negative"):
        automaton.scan((1, -1, 2))


def test_relative_octant_codec_roundtrips_at_three_bits_per_step() -> None:
    steps = tuple(range(8)) * 5
    payload, receipt = pack_octants(steps)
    assert receipt.information_bits == len(steps) * 3
    assert receipt.encoded_bytes == (len(steps) * 3 + 7) // 8
    assert unpack_octants(payload, len(steps)) == steps


def test_relative_octant_digit_is_not_a_whole_cell_claim() -> None:
    payload, receipt = pack_octants((7,))
    assert payload == b"\x07"
    assert receipt.encoded_bytes == 1
    # The codec covers the relative address digit only; no PNF payload/provenance
    # fields exist in this codec and therefore no whole-cell size claim follows.


def test_wikidata_qid_is_parsed_once_to_numeric_provider_payload() -> None:
    identifier = parse_wikidata_qid("Q12345")
    assert identifier.provider is WorldProvider.WIKIDATA
    assert identifier.numeric_id == 12345
    with pytest.raises(ValueError):
        parse_wikidata_qid("Springfield")
