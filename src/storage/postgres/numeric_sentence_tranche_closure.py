"""Compatibility surface for the promoted E0b sentence-tranche scheduler.

The production implementation lives in ``numeric_sentence_tranche_closure_setwise``.
Keeping this module preserves the established import surface used by streaming
execution and external callers while removing the old per-sentence admission loop.
"""

from src.storage.postgres.numeric_sentence_tranche_closure_setwise import (
    SentenceTrancheClosureReceipt,
    close_sentence_tranche_setwise as close_sentence_tranche,
    drain_sentence_closure_tranches,
)

__all__ = [
    "SentenceTrancheClosureReceipt",
    "close_sentence_tranche",
    "drain_sentence_closure_tranches",
]
