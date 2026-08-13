"""Compact codec for parent-relative eight-way refinement addresses.

Each relative child choice is 0..7 and therefore carries exactly three bits.
This codec bit-packs those address digits.  It does not claim that a whole PNF
cell, its provenance, or its semantic payload occupies three bits/one byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class OctantCodecReceipt:
    step_count: int
    encoded_bytes: int

    @property
    def information_bits(self) -> int:
        return self.step_count * 3

    @property
    def minimum_bytes(self) -> int:
        return (self.information_bits + 7) // 8


def pack_octants(steps: Iterable[int]) -> tuple[bytes, OctantCodecReceipt]:
    values = tuple(int(step) for step in steps)
    if any(step < 0 or step > 7 for step in values):
        raise ValueError("relative octant digits must be in 0..7")

    accumulator = 0
    bit_count = 0
    output = bytearray()
    for step in values:
        accumulator |= step << bit_count
        bit_count += 3
        while bit_count >= 8:
            output.append(accumulator & 0xFF)
            accumulator >>= 8
            bit_count -= 8
    if bit_count:
        output.append(accumulator & 0xFF)

    receipt = OctantCodecReceipt(len(values), len(output))
    if receipt.encoded_bytes != receipt.minimum_bytes:
        raise AssertionError("relative octant codec is not bit-density exact")
    return bytes(output), receipt


def unpack_octants(payload: bytes, step_count: int) -> tuple[int, ...]:
    if step_count < 0:
        raise ValueError("step_count must be non-negative")
    expected_bytes = (step_count * 3 + 7) // 8
    if len(payload) != expected_bytes:
        raise ValueError(
            f"expected {expected_bytes} bytes for {step_count} octants; got {len(payload)}"
        )

    accumulator = 0
    bit_count = 0
    byte_ordinal = 0
    values: list[int] = []
    for _ in range(step_count):
        while bit_count < 3:
            accumulator |= payload[byte_ordinal] << bit_count
            byte_ordinal += 1
            bit_count += 8
        values.append(accumulator & 0b111)
        accumulator >>= 3
        bit_count -= 3
    return tuple(values)
