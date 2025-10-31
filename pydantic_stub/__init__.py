"""Lightweight fallback for environments without the real Pydantic."""

from typing import Any


class BaseModel:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def Field(default: Any = None, **_: Any) -> Any:
    return default


__all__ = ["BaseModel", "Field"]
