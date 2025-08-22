from __future__ import annotations

from typing import Dict

# Simple ranking for Australian courts. Higher numbers indicate higher courts.
COURT_RANKS: Dict[str, int] = {
    "HCA": 3,      # High Court of Australia
    "FCAFC": 2,   # Full Court of the Federal Court
    "FCA": 1,     # Federal Court of Australia
}


def court_weight(court: str, panel_size: int | float | None = None) -> float:
    """Return a default edge weight for a case from ``court``.

    Parameters
    ----------
    court:
        Abbreviation of the court (e.g., ``"HCA"``).
    panel_size:
        Number of judges on the panel. Defaults to ``1`` when ``None`` or ``0``.

    Returns
    -------
    float
        Computed as ``court_rank * panel_size`` with unknown courts treated as
        rank 0.
    """

    rank = COURT_RANKS.get(court.upper(), 0)
    size = panel_size or 1
    return float(rank) * float(size)


__all__ = ["COURT_RANKS", "court_weight"]
