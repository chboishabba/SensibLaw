"""API package providing route definitions."""

try:  # pragma: no cover - optional dependency
    from .routes import router

    __all__ = ["router"]
except Exception:  # ImportError if FastAPI is missing
    router = None  # type: ignore
    __all__ = ["router"]
