"""Thread-local progress callbacks for one operational document compilation.

The compiler remains usable without instrumentation.  Catalogue workers may install a
callback around one document so deep parser/PNF phases can report live stage and token
coordinates without changing semantic outputs or sharing mutable graph state.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator, Mapping


CompilerProgressCallback = Callable[[Mapping[str, Any]], None]
_CALLBACK: ContextVar[CompilerProgressCallback | None] = ContextVar(
    "sensiblaw_compiler_progress_callback", default=None
)


def emit_compiler_progress(
    *,
    stage: str,
    document_ref: str,
    token_count: int | None = None,
    completed_tokens: int | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    callback = _CALLBACK.get()
    if callback is None:
        return
    payload: dict[str, Any] = {
        "stage": stage,
        "document_ref": document_ref,
    }
    if token_count is not None:
        payload["token_count"] = max(0, int(token_count))
    if completed_tokens is not None:
        payload["completed_tokens"] = max(0, int(completed_tokens))
    if details:
        payload["details"] = dict(details)
    callback(payload)


@contextmanager
def compiler_progress_callback(callback: CompilerProgressCallback | None) -> Iterator[None]:
    token = _CALLBACK.set(callback)
    try:
        yield
    finally:
        _CALLBACK.reset(token)


__all__ = [
    "CompilerProgressCallback",
    "compiler_progress_callback",
    "emit_compiler_progress",
]
