from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class USJurisdiction:
    code: str
    label: str
    type: str
    sovereign: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def canonical_us_jurisdictions() -> list[dict[str, str]]:
    jurisdictions: Iterable[USJurisdiction] = (
        USJurisdiction(code="US.FED", label="United States Federation", type="federal", sovereign="US"),
        USJurisdiction(code="US.CA", label="California", type="state", sovereign="US"),
        USJurisdiction(code="US.NY", label="New York", type="state", sovereign="US"),
        USJurisdiction(code="US.TX", label="Texas", type="state", sovereign="US"),
        USJurisdiction(code="US.FL", label="Florida", type="state", sovereign="US"),
        USJurisdiction(code="US.PR", label="Puerto Rico", type="territory", sovereign="US"),
        USJurisdiction(code="US.GU", label="Guam", type="territory", sovereign="US"),
        USJurisdiction(code="US.VI", label="U.S. Virgin Islands", type="territory", sovereign="US"),
        USJurisdiction(code="US.AS", label="American Samoa", type="territory", sovereign="US"),
    )
    return [jurisdiction.to_dict() for jurisdiction in jurisdictions]
