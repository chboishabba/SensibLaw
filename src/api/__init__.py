"""API package providing FastAPI application and route definitions."""

from .sample_routes import app

try:  # pragma: no cover - optional dependency
    from .routes import router
except Exception:  # ImportError if FastAPI is missing
    router = None  # type: ignore

__all__ = ["app", "router"]

