"""Generate sample act and judgment documents in data/corpus/.

This helper script illustrates how to use the Document model to
produce JSON files that comply with the project schema.
"""

from datetime import date
from src.models.document import Document, DocumentMetadata


def create_sample_act() -> None:
    metadata = DocumentMetadata(
        jurisdiction="Sample State",
        citation="Sample Act 2024",
        date=date(2024, 1, 1),
        lpo_tags=["sample"],
        cco_tags=["demo"],
        cultural_flags=["test"],
    )
    doc = Document(metadata=metadata, body="Section 1: Sample act text.")
    with open("data/corpus/sample_act.json", "w") as f:
        f.write(doc.to_json())


def create_sample_judgment() -> None:
    metadata = DocumentMetadata(
        jurisdiction="Sample Jurisdiction",
        citation="Sample v Example [2024] EX 1",
        date=date(2024, 1, 1),
        court="Sample Court",
        lpo_tags=["sample"],
        cco_tags=["demo"],
        cultural_flags=["test"],
    )
    doc = Document(
        metadata=metadata,
        body="The court held sample principles in this illustrative judgment.",
    )
    with open("data/corpus/sample_judgment.json", "w") as f:
        f.write(doc.to_json())


if __name__ == "__main__":
    create_sample_act()
    create_sample_judgment()
    print("Sample documents written to data/corpus/.")
