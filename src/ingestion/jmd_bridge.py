from __future__ import annotations

from typing import Any


def _token_count(text: str) -> int:
    return len([token for token in text.split() if token])


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def build_jmd_sl_ingest_from_runtime_object(runtime_object: dict[str, Any]) -> dict[str, Any]:
    obj = runtime_object["object"]
    erdfa = obj.get("erdfa", {})
    content_ref = obj["content_ref"]
    provenance = obj.get("provenance", {})

    return {
        "bridge_version": "jmd.sl.ingest.v1",
        "objects": [
            {
                "object_id": obj["object_id"],
                "object_type": obj.get("object_type", "shard"),
                "content_type": obj.get("content_type", "text/plain; charset=utf-8"),
                "text": obj["text"],
                "content_ref": content_ref,
                "erdfa": {
                    "provider": erdfa.get("provider", "erdfa-publish-rs"),
                    "shard_id": erdfa.get("shard_id"),
                    "cid": erdfa.get("cid"),
                    "component_kind": erdfa.get("component_kind", "text"),
                    "parent_refs": list(erdfa.get("parent_refs") or []),
                    "link_refs": list(erdfa.get("link_refs") or []),
                },
                "provenance": {
                    "source": provenance.get("source", "pastebin"),
                    "captured_at": provenance.get("captured_at", runtime_object.get("resolved_at")),
                },
                "reserved_commitments": {
                    "corpus_root": None,
                    "pipeline_id": None,
                    "params_hash": None,
                    "metric_commitment": None,
                    "score_commitment": None,
                },
            }
        ],
    }


def build_sl_jmd_overlay_from_runtime_object(runtime_object: dict[str, Any]) -> dict[str, Any]:
    obj = runtime_object["object"]
    erdfa = obj.get("erdfa", {})
    shard_id = erdfa.get("shard_id") or obj["object_id"].split(":")[-1]
    anchor_id = f"sl:anchor:{shard_id}:body"
    group_id = f"sl:group:{shard_id}:body"
    overlay_id = f"sl:overlay:{shard_id}:body"
    hint_id = f"sl:hint:{shard_id}:body"
    text = obj["text"]

    return {
        "bridge_version": "sl.jmd.overlay.v1",
        "source_object_id": obj["object_id"],
        "anchors": [
            {
                "anchor_id": anchor_id,
                "source_object_id": obj["object_id"],
                "byte_start": 0,
                "byte_end": _byte_len(text),
                "token_start": 0,
                "token_end": _token_count(text),
                "anchored_text": text,
            }
        ],
        "groups": [
            {
                "group_id": group_id,
                "kind": "claim-fragment",
                "anchor_refs": [anchor_id],
            }
        ],
        "overlays": [
            {
                "overlay_id": overlay_id,
                "overlay_kind": "organization_hint",
                "source_object_ids": [obj["object_id"]],
                "anchor_refs": [anchor_id],
                "detail": {
                    "group_id": group_id,
                    "reason": "full body imported from JMD runtime object",
                    "confidence": "advisory",
                },
            }
        ],
        "optimization_hints": [
            {
                "hint_id": hint_id,
                "hint_kind": "shared_fragment_candidate",
                "source_object_ids": [obj["object_id"]],
                "detail": {"group_id": group_id},
            }
        ],
    }


def build_jmd_sl_bridge_artifacts(runtime_object: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "ingest": build_jmd_sl_ingest_from_runtime_object(runtime_object),
        "overlay": build_sl_jmd_overlay_from_runtime_object(runtime_object),
    }
