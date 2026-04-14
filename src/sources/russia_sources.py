from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class RussianLegalSource:
    source_id: str
    source_label: str
    name: str
    document_type: str
    jurisdiction: str
    summary: str
    url: str
    canonical_query_keys: tuple[str, ...]
    authority_layer: str
    language: str = "ru"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def build_source_payload(self, focus: str) -> dict[str, object]:
        return {
            "source_label": self.source_label,
            "focus": focus,
            "metadata": {
                "source_id": self.source_id,
                "document_type": self.document_type,
                "jurisdiction": self.jurisdiction,
                "authority_layer": self.authority_layer,
                "portal_url": self.url,
                "canonical_query_keys": list(self.canonical_query_keys),
                "language": self.language,
            },
        }


def canonical_russian_legal_sources() -> list[RussianLegalSource]:
    return [
        RussianLegalSource(
            source_id="ru_constitution",
            source_label="russian.constitution",
            name="Constitution of the Russian Federation",
            document_type="constitution",
            jurisdiction="Russian Federation",
            summary="Supreme constitutional text establishing federal structure and fundamental rights.",
            url="http://www.constitution.ru/en/10003000/",  # english translation page, deterministic.
            canonical_query_keys=("article", "clause"),
            authority_layer="constitutional",
        ),
        RussianLegalSource(
            source_id="ru_federal_code_1",
            source_label="russian.federal_law_1",
            name="Federal Law No. 44-FZ on the Contract System",
            document_type="federal_law",
            jurisdiction="Russian Federation",
            summary="Federal procurement code regulating state contracting procedures.",
            url="http://www.consultant.ru/document/cons_doc_LAW_198191/",
            canonical_query_keys=("article",),
            authority_layer="federal_law",
        ),
        RussianLegalSource(
            source_id="ru_federal_code_2",
            source_label="russian.federal_law_2",
            name="Federal Law No. 59-FZ on the Procedure for Considering Appeals",
            document_type="federal_law",
            jurisdiction="Russian Federation",
            summary="Defines administration of citizen appeals to state organs and courts.",
            url="http://www.consultant.ru/document/cons_doc_LAW_170065/",
            canonical_query_keys=("article",),
            authority_layer="federal_law",
        ),
        RussianLegalSource(
            source_id="ru_const_court",
            source_label="russian.constitutional_court",
            name="Constitutional Court Interpretive Rulings",
            document_type="interpretation",
            jurisdiction="Russian Federation",
            summary="Selected Constitutional Court decisions interpreting constitutional provisions.",
            url="http://www.ksrf.ru/ru/Decision/Search/",
            canonical_query_keys=("decision-number", "paragraph"),
            authority_layer="constitutional_court",
        ),
        RussianLegalSource(
            source_id="ru_lower_court_sample",
            source_label="russian.lower_court",
            name="Moscow District Court Highlights",
            document_type="lower_court",
            jurisdiction="Moscow",
            summary="Representative lower-court holdings with statutory interpretation cues.",
            url="http://www.mos-gorsud.ru/court/",
            canonical_query_keys=("case-number",),
            authority_layer="lower_court",
            language="ru",
        ),
    ]


def canonical_russian_source_payloads(focus: str) -> list[dict[str, object]]:
    return [source.build_source_payload(focus) for source in canonical_russian_legal_sources()]
