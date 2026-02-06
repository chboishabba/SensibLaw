from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from sensiblaw.ribbon.lens_dsl import evaluate_rho


@dataclass(frozen=True)
class RibbonSegment:
    seg_id: str
    start_idx: int
    end_idx: int
    mass: float
    width_norm: float


def compute_segments(lens: Dict[str, object], signals: Dict[str, List[float]], boundaries: List[int]) -> List[RibbonSegment]:
    if len(boundaries) < 2:
        raise ValueError("boundaries must include at least start/end")
    rho = evaluate_rho(lens, signals)
    total_mass = sum(rho)

    segments: List[RibbonSegment] = []
    for idx in range(len(boundaries) - 1):
        start = boundaries[idx]
        end = boundaries[idx + 1]
        seg_mass = sum(rho[start:end])
        width = 0.0 if total_mass == 0 else seg_mass / total_mass
        segments.append(
            RibbonSegment(
                seg_id=f"seg-{idx+1}",
                start_idx=start,
                end_idx=end,
                mass=seg_mass,
                width_norm=width,
            )
        )
    return segments


def compute_total_mass(segments: Iterable[RibbonSegment]) -> float:
    return sum(seg.mass for seg in segments)
