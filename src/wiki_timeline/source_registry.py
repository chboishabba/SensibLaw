from __future__ import annotations

from typing import Any


TimelineSourceKey = str
TimelineSourceVariant = str


_SOURCE_CONFIGS: dict[TimelineSourceKey, dict[TimelineSourceVariant, dict[str, str]]] = {
    "gwb": {
        "timeline": {
            "rel_path": "SensibLaw/.cache_local/wiki_timeline_gwb.json",
            "timeline_suffix": "wiki_timeline_gwb.json",
        },
        "aoo": {
            "rel_path": "SensibLaw/.cache_local/wiki_timeline_gwb_aoo.json",
            "timeline_suffix": "wiki_timeline_gwb_aoo.json",
        },
    },
    "gwb_public_bios_v1": {
        "timeline": {
            "rel_path": "SensibLaw/demo/ingest/gwb/public_bios_v1/wiki_timeline_gwb_public_bios_v1.json",
            "timeline_suffix": "wiki_timeline_gwb_public_bios_v1.json",
        },
        "aoo": {
            "rel_path": "SensibLaw/demo/ingest/gwb/public_bios_v1/wiki_timeline_gwb_public_bios_v1_aoo.json",
            "timeline_suffix": "wiki_timeline_gwb_public_bios_v1_aoo.json",
        },
        "aoo_all": {
            "rel_path": "SensibLaw/demo/ingest/gwb/public_bios_v1/wiki_timeline_gwb_public_bios_v1.json",
            "timeline_suffix": "wiki_timeline_gwb_public_bios_v1.json",
        },
    },
    "gwb_corpus_v1": {
        "timeline": {
            "rel_path": "SensibLaw/demo/ingest/gwb/corpus_v1/wiki_timeline_gwb_corpus_v1.json",
            "timeline_suffix": "wiki_timeline_gwb_corpus_v1.json",
        },
        "aoo": {
            "rel_path": "SensibLaw/demo/ingest/gwb/corpus_v1/wiki_timeline_gwb_corpus_v1_aoo.json",
            "timeline_suffix": "wiki_timeline_gwb_corpus_v1_aoo.json",
        },
        "aoo_all": {
            "rel_path": "SensibLaw/demo/ingest/gwb/corpus_v1/wiki_timeline_gwb_corpus_v1.json",
            "timeline_suffix": "wiki_timeline_gwb_corpus_v1.json",
        },
    },
    "hca": {
        "timeline": {
            "rel_path": "SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json",
            "timeline_suffix": "wiki_timeline_hca_s942025_aoo.json",
        },
        "aoo": {
            "rel_path": "SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json",
            "timeline_suffix": "wiki_timeline_hca_s942025_aoo.json",
        },
        "aoo_all": {
            "rel_path": "SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json",
            "timeline_suffix": "wiki_timeline_hca_s942025_aoo.json",
        },
    },
    "legal": {
        "timeline": {
            "rel_path": "SensibLaw/demo/ingest/legal_principles_au_v1/wiki_timeline_legal_principles_au_v1.json",
            "timeline_suffix": "wiki_timeline_legal_principles_au_v1.json",
        },
        "aoo": {
            "rel_path": "SensibLaw/demo/ingest/legal_principles_au_v1/wiki_timeline_legal_principles_au_v1_aoo.json",
            "timeline_suffix": "wiki_timeline_legal_principles_au_v1_aoo.json",
        },
        "aoo_all": {
            "rel_path": "SensibLaw/demo/ingest/legal_principles_au_v1/wiki_timeline_legal_principles_au_v1.json",
            "timeline_suffix": "wiki_timeline_legal_principles_au_v1.json",
        },
    },
    "legal_follow": {
        "timeline": {
            "rel_path": "SensibLaw/demo/ingest/legal_principles_au_v1/follow/wiki_timeline_legal_principles_au_v1_follow.json",
            "timeline_suffix": "wiki_timeline_legal_principles_au_v1_follow.json",
        },
        "aoo": {
            "rel_path": "SensibLaw/demo/ingest/legal_principles_au_v1/follow/wiki_timeline_legal_principles_au_v1_follow_aoo.json",
            "timeline_suffix": "wiki_timeline_legal_principles_au_v1_follow_aoo.json",
        },
        "aoo_all": {
            "rel_path": "SensibLaw/demo/ingest/legal_principles_au_v1/follow/wiki_timeline_legal_principles_au_v1_follow.json",
            "timeline_suffix": "wiki_timeline_legal_principles_au_v1_follow.json",
        },
    },
}


def normalize_source_key(raw: Any, *, fallback: str) -> str:
    key = str(raw or fallback).strip().lower()
    if key in _SOURCE_CONFIGS:
        return key
    return fallback


def source_variant_for_projection(projection: str) -> str:
    if projection == "timeline_view":
        return "timeline"
    return "aoo"


def resolve_source_config(raw: Any, *, projection: str, fallback: str, variant: str | None = None) -> dict[str, str]:
    key = normalize_source_key(raw, fallback=fallback)
    resolved_variant = variant or source_variant_for_projection(projection)
    variant_cfg = _SOURCE_CONFIGS.get(key, {}).get(resolved_variant)
    if not variant_cfg:
        raise KeyError(f"no source config for key={key} variant={resolved_variant}")
    return {"source": key, **variant_cfg}
