import json
import argparse
from typing import List, Dict

Document = Dict[str, str]


def load_documents(path: str) -> List[Document]:
    """Load documents from a JSON file.

    The file should contain a list of objects with ``title``, ``citation`` and
    ``content`` fields.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_documents(
    docs: List[Document],
    citation: str | None = None,
    title: str | None = None,
    keyword: str | None = None,
) -> List[Document]:
    """Return documents matching the given filter."""
    if citation:
        return [d for d in docs if d.get("citation") == citation]
    if title:
        return [d for d in docs if d.get("title") == title]
    if keyword:
        kw = keyword.lower()
        return [
            d
            for d in docs
            if kw in d.get("title", "").lower()
            or kw in d.get("content", "").lower()
        ]
    return docs


def render_document(doc: Document) -> str:
    """Format a document for terminal display."""
    title = doc.get("title", "Untitled")
    citation = doc.get("citation", "")
    content = doc.get("content", "")
    return f"{title} ({citation})\n{content}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="View stored documents")
    parser.add_argument("path", help="Path to JSON document file")
    parser.add_argument("--citation", help="Select document by citation")
    parser.add_argument("--title", help="Select document by title")
    parser.add_argument("--search", help="Keyword to filter documents")
    args = parser.parse_args()

    docs = load_documents(args.path)
    results = filter_documents(docs, args.citation, args.title, args.search)
    if not results:
        print("No documents found.")
        return
    for doc in results:
        print(render_document(doc))


if __name__ == "__main__":
    main()
