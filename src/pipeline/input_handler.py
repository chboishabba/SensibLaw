"""Utilities for handling user input for the processing pipeline."""
from __future__ import annotations

from typing import List, TypedDict


class StoryNode(TypedDict, total=False):
    """A minimal representation of a node within a story graph."""

    text: str


class StoryGraph(TypedDict, total=False):
    """A lightweight story graph structure.

    Only the pieces required for `parse_input` are represented here. A
    StoryGraph consists of a list of nodes where each node may contain some
    textual description under the `text` key.
    """

    nodes: List[StoryNode]


def parse_input(query: str | StoryGraph) -> str:
    """Flatten different query types into raw text.

    Parameters
    ----------
    query:
        The user supplied query which may either be a free-form string or a
        `StoryGraph` structure.

    Returns
    -------
    str
        The textual representation of the query.
    """
    if isinstance(query, str):
        return query

    # Extract text from each node of the story graph, ignoring missing fields
    nodes = query.get("nodes", [])
    parts = [n.get("text", "") for n in nodes]
    return " ".join(p for p in parts if p)


__all__ = ["StoryGraph", "parse_input"]
