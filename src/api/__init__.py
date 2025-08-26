"""API package providing FastAPI route definitions."""

try:  # pragma: no cover - optional dependency
    from .routes import router
except Exception:  # ImportError if FastAPI is missing
    router = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from .sample_routes import router as sample_router
except Exception:  # ImportError if FastAPI is missing
    sample_router = None  # type: ignore

__all__ = ["router", "sample_router"]

