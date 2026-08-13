"""Finite cue matching over numeric SymbolIds only.

The compiler turns a finite pattern set into a total DFA over the pattern
alphabet.  Scan cost is therefore one state transition per input symbol plus one
charge per emitted match: O(N + matches) in the explicit charged-work model.
No regex or human-text comparison appears in the scan path.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

SymbolId = int
PatternId = int


@dataclass(frozen=True, slots=True)
class NumericCueMatch:
    pattern_id: PatternId
    end_ordinal: int


@dataclass(frozen=True, slots=True)
class NumericAutomatonReceipt:
    input_symbols: int
    match_count: int
    work_units: int

    @property
    def linear_plus_matches_bound(self) -> int:
        return self.input_symbols + self.match_count

    def assert_within_contract(self) -> None:
        if self.work_units > self.linear_plus_matches_bound:
            raise AssertionError(
                "numeric cue automaton exceeded N + matches charged-work contract"
            )


@dataclass(frozen=True, slots=True)
class NumericCueScan:
    matches: tuple[NumericCueMatch, ...]
    receipt: NumericAutomatonReceipt


class NumericCueAutomaton:
    """Aho-Corasick-derived total DFA over integer symbols.

    Failure links are consumed at build time to produce total transition rows for
    the finite pattern alphabet.  Runtime scanning never walks failure links.
    """

    def __init__(self, patterns: Mapping[PatternId, Sequence[SymbolId]]) -> None:
        if not patterns:
            raise ValueError("at least one numeric cue pattern is required")
        normalized: dict[PatternId, tuple[SymbolId, ...]] = {}
        for pattern_id, symbols in patterns.items():
            word = tuple(int(symbol) for symbol in symbols)
            if not word:
                raise ValueError(f"pattern {pattern_id} is empty")
            if any(symbol < 0 for symbol in word):
                raise ValueError("SymbolIds must be non-negative integers")
            normalized[int(pattern_id)] = word

        goto: list[dict[SymbolId, int]] = [{}]
        output: list[list[PatternId]] = [[]]
        alphabet: set[SymbolId] = set()

        for pattern_id, word in normalized.items():
            state = 0
            for symbol in word:
                alphabet.add(symbol)
                next_state = goto[state].get(symbol)
                if next_state is None:
                    next_state = len(goto)
                    goto[state][symbol] = next_state
                    goto.append({})
                    output.append([])
                state = next_state
            output[state].append(pattern_id)

        failure = [0] * len(goto)
        queue: deque[int] = deque()
        for state in goto[0].values():
            queue.append(state)

        while queue:
            state = queue.popleft()
            for symbol, target in goto[state].items():
                queue.append(target)
                fallback = failure[state]
                while fallback and symbol not in goto[fallback]:
                    fallback = failure[fallback]
                failure[target] = goto[fallback].get(symbol, 0)
                output[target].extend(output[failure[target]])

        ordered_alphabet = tuple(sorted(alphabet))
        total: list[dict[SymbolId, int]] = []
        for state in range(len(goto)):
            row: dict[SymbolId, int] = {}
            for symbol in ordered_alphabet:
                cursor = state
                while cursor and symbol not in goto[cursor]:
                    cursor = failure[cursor]
                row[symbol] = goto[cursor].get(symbol, 0)
            total.append(row)

        self._patterns = normalized
        self._alphabet = frozenset(alphabet)
        self._transition = tuple(total)
        self._output = tuple(tuple(items) for items in output)

    @property
    def state_count(self) -> int:
        return len(self._transition)

    @property
    def pattern_count(self) -> int:
        return len(self._patterns)

    def scan(self, symbols: Iterable[SymbolId]) -> NumericCueScan:
        state = 0
        input_count = 0
        matches: list[NumericCueMatch] = []
        for ordinal, raw_symbol in enumerate(symbols):
            symbol = int(raw_symbol)
            input_count += 1
            if symbol < 0:
                raise ValueError("SymbolIds must be non-negative integers")
            state = self._transition[state].get(symbol, 0)
            for pattern_id in self._output[state]:
                matches.append(NumericCueMatch(pattern_id, ordinal))

        receipt = NumericAutomatonReceipt(
            input_symbols=input_count,
            match_count=len(matches),
            work_units=input_count + len(matches),
        )
        receipt.assert_within_contract()
        return NumericCueScan(tuple(matches), receipt)
