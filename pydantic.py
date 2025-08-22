"""Minimal stubs for :mod:`pydantic` used in tests."""

from __future__ import annotations


class BaseModel:  # pragma: no cover - minimal behaviour
    pass


def Field(default, **kwargs):  # pragma: no cover - simple stub
    return default
