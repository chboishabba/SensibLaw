"""HTTP routes exposing sample data via FastAPI."""

from __future__ import annotations

from typing import List, Optional

try:  # pragma: no cover - fallback when FastAPI isn't available
    from fastapi import FastAPI, HTTPException, Query
except Exception:  # pragma: no cover
    # Minimal shims so the module can be imported without FastAPI installed.
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            self.status_code = status_code
            self.detail = detail

    class Query:  # type: ignore[misc]
        def __init__(self, default=None, **_: object) -> None:
            self.default = default

    class FastAPI:  # type: ignore[misc]
        def __init__(self) -> None:
            pass

        def get(self, _path: str):
            def decorator(func):
                return func

            return decorator

from ..sample_data import build_subgraph, get_provision, treatments_for

app = FastAPI()


@app.get("/subgraph")
def api_subgraph(
    node: Optional[List[str]] = Query(None),
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
):
    """Return a subgraph of the sample graph."""
    return build_subgraph(node, limit, offset)


@app.get("/treatment")
def api_treatment(
    doc: str = Query(..., description="Document identifier"),
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
):
    """Return edges involving a document."""
    edges = treatments_for(doc, limit, offset)
    return {"treatments": edges}


@app.get("/provision")
def api_provision(doc: str = Query(...), id: str = Query(...)):
    """Return a provision from the sample documents."""
    prov = get_provision(doc, id)
    if prov is None:
        raise HTTPException(status_code=404, detail="Provision not found")
    return prov


__all__ = ["app", "api_subgraph", "api_treatment", "api_provision"]

