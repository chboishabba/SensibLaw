"""FastAPI application exposing the corrections ledger."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

try:  # pragma: no cover - optional dependency shim
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    from pydantic_stub import BaseModel

from src.repro.ledger import LedgerEntry, ledger
from sensiblaw.api.routes import router as api_router

app = FastAPI(title="Corrections Ledger")
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")
app.include_router(api_router)


class Entry(BaseModel):
    """Pydantic model for incoming entries."""

    name: str
    message: str


@app.post("/ledger")
def add_entry(entry: Entry) -> dict[str, str]:
    """Store a new entry and return a confirmation message."""
    ledger.add_entry(LedgerEntry(**entry.model_dump()))
    return {"status": "ok"}


@app.get("/ledger")
def list_entries() -> list[LedgerEntry]:
    """Return the list of stored entries."""
    return ledger.list_entries()
