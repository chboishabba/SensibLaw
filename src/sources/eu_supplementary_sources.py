from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class EUSupplementarySource:
    name: str
    jurisdiction: str
    source_family: str
    base_url: str
    source_kind: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def canonical_eu_supplementary_sources() -> list[dict[str, str]]:
    sources: Iterable[EUSupplementarySource] = (
        EUSupplementarySource(
            name="Court of Justice of the European Union (Curia)",
            jurisdiction="EU",
            source_family="curia",
            base_url="https://curia.europa.eu",
            source_kind="case_law",
        ),
        EUSupplementarySource(
            name="European Central Bank Legal Acts",
            jurisdiction="EU",
            source_family="ecb_legal_acts",
            base_url="https://www.ecb.europa.eu/ecb/legal/html/index.en.html",
            source_kind="monetary_regulation",
        ),
        EUSupplementarySource(
            name="European Commission Legal Documents",
            jurisdiction="EU",
            source_family="ec_commission_legal_docs",
            base_url="https://commission.europa.eu/law/law-topic_en",
            source_kind="commission_legal_docs",
        ),
    )
    return [source.to_dict() for source in sources]
