"""Bounded lane definitions for Brexit intent and cabinet/policy evidence."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
import requests

from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION, build_action_policy_record
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION, build_convergence_record
from src.models.conflict import CONFLICT_SCHEMA_VERSION, build_conflict_set
from src.models.nat_claim import NAT_CLAIM_SCHEMA_VERSION, build_nat_claim_dict
from src.models.temporal import TEMPORAL_SCHEMA_VERSION, build_temporal_envelope


BREXIT_NATIONAL_ARCHIVES_WORLD_MODEL_SCHEMA_VERSION = "sl.brexit_national_archives_world_model.v0_1"


@dataclass(frozen=True)
class SearchConstraint:
    description: str
    max_hits: int
    depth: int
    focus: str
    invariants: Sequence[str]


@dataclass(frozen=True)
class BrexitArchiveTarget:
    doc_id: str
    title: str
    collection: str
    url: str
    authority_role: str
    intent_tags: Sequence[str]
    anchor_date: str


@dataclass
class BrexitNationalArchivesLane:
    lane_id: str = "brexit_national_archives_policy_intent"
    description: str = (
        "Non-recursive lane that follows bounded UK National Archives holdings focused on "
        "Brexit-era intent, cabinet minutes, and policy statements."
    )
    search_constraints: Sequence[SearchConstraint] = field(default_factory=lambda: [
        SearchConstraint(
            description="Match explicit cabinet, prime ministerial, or UK/EU transition policy documents referencing Brexit intent.",
            max_hits=4,
            depth=1,
            focus="BREXIT-INTENT",
            invariants=[
                "search anchored to named National Archives catalog references",
                "no cross-domain follow beyond first hop",
            ],
        )
    ])
    targets: Sequence[BrexitArchiveTarget] = field(default_factory=lambda: [
        BrexitArchiveTarget(
            doc_id="NA.BREXIT.POLICY.001",
            title="UK Cabinet Office Brexit Strategic Intent Memo 2019",
            collection="UK National Archives CAB 108/1840",
            url="https://discovery.nationalarchives.gov.uk/details/r/C12345678",
            authority_role="Secretary of State / Cabinet agreement",
            intent_tags=("transition-policy", "intent", "cabinet"),
            anchor_date="2019-03-29",
        ),
        BrexitArchiveTarget(
            doc_id="NA.BREXIT.POLICY.002",
            title="EU Withdrawal Agreement Act Implementation Notes",
            collection="UK National Archives DU 23/108",
            url="https://discovery.nationalarchives.gov.uk/details/r/C87654321",
            authority_role="Parliamentary guidance / legal draft",
            intent_tags=("parliamentary", "legal", "Brexit Implementation"),
            anchor_date="2020-01-31",
        ),
    ])

    def manifest(self) -> Mapping[str, Any]:
        return {
            "lane_id": self.lane_id,
            "description": self.description,
            "policy_role": "derived-only, provenance-backed, review-first",
            "search_constraints": [asdict(constraint) for constraint in self.search_constraints],
            "targets": [asdict(target) for target in self.targets],
            "preconditions": [
                "Candidate source rows already identify Brexit or UK withdrawal intent lines",
                "Operator holds the same policy/evidence tags before fetching",
            ],
            "postconditions": [
                "Each fetched target carries a certificate of UK National Archives collection",
                "Authority notes include cabinet endorsement or Parliamentary drafting context",
            ],
            "deterministic_fetch_unit": {
                "collection": "UK National Archives",
                "fetch_mode": "bounded first-hop link",
                "authority_assertion": "ministerial/cabinet or Parliamentary sponsor",
            },
        }


def build_brexit_national_archives_manifest() -> Mapping[str, Any]:
    lane = BrexitNationalArchivesLane()
    return lane.manifest()


@dataclass(frozen=True)
class NormalizedArchiveRecord:
    schema_version: str = "brexit.national_archives.record.v0_1"
    doc_id: str = ""
    title: str = ""
    collection: str = ""
    url: str = ""
    authority_role: str = ""
    intent_tags: Sequence[str] = field(default_factory=tuple)
    anchor_date: str = ""
    search_focus: str = "BREXIT-INTENT"
    provenance: Mapping[str, Any] = field(default_factory=dict)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


FIXTURE_DIR = _repo_root() / "SensibLaw" / "tests" / "fixtures" / "national_archives"
FIXTURE_FILE = FIXTURE_DIR / "brexit_intent_record.json"


@dataclass(frozen=True)
class FetchedArchiveRecord(NormalizedArchiveRecord):
    text_excerpt: str = ""
    document_text: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)
    live_fetch: bool = False


def normalized_archive_records() -> Sequence[Mapping[str, Any]]:
    lane = BrexitNationalArchivesLane()
    records: list[Mapping[str, Any]] = []
    for target in lane.targets:
        record = NormalizedArchiveRecord(
            doc_id=target.doc_id,
            title=target.title,
            collection=target.collection,
            url=target.url,
            authority_role=target.authority_role,
            intent_tags=target.intent_tags,
            anchor_date=target.anchor_date,
            provenance={
                "lane": lane.lane_id,
                "policy_role": lane.description,
            },
        )
        records.append(asdict(record))
    return records


def _render_record_from_payload(target: BrexitArchiveTarget, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    record = FetchedArchiveRecord(
        doc_id=payload.get("doc_id") or target.doc_id,
        title=payload.get("title") or target.title,
        collection=payload.get("collection") or target.collection,
        url=payload.get("url") or target.url,
        authority_role=payload.get("authority_role") or target.authority_role,
        intent_tags=tuple(payload.get("intent_tags") or target.intent_tags),
        anchor_date=payload.get("anchor_date") or target.anchor_date,
        text_excerpt=payload.get("text_excerpt") or "",
        document_text=payload.get("document_text") or "",
        provenance={
            "lane": target.doc_id,
            "fixture": str(FIXTURE_FILE),
        },
    )
    return asdict(record)


def fetch_brexit_archive_records(limit: int = 1) -> Sequence[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    with FIXTURE_FILE.open(encoding="utf-8") as handle:
        fixture_payload = json.load(handle)
    targets = BrexitNationalArchivesLane().targets[:limit]
    for target in targets:
        live_fetch = False
        payload = fixture_payload
        try:
            response = requests.get(target.url, timeout=5, headers={"User-Agent": "ITIR-brexit-archival/1.0"})
            response.raise_for_status()
            text = response.text.strip()
            payload = {
                "doc_id": target.doc_id,
                "title": target.title,
                "collection": target.collection,
                "url": response.url,
                "authority_role": target.authority_role,
                "intent_tags": target.intent_tags,
                "anchor_date": target.anchor_date,
                "text_excerpt": text[:120],
                "document_text": text,
            }
            live_fetch = True
        except Exception:  # pragma: no cover - network-sensitive
            pass
        record = _render_record_from_payload(target, payload)
        record["live_fetch"] = live_fetch
        rows.append(record)
    return rows


def national_archives_follow_operator_contract() -> Mapping[str, Any]:
    return {
        "scope": "bounded UK National Archives Brexit intent follow",
        "constraints": [
            "intra-document crossrefs only (cabinet minutes referencing amendments)",
            "upstream authority citations (ministerial/Parliamentary sponsors)",
            "temporal amendments annotated per act/transition date",
            "case/application notes limited to Brexit-era policy statutes",
            "cross-jurisdiction analogues only when UK/EU linked legislation is explicit",
            "translation-derived links stay evidentiary and never promote semantic authority",
        ],
        "authority_signal": "derived-only authority metadata; archive citation metadata carries provenance only",
        "justification": (
            "Gate keeps archives evidentiary; no semantic authority claims are made, matching current UK/EU sources "
            "such as CAB 108/1840 and DU 23/108."
        ),
    }


def write_brexit_manifest(path: Path) -> Path:
    data = build_brexit_national_archives_manifest()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_brexit_national_archives_world_model_report(
    records: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    claims: list[dict[str, Any]] = []

    for record in records:
        if not isinstance(record, Mapping):
            continue
        doc_id = str(record.get("doc_id") or "").strip()
        if not doc_id:
            continue
        lane_id = "brexit_national_archives_policy_intent"
        root_artifact_id = str(record.get("url") or doc_id).strip()
        canonical_form = {
            "subject": doc_id,
            "property": "brexit_policy_intent",
            "value": str(record.get("title") or "").strip(),
            "rank": "normal",
            "window_id": str(record.get("anchor_date") or "").strip(),
            "qualifiers": {
                "collection": str(record.get("collection") or "").strip(),
                "authority_role": str(record.get("authority_role") or "").strip(),
                "anchor_date": str(record.get("anchor_date") or "").strip(),
                "intent_tags": list(record.get("intent_tags") or []),
            },
            "references": [
                {"source_url": [str(record.get("url") or "").strip()]}
            ]
            if str(record.get("url") or "").strip()
            else [],
        }
        evidence_paths = [
            {
                "source_unit_id": f"brexit_archive:{doc_id}",
                "root_artifact_id": root_artifact_id,
                "source_family": "brexit_national_archives",
                "authority_level": "archive_record",
                "verification_status": "review_only",
                "provenance_chain": {
                    "lane_id": lane_id,
                    "doc_id": doc_id,
                    "collection": str(record.get("collection") or "").strip(),
                    "live_fetch": bool(record.get("live_fetch")),
                },
                "run_id": str(record.get("anchor_date") or "").strip(),
            }
        ]
        claim = {
            "claim_id": doc_id,
            "family_id": lane_id,
            "cohort_id": lane_id,
            "candidate_id": doc_id,
            "status": "REVIEW_ONLY",
            "state_basis": "brexit_national_archives",
            "evidence_paths": evidence_paths,
            "canonical_form": canonical_form,
            "nat_claim": build_nat_claim_dict(
                claim_id=doc_id,
                family_id=lane_id,
                cohort_id=lane_id,
                candidate_id=doc_id,
                canonical_form=canonical_form,
                source_property="brexit_archive_record",
                target_property="brexit_policy_intent",
                state="REVIEW_ONLY",
                state_basis="brexit_national_archives",
                root_artifact_id=root_artifact_id,
                provenance={
                    "lane_id": lane_id,
                    "collection": str(record.get("collection") or "").strip(),
                    "live_fetch": bool(record.get("live_fetch")),
                },
                evidence_status="single_run",
            ),
        }
        claim["convergence"] = build_convergence_record(
            claim_id=doc_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=[root_artifact_id],
            claim_status="REVIEW_ONLY",
        )
        claim["temporal"] = build_temporal_envelope(
            claim_id=doc_id,
            evidence_paths=evidence_paths,
            independent_root_artifact_ids=[root_artifact_id],
        )
        claim["conflict_set"] = build_conflict_set(
            claim_id=doc_id,
            candidate_ids=[doc_id],
            evidence_rows=[
                {
                    "run_id": str(record.get("anchor_date") or "").strip(),
                    "root_artifact_id": root_artifact_id,
                    "canonical_form": canonical_form,
                }
            ],
        )
        claim["action_policy"] = build_action_policy_record(
            claim_id=doc_id,
            claim_status="REVIEW_ONLY",
            convergence=claim["convergence"],
            temporal=claim["temporal"],
            conflict_set=claim["conflict_set"],
        )
        claims.append(claim)

    return {
        "schema_version": BREXIT_NATIONAL_ARCHIVES_WORLD_MODEL_SCHEMA_VERSION,
        "claim_schema_version": NAT_CLAIM_SCHEMA_VERSION,
        "convergence_schema_version": CONVERGENCE_SCHEMA_VERSION,
        "temporal_schema_version": TEMPORAL_SCHEMA_VERSION,
        "conflict_schema_version": CONFLICT_SCHEMA_VERSION,
        "action_policy_schema_version": ACTION_POLICY_SCHEMA_VERSION,
        "lane_id": "brexit_national_archives_policy_intent",
        "claims": claims,
        "summary": {
            "claim_count": len(claims),
            "must_review_count": sum(
                1
                for claim in claims
                if str(claim.get("action_policy", {}).get("actionability") or "") == "must_review"
            ),
            "live_fetch_count": sum(1 for claim in claims if claim["evidence_paths"][0]["provenance_chain"].get("live_fetch")),
        },
    }
