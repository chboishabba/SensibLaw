"""Minimal stubs for the :mod:`fastapi` package used in tests."""

from __future__ import annotations


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class APIRouter:
    def __init__(self) -> None:  # pragma: no cover - behaviour not essential for tests
        pass

    def get(self, *args, **kwargs):
        def deco(fn):
            return fn
        return deco

    def post(self, *args, **kwargs):
        def deco(fn):
            return fn
        return deco


def Query(*args, **kwargs):  # pragma: no cover - simple stub
    return None
