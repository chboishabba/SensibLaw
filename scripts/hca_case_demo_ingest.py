#!/usr/bin/env python3
"""Download an HCA case bundle, ingest PDFs, and emit a demo graph pack.

This utility is intentionally bounded and reproducible:
- Downloads only one case page and the document links discovered for that case.
- Runs a second-pass URL discovery from the case page "Documents" table.
- Extracts case-recording Vimeo metadata, captions, and transcript segments.
- Ingests downloaded PDFs and writes a simple graph JSON + DOT.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


SENSIBLAW_ROOT = Path(__file__).resolve().parents[1]
if str(SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(SENSIBLAW_ROOT))

from src.graph.ingest import Graph, ingest_document  # noqa: E402
from src.pdf_ingest import process_pdf  # noqa: E402


CASE_URL_DEFAULT = "https://www.hcourt.gov.au/cases-and-judgments/cases/decided/case-s942025"

_MONTH_TOKEN_TO_INT = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _safe_name(text: str) -> str:
    t = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text or "").strip())
    t = re.sub(r"_+", "_", t).strip("._")
    return t or "artifact"


def _norm_label(text: str) -> str:
    t = html.unescape(str(text or "")).lower()
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return _collapse_ws(t)


def _guess_ext(url: str, content_type: str) -> str:
    p = urllib.parse.urlparse(url)
    ext = Path(p.path or "").suffix.lower()
    if ext:
        return ext
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return ".pdf"
    if "json" in ct:
        return ".json"
    if "html" in ct:
        return ".html"
    if "vtt" in ct:
        return ".vtt"
    return ".bin"


def _abs_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(str(href or "").strip()))


def _fetch(url: str, timeout: int, headers: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    req_headers = {"User-Agent": "ITIR-suite/0.1"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - bounded explicit fetch
        data = resp.read()
        content_type = str(resp.headers.get("Content-Type") or "")
        final_url = str(resp.geturl() or url)
    return {
        "url": url,
        "final_url": final_url,
        "content_type": content_type,
        "bytes": len(data),
        "data": data,
    }


def _download(url: str, out_path: Path, timeout: int, headers: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    fetched = _fetch(url, timeout=timeout, headers=headers)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(fetched["data"])  # type: ignore[index]
    return {
        "url": fetched["url"],
        "final_url": fetched["final_url"],
        "content_type": fetched["content_type"],
        "bytes": fetched["bytes"],
        "path": str(out_path),
    }


def _strip_tags(fragment: str) -> str:
    s = re.sub(r"<[^>]+>", " ", str(fragment or ""))
    s = html.unescape(s)
    return _collapse_ws(s)


def _html_to_text(fragment: str) -> str:
    s = str(fragment or "")
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r"</?(p|div|li|h[1-6]|tr|br)[^>]*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    lines = [_collapse_ws(line) for line in s.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def _score_case_doc_link(label: str, url: str) -> int:
    label_norm = _norm_label(label)
    u = str(url or "").lower()
    score = 0
    if ".pdf" in u:
        score += 60
    if "/sites/default/files/" in u:
        score += 10
    if "judgment summary" in label_norm and ("judgment-summaries" in u or "case-summaries" in u):
        score += 80
    if "judgment summary" in label_norm and "/judgments/" in u and ".pdf" not in u:
        score -= 60
    if "case recording" in label_norm:
        if "/av-recording/" in u:
            score += 80
        elif ".pdf" in u:
            score -= 30
    if "notice of appeal" in label_norm and "notice" in u and "appeal" in u:
        score += 40
    if "chronology" in label_norm and "chronology" in u:
        score += 30
    if "written submissions" in label_norm and "written-submissions" in u:
        score += 30
    if "outline of oral argument" in label_norm and "oral-argument" in u:
        score += 30
    return score


def _pick_best_case_doc_link(label: str, links: List[str]) -> Optional[str]:
    if not links:
        return None
    best_score = None
    best_url = None
    for idx, url in enumerate(links):
        score = _score_case_doc_link(label, url)
        # Stable tie-break: earlier list index wins.
        key = (score, -idx)
        if best_score is None or key > best_score:
            best_score = key
            best_url = url
    return best_url


def _extract_transcript_links_from_recording_page(recording_html: str, base_url: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    block = recording_html
    m = re.search(
        r'field--name-field-av-transcripts.*?<div class="field__item">(.*?)</div>',
        recording_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        block = m.group(1)
    for m_link in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.IGNORECASE | re.DOTALL):
        href = _abs_url(base_url, m_link.group(1))
        label = _strip_tags(m_link.group(2)) or "Transcript"
        if href in seen:
            continue
        seen.add(href)
        out.append({"label": label, "url": href})
    return out


def _build_doc_plan(case_url: str) -> List[Dict[str, Optional[str]]]:
    # Baseline list requested by user. Missing links are resolved via case-page second pass.
    return [
        {"date": "2025-06-17", "label": "Hearing (SLA, Canberra)", "url": None},
        {"date": "2025-07-01", "label": "Notice of appeal", "url": None},
        {"date": "2025-07-07", "label": "Written submissions (Appellant)", "url": None},
        {"date": "2025-07-07", "label": "Chronology (Appellant)", "url": None},
        {"date": "2025-07-18", "label": "Written submissions (Respondent)", "url": None},
        {"date": "2025-07-23", "label": "Reply", "url": None},
        {"date": "2025-08-07", "label": "Hearing (Full Court, Canberra)", "url": None},
        {"date": "2025-08-07", "label": "Outline of oral argument (Appellant)", "url": None},
        {"date": "2025-08-07", "label": "Outline of oral argument (Respondent)", "url": None},
        {"date": "2026-02-11", "label": "Judgment (Judgment Summary)", "url": None},
        {
            "date": "2025-08-01",
            "label": "Case summary (Canberra PDF)",
            "url": "https://www.hcourt.gov.au/sites/default/files/case-summaries/2025-08/SP%20August%202025%20-%20Canberra.pdf",
        },
        {"date": "2025-08-07", "label": "Case recording", "url": None},
        {"date": None, "label": "Case page", "url": case_url},
    ]


def _extract_case_document_rows(case_html: str, case_url: str) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    m = re.search(
        r"field--name-field-case-documents.*?<table>(?P<body>.*?)</table>",
        case_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return out
    body = m.group("body")
    for tr in re.findall(r"<tr>(.*?)</tr>", body, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 2:
            continue
        date_text = _strip_tags(cells[0])
        col_html = cells[1]
        label_text = _strip_tags(col_html)
        hrefs = [_abs_url(case_url, h) for h in re.findall(r'href="([^"]+)"', col_html, flags=re.IGNORECASE)]
        out.append(
            {
                "date": date_text,
                "label_text": label_text,
                "label_norm": _norm_label(label_text),
                "links": hrefs,
            }
        )
    return out


def _extract_case_recording(case_html: str, case_url: str) -> Dict[str, Optional[str]]:
    rec_page = None
    oembed_url = None
    m = re.search(r'href="([^"]*/av-recording/[^"]+)"', case_html, flags=re.IGNORECASE)
    if m:
        rec_page = _abs_url(case_url, m.group(1))
    m = re.search(r'<iframe[^>]+src="([^"]+/media/oembed\?[^"]+)"', case_html, flags=re.IGNORECASE)
    if m:
        oembed_url = _abs_url(case_url, m.group(1))
    return {
        "recording_page_url": rec_page,
        "oembed_url": oembed_url,
    }


def _apply_case_page_discovery(plan: List[Dict[str, Optional[str]]], case_html: str, case_url: str) -> Dict[str, object]:
    rows = _extract_case_document_rows(case_html, case_url)
    rec = _extract_case_recording(case_html, case_url)

    updates: List[Dict[str, object]] = []
    unresolved: List[Dict[str, str]] = []

    for item in plan:
        label = str(item.get("label") or "")
        if not label:
            continue
        label_norm = _norm_label(label)
        if label.lower() == "case page":
            continue

        matched_row = None
        for row in rows:
            row_norm = str(row.get("label_norm") or "")
            if not row_norm:
                continue
            if label_norm in row_norm or row_norm in label_norm:
                matched_row = row
                break

        if matched_row and matched_row.get("links"):
            links = matched_row.get("links") or []
            if links:
                prev = item.get("url")
                new_url = _pick_best_case_doc_link(label, [str(x) for x in links]) or str(links[0])
                # Keep hearing links synced to the case documents table.
                if prev != new_url:
                    item["url"] = new_url
                    updates.append(
                        {
                            "label": label,
                            "date": item.get("date"),
                            "url": new_url,
                            "source": "case_page_documents_table",
                        }
                    )
                continue

        if label.lower() == "case recording":
            rec_url = rec.get("recording_page_url")
            if rec_url and item.get("url") != rec_url:
                item["url"] = rec_url
                updates.append(
                    {
                        "label": label,
                        "date": item.get("date"),
                        "url": rec_url,
                        "source": "case_page_recording_block",
                    }
                )
            elif not rec_url:
                unresolved.append({"label": label, "reason": "recording_url_not_found"})
            continue

        if not item.get("url"):
            unresolved.append({"label": label, "reason": "no_link_in_case_documents_table"})

    return {
        "rows_found": len(rows),
        "updates": updates,
        "unresolved": unresolved,
        "recording_page_url": rec.get("recording_page_url"),
        "oembed_url": rec.get("oembed_url"),
    }


def _extract_iframe_srcs(html_text: str, base_url: str) -> List[str]:
    out = []
    seen = set()
    for src in re.findall(r'<iframe[^>]+src="([^"]+)"', html_text, flags=re.IGNORECASE):
        u = _abs_url(base_url, src)
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _decode_oembed_player_url(oembed_url: str) -> Optional[str]:
    p = urllib.parse.urlparse(oembed_url)
    q = urllib.parse.parse_qs(p.query)
    raw = (q.get("url") or [None])[0]
    if not raw:
        return None
    url = html.unescape(str(raw))
    url = url.replace("&amp;", "&")
    return url


def _vimeo_config_url(player_url: str) -> Optional[str]:
    m = re.search(r"(https?://player\.vimeo\.com/video/\d+)", player_url)
    if not m:
        return None
    base = m.group(1).rstrip("/")
    parsed = urllib.parse.urlparse(player_url)
    qs = parsed.query or ""
    return f"{base}/config?{qs}" if qs else f"{base}/config"


def _extract_vimeo_id(player_url: str) -> Optional[str]:
    m = re.search(r"player\.vimeo\.com/video/(\d+)", player_url)
    return m.group(1) if m else None


def _extract_vimeo_config_request_url(player_html: str) -> Optional[str]:
    m = re.search(r"https://player\.vimeo\.com/video/\d+/config/request\?[^\"']+", player_html)
    if not m:
        return None
    raw = m.group(0)
    return raw.replace("\\u0026", "&").replace("&amp;", "&")


def _collect_stream_manifest_urls(cfg: Dict[str, object]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    files = cfg.get("files") if isinstance(cfg, dict) else {}
    if not isinstance(files, dict):
        return out
    for proto in ("hls", "dash"):
        container = files.get(proto)
        if not isinstance(container, dict):
            continue
        cdns = container.get("cdns")
        if not isinstance(cdns, dict):
            continue
        for cdn_name, cdn_row in cdns.items():
            if not isinstance(cdn_row, dict):
                continue
            for key in ("url", "avc_url"):
                url = cdn_row.get(key)
                if not isinstance(url, str) or not url:
                    continue
                if url in seen:
                    continue
                seen.add(url)
                out.append({"protocol": proto, "cdn": str(cdn_name), "kind": key, "url": url})
    return out


def _parse_vtt_segments(vtt_text: str) -> List[Dict[str, str]]:
    segments: List[Dict[str, str]] = []
    lines = vtt_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        parts = [p.strip() for p in line.split("-->")]
        if len(parts) != 2:
            i += 1
            continue
        start, end = parts[0], parts[1].split()[0]
        i += 1
        text_lines: List[str] = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1
        text = _collapse_ws(" ".join(text_lines))
        if text:
            segments.append({"start": start, "end": end, "text": text})
        i += 1
    return segments


def _extract_media(
    *,
    case_url: str,
    case_html: str,
    discovery: Dict[str, object],
    raw_dir: Path,
    media_dir: Path,
    timeout: int,
    download_video: bool,
) -> Dict[str, object]:
    report: Dict[str, object] = {
        "ok": True,
        "recording_page": None,
        "oembed_urls": [],
        "player_urls": [],
        "videos": [],
        "captions": [],
        "transcript_links": [],
        "transcript_pages": [],
        "stream_manifests": [],
        "errors": [],
    }

    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / "video").mkdir(parents=True, exist_ok=True)
    (media_dir / "captions").mkdir(parents=True, exist_ok=True)
    (media_dir / "transcripts").mkdir(parents=True, exist_ok=True)

    oembed_urls: List[str] = []
    initial_oembed = discovery.get("oembed_url")
    if isinstance(initial_oembed, str) and initial_oembed:
        oembed_urls.append(initial_oembed)

    recording_page_url = discovery.get("recording_page_url")
    if isinstance(recording_page_url, str) and recording_page_url:
        report["recording_page"] = recording_page_url
        try:
            out_path = raw_dir / "undated_Case_recording_page.html"
            rec_dl = _download(recording_page_url, out_path, timeout=timeout)
            rec_html = out_path.read_text(encoding="utf-8", errors="replace")
            transcript_links = _extract_transcript_links_from_recording_page(rec_html, recording_page_url)
            report["transcript_links"] = transcript_links
            transcript_pages: List[Dict[str, object]] = []
            for idx, t in enumerate(transcript_links, start=1):
                t_url = str(t.get("url") or "")
                if not t_url:
                    continue
                t_label = str(t.get("label") or f"transcript_{idx}")
                t_ext = ".pdf" if t_url.lower().endswith(".pdf") else ".html"
                t_path = media_dir / "transcripts" / f"{idx:02d}_{_safe_name(t_label)}{t_ext}"
                td = _download(
                    t_url,
                    t_path,
                    timeout=timeout,
                    headers={"Referer": recording_page_url},
                )
                row: Dict[str, object] = {
                    "label": t_label,
                    "url": t_url,
                    "path": str(t_path),
                    "bytes": td.get("bytes"),
                    "content_type": td.get("content_type"),
                }
                if t_ext == ".html":
                    t_html = t_path.read_text(encoding="utf-8", errors="replace")
                    text = _html_to_text(t_html)
                    txt_path = media_dir / "transcripts" / f"{idx:02d}_{_safe_name(t_label)}.txt"
                    txt_path.write_text(text + ("\n" if text else ""), encoding="utf-8")
                    row["text_path"] = str(txt_path)
                transcript_pages.append(row)
            report["transcript_pages"] = transcript_pages
            for src in _extract_iframe_srcs(rec_html, recording_page_url):
                if "/media/oembed?" in src and src not in oembed_urls:
                    oembed_urls.append(src)
            report["recording_page_download"] = rec_dl
        except Exception as e:  # pragma: no cover - defensive
            report["errors"].append(f"recording_page_fetch_failed: {type(e).__name__}: {e}")

    # Also scan case page for iframe/oembed in case recording page fetch fails.
    for src in _extract_iframe_srcs(case_html, case_url):
        if "/media/oembed?" in src and src not in oembed_urls:
            oembed_urls.append(src)
    report["oembed_urls"] = oembed_urls

    player_urls: List[str] = []
    for idx, oembed_url in enumerate(oembed_urls, start=1):
        try:
            oembed_path = raw_dir / f"oembed_{idx}.html"
            _download(oembed_url, oembed_path, timeout=timeout)
            oembed_html = oembed_path.read_text(encoding="utf-8", errors="replace")
            found = None
            for src in _extract_iframe_srcs(oembed_html, oembed_url):
                if "player.vimeo.com/video/" in src:
                    found = src
                    break
            if not found:
                found = _decode_oembed_player_url(oembed_url)
            if found and found not in player_urls:
                player_urls.append(found)
        except Exception as e:  # pragma: no cover - defensive
            report["errors"].append(f"oembed_fetch_failed[{idx}]: {type(e).__name__}: {e}")
    report["player_urls"] = player_urls

    for purl in player_urls:
        vid = _extract_vimeo_id(purl)
        if not vid:
            report["errors"].append(f"vimeo_id_not_found: {purl}")
            continue
        cfg_url = _vimeo_config_url(purl)
        if not cfg_url:
            report["errors"].append(f"vimeo_config_url_not_found: {purl}")
            continue

        cfg = None
        cfg_source = None
        try:
            fetched = _fetch(
                cfg_url,
                timeout=timeout,
                headers={
                    "Referer": purl,
                    "Origin": "https://player.vimeo.com",
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            cfg_bytes = fetched["data"]  # type: ignore[index]
            cfg = json.loads(cfg_bytes.decode("utf-8", errors="replace"))
            cfg_source = "config"
        except Exception as e:
            report["errors"].append(f"vimeo_config_fetch_failed[{vid}]: {type(e).__name__}: {e}")
            try:
                player_fetched = _fetch(
                    purl,
                    timeout=timeout,
                    headers={
                        "Referer": case_url,
                        "Accept": "text/html,*/*",
                    },
                )
                player_html = (player_fetched["data"] or b"").decode("utf-8", errors="replace")  # type: ignore[index]
                req_url = _extract_vimeo_config_request_url(player_html)
                if not req_url:
                    raise ValueError("config_request_url_not_found")
                req_fetched = _fetch(
                    req_url,
                    timeout=timeout,
                    headers={
                        "Referer": purl,
                        "Accept": "application/json,text/plain,*/*",
                    },
                )
                cfg = json.loads((req_fetched["data"] or b"").decode("utf-8", errors="replace"))  # type: ignore[index]
                cfg_source = "config_request"
            except Exception as e2:
                report["errors"].append(f"vimeo_config_request_fetch_failed[{vid}]: {type(e2).__name__}: {e2}")
                continue

        cfg_path = media_dir / f"vimeo_{vid}_{cfg_source or 'config'}.json"
        cfg_path.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")

        request = cfg.get("request") if isinstance(cfg, dict) else {}
        files = None
        tracks = None
        if isinstance(request, dict):
            files = request.get("files")
            tracks = request.get("text_tracks")
        if not isinstance(files, dict):
            files = cfg.get("files") if isinstance(cfg, dict) else {}
        if not isinstance(tracks, list):
            tracks = cfg.get("text_tracks") if isinstance(cfg, dict) else []
        progressive = files.get("progressive") if isinstance(files, dict) else []

        stream_manifests = _collect_stream_manifest_urls(cfg if isinstance(cfg, dict) else {})
        for idx, row in enumerate(stream_manifests, start=1):
            m_url = row.get("url") or ""
            if not m_url:
                continue
            guessed_ext = ".m3u8" if str(row.get("protocol")) == "hls" else ".mpd"
            out_manifest = media_dir / "video" / f"vimeo_{vid}_{idx:02d}_{_safe_name(str(row.get('protocol')))}_{_safe_name(str(row.get('cdn')))}_{_safe_name(str(row.get('kind')))}{guessed_ext}"
            try:
                md = _download(m_url, out_manifest, timeout=timeout, headers={"Referer": purl})
                cast = dict(row)
                cast["path"] = str(out_manifest)
                cast["bytes"] = md.get("bytes")
                cast["content_type"] = md.get("content_type")
                report_streams = report.get("stream_manifests")
                if isinstance(report_streams, list):
                    report_streams.append(cast)
            except Exception as e:
                report["errors"].append(f"vimeo_manifest_download_failed[{vid}:{idx}]: {type(e).__name__}: {e}")

        if download_video and isinstance(progressive, list) and progressive:
            best = None
            for row in progressive:
                if not isinstance(row, dict):
                    continue
                if not isinstance(row.get("url"), str):
                    continue
                h = int(row.get("height") or 0)
                bitrate = int(row.get("bitrate") or 0)
                score = (h, bitrate)
                if best is None or score > best[0]:
                    best = (score, row)
            if best is not None:
                row = best[1]
                vurl = str(row.get("url"))
                h = int(row.get("height") or 0)
                out_path = media_dir / "video" / f"vimeo_{vid}_{h}p.mp4"
                try:
                    dl = _download(vurl, out_path, timeout=timeout)
                    report["videos"].append(
                        {
                            "video_id": vid,
                            "height": h,
                            "path": str(out_path),
                            "bytes": dl.get("bytes"),
                            "url": dl.get("final_url"),
                        }
                    )
                except Exception as e:
                    report["errors"].append(f"vimeo_video_download_failed[{vid}]: {type(e).__name__}: {e}")

        if isinstance(tracks, list):
            for t in tracks:
                if not isinstance(t, dict):
                    continue
                turl = str(t.get("url") or "").strip()
                if not turl:
                    continue
                if turl.startswith("//"):
                    turl = "https:" + turl
                elif turl.startswith("/"):
                    turl = urllib.parse.urljoin("https://player.vimeo.com", turl)
                lang = str(t.get("lang") or t.get("language") or "und")
                kind = str(t.get("kind") or "subtitles")
                out_vtt = media_dir / "captions" / f"vimeo_{vid}_{_safe_name(lang)}_{_safe_name(kind)}.vtt"
                try:
                    td = _download(turl, out_vtt, timeout=timeout)
                    vtt_text = out_vtt.read_text(encoding="utf-8", errors="replace")
                    segments = _parse_vtt_segments(vtt_text)
                    seg_path = media_dir / "transcripts" / f"vimeo_{vid}_{_safe_name(lang)}.segments.json"
                    md_path = media_dir / "transcripts" / f"vimeo_{vid}_{_safe_name(lang)}.md"
                    seg_path.write_text(json.dumps({"video_id": vid, "lang": lang, "segments": segments}, indent=2), encoding="utf-8")
                    md_lines = [f"# Transcript ({vid}, {lang})", ""]
                    for s in segments:
                        md_lines.append(f"- [{s['start']} --> {s['end']}] {s['text']}")
                    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
                    report["captions"].append(
                        {
                            "video_id": vid,
                            "lang": lang,
                            "kind": kind,
                            "vtt": str(out_vtt),
                            "segments_json": str(seg_path),
                            "transcript_md": str(md_path),
                            "bytes": td.get("bytes"),
                        }
                    )
                except Exception as e:
                    report["errors"].append(f"vimeo_caption_download_failed[{vid}:{lang}]: {type(e).__name__}: {e}")

    return report


def _iter_pdfs(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.suffix.lower() == ".pdf":
            yield p


def _resolve_dot_binary(cli_value: Optional[str]) -> Optional[str]:
    if cli_value:
        p = Path(cli_value)
        if p.exists() and p.is_file():
            return str(p)
    env_dot = os.environ.get("SENSIBLAW_DOT_BIN") or os.environ.get("GRAPHVIZ_DOT")
    if env_dot:
        p = Path(env_dot)
        if p.exists() and p.is_file():
            return str(p)
    for cand in ("dot", "/usr/bin/dot", "/usr/local/bin/dot", "/opt/conda/bin/dot"):
        resolved = shutil.which(cand) if cand == "dot" else (cand if Path(cand).exists() else None)
        if resolved:
            return resolved
    return None


def _graph_payload(graph: Graph) -> Dict[str, object]:
    nodes: List[Dict[str, object]] = []
    for node in sorted(graph.nodes.values(), key=lambda n: n.id):
        row: Dict[str, object] = {"id": node.id, "type": node.label, "label": node.label}
        row.update(node.properties or {})
        nodes.append(row)
    edges: List[Dict[str, object]] = []
    for edge in graph.edges:
        row: Dict[str, object] = {"source": edge.source, "target": edge.target, "type": edge.type}
        row.update(edge.properties or {})
        edges.append(row)
    return {"nodes": nodes, "edges": edges}


def _graph_dot(graph_json: Dict[str, object]) -> str:
    lines = []
    lines.append("digraph case_bundle {")
    lines.append('  rankdir="LR";')
    lines.append('  graph [bgcolor="white"];')
    lines.append('  node [shape="box", style="rounded,filled", fillcolor="#f8fafc", color="#94a3b8", fontname="Helvetica"];')
    lines.append('  edge [color="#64748b", fontname="Helvetica", fontsize=10];')
    for n in graph_json.get("nodes", []):
        if not isinstance(n, dict):
            continue
        node_id = str(n.get("id") or "")
        if not node_id:
            continue
        label = str(n.get("id") or "").replace('"', "'")
        lines.append(f'  "{node_id}" [label="{label}"];')
    for e in graph_json.get("edges", []):
        if not isinstance(e, dict):
            continue
        src = str(e.get("source") or "")
        dst = str(e.get("target") or "")
        if not src or not dst:
            continue
        et = str(e.get("type") or "").replace('"', "'")
        lines.append(f'  "{src}" -> "{dst}" [label="{et}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _anchor_from_date_text(date_text: Optional[str]) -> Dict[str, object]:
    raw = _collapse_ws(date_text or "")
    m = re.match(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$", raw)
    if not m:
        return {"year": 0, "month": None, "day": None, "precision": "undated", "text": raw or "undated", "kind": "date"}
    y = int(m.group(1))
    mm = int(m.group(2)) if m.group(2) else None
    dd = int(m.group(3)) if m.group(3) else None
    if dd is not None:
        precision = "day"
    elif mm is not None:
        precision = "month"
    else:
        precision = "year"
    return {"year": y, "month": mm, "day": dd, "precision": precision, "text": raw, "kind": "date"}


def _section_for_label(label: str) -> str:
    l = (label or "").lower()
    if "hearing" in l or "oral argument" in l:
        return "Hearings"
    if "judgment" in l:
        return "Judgment"
    if "notice of appeal" in l or "written submissions" in l or "chronology" in l or l.strip() == "reply":
        return "Filings"
    if "recording" in l or "transcript" in l or "caption" in l:
        return "Recordings"
    if "case summary" in l:
        return "Summaries"
    return "Case artifacts"


def _action_for_label(label: str, status: str) -> str:
    if status in {"missing_url", "error"}:
        return "pending"
    l = (label or "").lower()
    if "hearing" in l:
        return "heard"
    if "oral argument" in l:
        return "argued"
    if "notice of appeal" in l:
        return "appealed"
    if "written submissions" in l or "chronology" in l or l.strip() == "reply":
        return "filed"
    if "judgment" in l:
        return "decided"
    if "case summary" in l:
        return "published"
    if "recording" in l:
        return "recorded"
    if "transcript" in l:
        return "transcribed"
    if "caption" in l:
        return "captioned"
    if "manifest" in l:
        return "streamed"
    return "documented"


def _extract_ints(text: str) -> List[int]:
    out: List[int] = []
    cur = ""
    for ch in str(text or ""):
        if ch.isdigit():
            cur += ch
            continue
        if cur:
            try:
                out.append(int(cur))
            except Exception:
                pass
            cur = ""
    if cur:
        try:
            out.append(int(cur))
        except Exception:
            pass
    return out


def _citation_follow_hints(citation_text: str, source_document_json: str, source_pdf: str) -> List[Dict[str, str]]:
    q = urllib.parse.quote_plus(str(citation_text or "").strip())
    hints: List[Dict[str, str]] = []
    if q:
        hints.append(
            {
                "provider": "wikipedia",
                "mode": "search",
                "url": f"https://en.wikipedia.org/wiki/Special:Search?search={q}",
            }
        )
        hints.append(
            {
                "provider": "wiki_connector",
                "mode": "snapshot_pull",
                "script": str(SENSIBLAW_ROOT / "scripts" / "wiki_pull_api.py"),
                "driver": "pywikibot",
                "wiki": "enwiki",
                "title": str(citation_text or "").strip(),
            }
        )
    if source_document_json:
        hints.append(
            {
                "provider": "source_document",
                "mode": "local_document_json",
                "path": source_document_json,
            }
        )
    if source_pdf:
        hints.append(
            {
                "provider": "source_pdf",
                "mode": "local_pdf",
                "path": source_pdf,
            }
        )
    return hints


def _looks_like_citation_text(text: str) -> bool:
    s = _collapse_ws(text)
    if not s:
        return False
    if "[" in s and "]" in s:
        return True
    if "CAB " in s or s.startswith("CAB"):
        return True
    if s.isdigit() and len(s) <= 3:
        return True
    return False


def _extract_citations(text: str, source_document_json: str = "", source_pdf: str = "") -> List[Dict[str, object]]:
    s = str(text or "")
    out: List[Dict[str, object]] = []
    seen = set()

    def add_citation(cit_text: str, kind: str, prefix: Optional[str] = None) -> None:
        ctext = _collapse_ws(cit_text)
        if not ctext:
            return
        if kind in {"doc_pointer", "bracket_ref", "court_citation"}:
            if ctext.count("[") != ctext.count("]"):
                return
        key = (kind, ctext.lower())
        if key in seen:
            return
        seen.add(key)
        row: Dict[str, object] = {
            "text": ctext,
            "kind": kind,
            "targets": _extract_ints(ctext),
            "follower_order": ["wikipedia", "wiki_connector", "source_document", "source_pdf"],
            "follow": _citation_follow_hints(ctext, source_document_json=source_document_json, source_pdf=source_pdf),
        }
        if prefix:
            row["prefix"] = prefix
        out.append(row)

    i = 0
    n = len(s)
    while i < n:
        ch = s[i]

        # Pattern: [2026] HCA 2
        if ch == "[":
            j = i + 1
            while j < n and s[j].isdigit():
                j += 1
            if j < n and s[j] == "]" and (j - (i + 1)) == 4:
                k = j + 1
                while k < n and s[k].isspace():
                    k += 1
                l = k
                while l < n and s[l].isalpha():
                    l += 1
                if l > k:
                    while l < n and s[l].isspace():
                        l += 1
                    m = l
                    while m < n and s[m].isdigit():
                        m += 1
                    if m > l:
                        add_citation(s[i:m], kind="court_citation")
                        i = m
                        continue

        # Pattern: AS[27]-[29], SC[210], RS[15]
        if ch.isalpha():
            j = i
            while j < n and s[j].isalpha():
                j += 1
            token = s[i:j]
            upper = token.upper()
            if token == upper and 1 <= len(token) <= 5:
                k = j
                while k < n and s[k].isspace():
                    k += 1
                if k < n and s[k] == "[":
                    l = k + 1
                    while l < n:
                        c = s[l]
                        if c.isdigit() or c in "[]-–—,; ":
                            l += 1
                            continue
                        break
                    add_citation(s[i:l], kind="doc_pointer", prefix=upper)
                    i = l
                    continue
                if upper == "CAB":
                    l = k
                    while l < n and (s[l].isdigit() or s[l] in " ,-–—;"):
                        l += 1
                    if l > k and any(c.isdigit() for c in s[k:l]):
                        add_citation(s[i:l], kind="bundle_pages", prefix=upper)
                        i = l
                        continue

        # Pattern: standalone bracket refs [218], [257]
        if ch == "[":
            j = i + 1
            while j < n and s[j].isdigit():
                j += 1
            if j < n and s[j] == "]" and j > i + 1:
                add_citation(s[i : j + 1], kind="bracket_ref")
                i = j + 1
                continue

        # Pattern: footnote markers .11 ;12
        if ch in ".;" and (i + 1) < n and s[i + 1].isdigit():
            j = i + 1
            while j < n and s[j].isdigit():
                j += 1
            if 1 <= (j - (i + 1)) <= 3:
                add_citation(s[i:j], kind="footnote_marker")
                i = j
                continue

        i += 1

    return out


def _norm_match_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _collapse_ws(str(text or "")).lower()).strip()


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{4,}", _norm_match_text(text)))


def _iter_reference_payloads(raw: object) -> Iterable[Dict[str, object]]:
    if isinstance(raw, list):
        # Common parser tuple: [authority, type, value, source_text, ...]
        if raw and all(not isinstance(x, (list, tuple, dict)) for x in raw):
            authority = str(raw[0] or "").strip() if len(raw) >= 1 else ""
            ref_kind = str(raw[1] or "").strip() if len(raw) >= 2 else ""
            ref_value = str(raw[2] or "").strip() if len(raw) >= 3 else ""
            ref_text = str(raw[3] or "").strip() if len(raw) >= 4 else ""
            yield {
                "authority": authority,
                "ref_kind": ref_kind,
                "ref_value": ref_value,
                "ref_text": ref_text or authority or ref_value,
            }
            return
        for item in raw:
            yield from _iter_reference_payloads(item)
        return
    if isinstance(raw, dict):
        authority = str(raw.get("authority") or raw.get("instrument") or "").strip()
        ref_kind = str(raw.get("kind") or raw.get("type") or "").strip()
        ref_value = str(raw.get("value") or raw.get("id") or "").strip()
        ref_text = str(raw.get("text") or raw.get("label") or "").strip()
        if authority or ref_kind or ref_value or ref_text:
            yield {
                "authority": authority,
                "ref_kind": ref_kind,
                "ref_value": ref_value,
                "ref_text": ref_text or authority or ref_value,
            }
        return
    if isinstance(raw, str):
        s = _collapse_ws(raw)
        if s:
            yield {"authority": "", "ref_kind": "", "ref_value": "", "ref_text": s}


def _collect_sl_reference_rows(document_json_path: str) -> List[Dict[str, object]]:
    p = Path(str(document_json_path or "").strip())
    if not p.exists():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []

    rows: List[Dict[str, object]] = []
    seen = set()
    provisions = payload.get("provisions")
    if not isinstance(provisions, list):
        return rows

    def add_rows(
        refs_payload: object,
        lane: str,
        context_text: str,
        provision_stable_id: str,
        rule_atom_stable_id: str = "",
    ) -> None:
        for parsed in _iter_reference_payloads(refs_payload):
            authority = str(parsed.get("authority") or "").strip()
            ref_kind = str(parsed.get("ref_kind") or "").strip()
            ref_value = str(parsed.get("ref_value") or "").strip()
            ref_text = str(parsed.get("ref_text") or "").strip()
            if not (authority or ref_kind or ref_value or ref_text):
                continue
            dedupe_key = (
                lane,
                provision_stable_id,
                rule_atom_stable_id,
                authority.lower(),
                ref_kind.lower(),
                ref_value.lower(),
                ref_text.lower(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                {
                    "lane": lane,
                    "authority": authority,
                    "ref_kind": ref_kind,
                    "ref_value": ref_value,
                    "text": ref_text,
                    "source_document_json": str(p),
                    "provision_stable_id": provision_stable_id or None,
                    "rule_atom_stable_id": rule_atom_stable_id or None,
                    "_context_norm": _norm_match_text(context_text),
                }
            )

    for provision in provisions:
        if not isinstance(provision, dict):
            continue
        provision_text = str(provision.get("text") or "")
        provision_stable_id = str(provision.get("stable_id") or provision.get("toc_id") or "").strip()
        add_rows(
            provision.get("references") or [],
            lane="provisions.references",
            context_text=provision_text,
            provision_stable_id=provision_stable_id,
        )
        rule_tokens = provision.get("rule_tokens")
        if isinstance(rule_tokens, dict):
            add_rows(
                rule_tokens.get("references") or [],
                lane="provisions.rule_tokens.references",
                context_text=provision_text,
                provision_stable_id=provision_stable_id,
            )

        rule_atoms = provision.get("rule_atoms")
        if not isinstance(rule_atoms, list):
            continue
        for atom in rule_atoms:
            if not isinstance(atom, dict):
                continue
            atom_text = str(atom.get("text") or provision_text)
            atom_stable_id = str(atom.get("stable_id") or "").strip()
            add_rows(
                atom.get("references") or [],
                lane="rule_atoms.references",
                context_text=atom_text,
                provision_stable_id=provision_stable_id,
                rule_atom_stable_id=atom_stable_id,
            )
            subject = atom.get("subject")
            if isinstance(subject, dict):
                add_rows(
                    subject.get("refs") or [],
                    lane="rule_atoms.subject.refs",
                    context_text=atom_text,
                    provision_stable_id=provision_stable_id,
                    rule_atom_stable_id=atom_stable_id,
                )
            elements = atom.get("elements")
            if not isinstance(elements, list):
                continue
            for idx, element in enumerate(elements):
                if not isinstance(element, dict):
                    continue
                element_text = str(element.get("text") or atom_text)
                add_rows(
                    element.get("references") or [],
                    lane=f"rule_atoms.elements[{idx}].references",
                    context_text=element_text,
                    provision_stable_id=provision_stable_id,
                    rule_atom_stable_id=atom_stable_id,
                )
    return rows


def _select_sl_references_for_sentence(
    doc_rows: List[Dict[str, object]],
    sentence_text: str,
    source_document_json: str = "",
    source_pdf: str = "",
    max_rows: int = 16,
) -> List[Dict[str, object]]:
    if not doc_rows:
        return []
    sentence_norm = _norm_match_text(sentence_text)
    sentence_tokens = _token_set(sentence_text)
    scored: List[Tuple[float, Dict[str, object]]] = []
    for row in doc_rows:
        if not isinstance(row, dict):
            continue
        context_norm = str(row.get("_context_norm") or "")
        if not context_norm:
            continue
        score = 0.0
        if sentence_norm and context_norm:
            if sentence_norm in context_norm:
                score += 10.0
            elif context_norm in sentence_norm:
                score += 4.0
        if sentence_tokens:
            overlap = sentence_tokens.intersection(_token_set(context_norm))
            if overlap:
                score += float(len(overlap)) / 3.0
        if score > 0.0:
            scored.append((score, row))

    scored.sort(
        key=lambda item: (
            -item[0],
            str(item[1].get("authority") or "").lower(),
            str(item[1].get("ref_value") or "").lower(),
            str(item[1].get("text") or "").lower(),
        )
    )

    out: List[Dict[str, object]] = []
    seen = set()
    for _, row in scored:
        dedupe_key = (
            str(row.get("lane") or ""),
            str(row.get("authority") or "").lower(),
            str(row.get("ref_kind") or "").lower(),
            str(row.get("ref_value") or "").lower(),
            str(row.get("text") or "").lower(),
            str(row.get("provision_stable_id") or ""),
            str(row.get("rule_atom_stable_id") or ""),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        ref_text = str(row.get("text") or "").strip()
        follow_text = ref_text or f"{row.get('authority') or ''} {row.get('ref_value') or ''}".strip()
        out.append(
            {
                "lane": str(row.get("lane") or ""),
                "authority": str(row.get("authority") or ""),
                "ref_kind": str(row.get("ref_kind") or ""),
                "ref_value": str(row.get("ref_value") or ""),
                "text": ref_text,
                "source_document_json": str(source_document_json or row.get("source_document_json") or ""),
                "source_pdf": str(source_pdf or ""),
                "provision_stable_id": row.get("provision_stable_id"),
                "rule_atom_stable_id": row.get("rule_atom_stable_id"),
                "follower_order": ["wikipedia", "wiki_connector", "source_document", "source_pdf"],
                "follow": _citation_follow_hints(
                    follow_text,
                    source_document_json=str(source_document_json or row.get("source_document_json") or ""),
                    source_pdf=str(source_pdf or ""),
                ),
            }
        )
        if len(out) >= max(1, int(max_rows)):
            break
    return out


def _flatten_toc_entries(raw: object) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []

    def walk(entries: object, lineage: List[str]) -> None:
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            identifier = _collapse_ws(str(entry.get("identifier") or ""))
            title = _collapse_ws(str(entry.get("title") or ""))
            node_type = _collapse_ws(str(entry.get("node_type") or ""))
            label = _collapse_ws(" ".join(x for x in [identifier, title] if x))
            if label:
                path_tokens = [x for x in lineage + [label] if x]
                out.append(
                    {
                        "identifier": identifier,
                        "title": title,
                        "node_type": node_type,
                        "label": label,
                        "path": " > ".join(path_tokens),
                        "_norm": _norm_match_text(label),
                    }
                )
            walk(entry.get("children"), lineage + ([label] if label else []))

    walk(raw, [])
    return out


def _collect_doc_context(document_json_path: str) -> Dict[str, object]:
    p = Path(str(document_json_path or "").strip())
    if not p.exists():
        return {"toc_rows": [], "metadata": {}}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"toc_rows": [], "metadata": {}}
    toc_rows = _flatten_toc_entries(payload.get("toc_entries"))
    metadata = payload.get("metadata")
    sentence_rows = payload.get("sentences")
    sentence_texts: List[str] = []
    if isinstance(sentence_rows, list):
        for row in sentence_rows:
            if not isinstance(row, dict):
                continue
            txt = _collapse_ws(str(row.get("text") or ""))
            if txt:
                sentence_texts.append(txt)
    return {
        "toc_rows": toc_rows,
        "metadata": metadata if isinstance(metadata, dict) else {},
        "sentence_texts": sentence_texts,
    }


def _select_toc_entries_for_sentence(
    toc_rows: List[Dict[str, object]],
    sentence_text: str,
    max_rows: int = 4,
) -> List[Dict[str, object]]:
    if not toc_rows:
        return []
    sentence_norm = _norm_match_text(sentence_text)
    sentence_tokens = _token_set(sentence_text)
    scored: List[Tuple[float, Dict[str, object]]] = []
    for row in toc_rows:
        if not isinstance(row, dict):
            continue
        row_norm = str(row.get("_norm") or "").strip()
        if not row_norm:
            continue
        score = 0.0
        if sentence_norm and row_norm:
            if row_norm in sentence_norm:
                score += 8.0
            elif sentence_norm in row_norm:
                score += 2.0
        if sentence_tokens:
            overlap = sentence_tokens.intersection(_token_set(row_norm))
            if overlap:
                score += float(len(overlap)) / 2.0
        if score > 0.0:
            scored.append((score, row))
    scored.sort(
        key=lambda item: (
            -item[0],
            str(item[1].get("node_type") or "").lower(),
            str(item[1].get("identifier") or "").lower(),
            str(item[1].get("title") or "").lower(),
        )
    )
    out: List[Dict[str, object]] = []
    seen: Set[Tuple[str, str, str]] = set()
    for _, row in scored:
        key = (
            str(row.get("node_type") or "").lower(),
            str(row.get("identifier") or "").lower(),
            str(row.get("title") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "node_type": row.get("node_type"),
                "identifier": row.get("identifier"),
                "title": row.get("title"),
                "path": row.get("path"),
            }
        )
        if len(out) >= max(1, int(max_rows)):
            break
    return out


def _derive_party_from_label(label: str) -> str:
    l = str(label or "").lower()
    if "appellant" in l:
        return "appellant"
    if "respondent" in l:
        return "respondent"
    if "reply" in l:
        return "appellant_reply"
    if "judgment" in l or "case summary" in l:
        return "court"
    if "hearing" in l or "oral argument" in l:
        return "hearing"
    return "unknown"


def _token_lemmas(text: str, nlp: Optional[object] = None) -> List[str]:
    s = _collapse_ws(text)
    if not s:
        return []
    if nlp is not None:
        try:
            doc = nlp(s)
            out: List[str] = []
            for tok in doc:
                if bool(getattr(tok, "is_space", False)) or bool(getattr(tok, "is_punct", False)):
                    continue
                lemma = _collapse_ws(str(getattr(tok, "lemma_", "") or getattr(tok, "text", ""))).lower()
                if lemma:
                    out.append(lemma)
            if out:
                return out
        except Exception:
            pass
    return [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'-]*", s)]


def _contains_seq(tokens: List[str], seq: List[str]) -> bool:
    if not tokens or not seq or len(tokens) < len(seq):
        return False
    n = len(seq)
    for i in range(0, len(tokens) - n + 1):
        if tokens[i : i + n] == seq:
            return True
    return False


def _infer_party_from_doc_context(
    *,
    doc_context: Dict[str, object],
    source_label: str,
    nlp: Optional[object] = None,
) -> Dict[str, object]:
    scores: Dict[str, float] = {"appellant": 0.0, "respondent": 0.0, "court": 0.0}
    evidence: List[str] = []

    def score_text(text: str, weight: float) -> None:
        t = _norm_match_text(text)
        if not t:
            return
        if "appellant" in t:
            scores["appellant"] += weight
        if "respondent" in t:
            scores["respondent"] += weight
        if "judgment" in t or "court of appeal" in t or "high court" in t or "judge" in t:
            scores["court"] += weight * 0.75

    toc_rows = doc_context.get("toc_rows")
    if isinstance(toc_rows, list):
        for row in toc_rows[:80]:
            if not isinstance(row, dict):
                continue
            score_text(str(row.get("path") or row.get("label") or ""), 1.4)
    metadata = doc_context.get("metadata")
    if isinstance(metadata, dict):
        score_text(str(metadata.get("title") or ""), 2.0)
        score_text(str(metadata.get("court") or ""), 1.2)
        score_text(str(metadata.get("citation") or ""), 0.8)

    sentence_texts = doc_context.get("sentence_texts")
    if isinstance(sentence_texts, list):
        for sent in sentence_texts[:40]:
            if not isinstance(sent, str):
                continue
            toks = _token_lemmas(sent, nlp=nlp)
            if not toks:
                continue
            if _contains_seq(toks, ["filing", "party", "appellant"]):
                scores["appellant"] += 10.0
                evidence.append("filing_party:appellant")
            if _contains_seq(toks, ["filing", "party", "respondent"]):
                scores["respondent"] += 10.0
                evidence.append("filing_party:respondent")
            app_hits = sum(1 for t in toks if t == "appellant")
            resp_hits = sum(1 for t in toks if t == "respondent")
            court_hits = sum(1 for t in toks if t in {"court", "judge", "judgment"})
            if app_hits:
                scores["appellant"] += min(2.0, app_hits * 0.25)
            if resp_hits:
                scores["respondent"] += min(2.0, resp_hits * 0.25)
            if court_hits:
                scores["court"] += min(1.5, court_hits * 0.2)

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best_party = ranked[0][0] if ranked else "unknown"
    best_score = float(ranked[0][1]) if ranked else 0.0
    runner_up = float(ranked[1][1]) if len(ranked) > 1 else 0.0

    if best_score < 1.0 or best_score <= runner_up:
        fallback = _derive_party_from_label(source_label)
        if fallback != "unknown":
            return {
                "party": fallback,
                "source": "label_fallback",
                "scores": scores,
                "evidence": evidence,
            }
        return {
            "party": "unknown",
            "source": "unresolved",
            "scores": scores,
            "evidence": evidence,
        }

    return {
        "party": best_party,
        "source": "document_structure",
        "scores": scores,
        "evidence": evidence,
    }


def _anchor_sort_key(anchor: Dict[str, object]) -> Tuple[int, int, int, str]:
    y = int(anchor.get("year") or 0)
    m = int(anchor.get("month") or 99) if anchor.get("month") is not None else 99
    d = int(anchor.get("day") or 99) if anchor.get("day") is not None else 99
    return (y, m, d, str(anchor.get("text") or ""))


def _extract_temporal_anchors_from_sentence(
    sentence_text: str,
    fallback_anchor: Dict[str, object],
    nlp: Optional[object] = None,
) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    seen: Set[Tuple[int, Optional[int], Optional[int], str]] = set()
    default_year = int(fallback_anchor.get("year") or 0) or 1900
    if nlp is not None:
        try:
            doc = nlp(sentence_text)
            ents = [ent for ent in getattr(doc, "ents", []) if str(getattr(ent, "label_", "")) == "DATE"]
            for ent in ents:
                year: Optional[int] = None
                month: Optional[int] = None
                day: Optional[int] = None
                for tok in ent:
                    t = str(getattr(tok, "text", "") or "").strip("[](),.;")
                    if not t:
                        continue
                    tl = t.lower()
                    if tl in _MONTH_TOKEN_TO_INT:
                        month = _MONTH_TOKEN_TO_INT[tl]
                        continue
                    if t.isdigit():
                        v = int(t)
                        if 1800 <= v <= 2200:
                            year = v
                            continue
                        if 1 <= v <= 31 and day is None:
                            day = v
                if year is None and month is not None:
                    year = default_year
                if year is None:
                    continue
                if month is None:
                    day = None
                    precision = "year"
                elif day is None:
                    precision = "month"
                else:
                    precision = "day"
                key = (year, month, day, precision)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "year": year,
                        "month": month,
                        "day": day,
                        "precision": precision,
                        "text": _collapse_ws(str(getattr(ent, "text", "") or "")),
                        "kind": "date_mention",
                    }
                )
        except Exception:
            pass
    if out:
        out.sort(key=_anchor_sort_key)
        return out
    return [dict(fallback_anchor)]


def _build_timeline_facts_for_event(
    *,
    event_id: str,
    sentence_text: str,
    steps: object,
    fallback_anchor: Dict[str, object],
    party: str,
    nlp: Optional[object] = None,
) -> List[Dict[str, object]]:
    anchors = _extract_temporal_anchors_from_sentence(
        sentence_text=sentence_text,
        fallback_anchor=fallback_anchor,
        nlp=nlp,
    )
    step_rows = steps if isinstance(steps, list) else []
    facts: List[Dict[str, object]] = []
    fact_seq = 1
    for step_idx, step in enumerate(step_rows):
        if not isinstance(step, dict):
            continue
        action = _collapse_ws(step.get("action"))
        subjects = sorted(set(_collapse_ws(x) for x in step.get("subjects") or [] if _collapse_ws(x)))
        objects = sorted(set(_collapse_ws(x) for x in step.get("objects") or [] if _collapse_ws(x)))
        purpose = _collapse_ws(step.get("purpose"))
        if not action and not subjects and not objects:
            continue
        for anchor in anchors:
            facts.append(
                {
                    "fact_id": f"{event_id}:f{fact_seq:02d}",
                    "event_id": event_id,
                    "step_index": int(step_idx),
                    "anchor": anchor,
                    "party": party,
                    "subjects": subjects,
                    "action": action or None,
                    "objects": objects,
                    "purpose": purpose or None,
                    "text": sentence_text,
                }
            )
            fact_seq += 1
    return facts


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _try_load_spacy_narrative(model: str = "en_core_web_sm") -> Tuple[Optional[object], Dict[str, object]]:
    info: Dict[str, object] = {"name": "spacy", "model": model}
    try:
        import spacy  # type: ignore

        nlp = spacy.load(model)
        meta = getattr(nlp, "meta", {}) or {}
        info["spacy_version"] = getattr(spacy, "__version__", "")
        info["model_name"] = str(meta.get("name") or model)
        info["model_version"] = str(meta.get("version") or "")
        info["fallback"] = False
        path = getattr(nlp, "path", None)
        if path:
            blob = ""
            meta_path = Path(path) / "meta.json"
            cfg_path = Path(path) / "config.cfg"
            if meta_path.exists():
                blob += meta_path.read_text(encoding="utf-8")
            if cfg_path.exists():
                blob += "\n---\n" + cfg_path.read_text(encoding="utf-8")
            if blob.strip():
                info["model_sha256"] = _sha256_text(blob)
        return nlp, info
    except Exception as e:
        info["fallback"] = True
        info["error"] = f"{type(e).__name__}: {e}"
        return None, info


def _sentence_split_fallback(text: str, nlp: Optional[object] = None) -> List[str]:
    raw = _collapse_ws(text)
    if not raw:
        return []

    if nlp is not None:
        try:
            doc = nlp(raw)
            out = [_collapse_ws(str(getattr(s, "text", "") or "")) for s in getattr(doc, "sents", [])]
            out = [s for s in out if s]
            if out:
                return out
        except Exception:
            pass

    # Worst-case fallback when parser pipeline is unavailable.
    parts = re.split(r"(?<=[.?!;])\s+(?=[A-Z])", raw)
    out: List[str] = []
    for p in parts:
        s = _collapse_ws(p)
        if s:
            out.append(s)
    return out


def _is_narrative_sentence(text: str, nlp: Optional[object] = None) -> bool:
    s = _collapse_ws(text)
    if len(s) < 48:
        return False
    lower = s.lower()
    if "please direct enquiries" in lower:
        return False
    if "this statement is not intended to be a substitute" in lower:
        return False
    if "website:" in lower and "email:" in lower:
        return False
    if "page no" in lower or "name of matter" in lower:
        return False
    if s.count("_") >= 6:
        return False

    # Parser-first gate: use deterministic token/POS cues for proposition-like lines.
    if nlp is not None:
        try:
            doc = nlp(s)
            toks = [t for t in doc if not getattr(t, "is_space", False)]
            if not toks:
                return False
            verbs = [t for t in toks if getattr(t, "pos_", "") in {"VERB", "AUX"}]
            if not verbs:
                return False
            # Reject heading/table-like rows: mostly labels/date fragments with only light auxiliary verbs.
            nounish = sum(1 for t in toks if getattr(t, "pos_", "") in {"PROPN", "NOUN", "NUM"})
            if nounish / float(len(toks)) >= 0.75:
                strong_verbs = [t for t in verbs if (getattr(t, "lemma_", "") or "").lower() not in {"be", "have"}]
                if not strong_verbs:
                    return False
        except Exception:
            # If parser fails on this sentence, fall through to conservative fallback checks.
            pass

    # Skip heading-like lines with sparse lowercase content.
    letters = [ch for ch in s if ch.isalpha()]
    if letters:
        lower_ratio = sum(1 for ch in letters if ch.islower()) / float(len(letters))
        if lower_ratio < 0.25:
            return False
    return True


def _doc_sentences(document_json_path: Path, max_sentences: int, nlp: Optional[object] = None) -> List[str]:
    try:
        payload = json.loads(document_json_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    out: List[str] = []
    sent_rows = payload.get("sentences")
    if isinstance(sent_rows, list):
        for row in sent_rows:
            if not isinstance(row, dict):
                continue
            text = _collapse_ws(row.get("text"))
            if _is_narrative_sentence(text, nlp=nlp):
                out.append(text)
            if len(out) >= max_sentences:
                break
    if out:
        return out

    body = _collapse_ws(payload.get("body"))
    for text in _sentence_split_fallback(body, nlp=nlp):
        if _is_narrative_sentence(text, nlp=nlp):
            out.append(text)
        if len(out) >= max_sentences:
            break
    return out


def _narrative_timeline_events(
    manifest: Dict[str, object],
    ingest_rows: List[Dict[str, object]],
    max_sentences_per_doc: int,
    nlp: Optional[object] = None,
) -> Tuple[List[Dict[str, object]], Dict[str, Dict[str, str]]]:
    by_pdf: Dict[str, str] = {}
    for row in ingest_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") != "ingested":
            continue
        pdf_path = str(row.get("source_pdf") or "").strip()
        doc_json = str(row.get("document_json") or "").strip()
        if pdf_path and doc_json:
            by_pdf[pdf_path] = doc_json

    events: List[Dict[str, object]] = []
    provenance: Dict[str, Dict[str, str]] = {}
    rows = manifest.get("documents")
    if not isinstance(rows, list):
        return events, provenance

    seq = 1
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") != "downloaded":
            continue
        source_pdf = str(row.get("path") or "").strip()
        if not source_pdf.lower().endswith(".pdf"):
            continue
        doc_json = by_pdf.get(source_pdf)
        if not doc_json:
            continue
        date_text = str(row.get("date") or "").strip()
        label = str(row.get("label") or "").strip() or "Case artifact"
        sentences = _doc_sentences(Path(doc_json), max_sentences=max_sentences_per_doc, nlp=nlp)
        for sentence in sentences:
            ev_id = f"narr:{seq:04d}"
            seq += 1
            events.append(
                {
                    "event_id": ev_id,
                    "anchor": _anchor_from_date_text(date_text),
                    "section": "Narrative",
                    "text": sentence,
                    "links": [],
                }
            )
            provenance[ev_id] = {
                "label": label,
                "date": date_text,
                "source_pdf": source_pdf,
                "document_json": doc_json,
            }
    return events, provenance


def _extract_narrative_aoo(
    timeline_events: List[Dict[str, object]],
    out_dir: Path,
    timeout: int,
) -> Dict[str, object]:
    if not timeline_events:
        return {"ok": True, "events": [], "parser": {"kind": "wiki_timeline_aoo_extract", "skipped": "no_timeline_events"}}

    graph_dir = out_dir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    timeline_path = graph_dir / "hca_case_narrative.timeline.json"
    aoo_path = graph_dir / "hca_case_narrative.aoo.json"
    candidates_path = graph_dir / "hca_case_narrative.candidates.empty.json"
    timeline_path.write_text(json.dumps({"events": timeline_events}, indent=2, sort_keys=True), encoding="utf-8")
    candidates_path.write_text(json.dumps({"candidates": []}, indent=2, sort_keys=True), encoding="utf-8")

    cmd = [
        sys.executable,
        str(SENSIBLAW_ROOT / "scripts" / "wiki_timeline_aoo_extract.py"),
        "--timeline",
        str(timeline_path),
        "--candidates",
        str(candidates_path),
        "--out",
        str(aoo_path),
        "--root-actor",
        "High Court of Australia",
        "--root-surname",
        "HCA",
        "--max-events",
        str(max(1, len(timeline_events))),
    ]
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(20, int(timeout)),
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "events": [],
            "error": "wiki_timeline_aoo_extract_failed",
            "stderr": (proc.stderr or "").strip(),
            "stdout": (proc.stdout or "").strip(),
            "timeline": str(timeline_path),
        }
    try:
        payload = json.loads(aoo_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "ok": False,
            "events": [],
            "error": f"aoo_read_failed:{type(e).__name__}",
            "timeline": str(timeline_path),
            "aoo_path": str(aoo_path),
        }
    return {
        "ok": True,
        "events": payload.get("events") if isinstance(payload.get("events"), list) else [],
        "parser": payload.get("parser"),
        "timeline": str(timeline_path),
        "aoo_path": str(aoo_path),
    }


def _build_sb_signal_payload(case_url: str, aoo_payload: Dict[str, object]) -> Dict[str, object]:
    rows = aoo_payload.get("events")
    events = rows if isinstance(rows, list) else []
    signals: List[Dict[str, object]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        steps = ev.get("steps")
        step0 = steps[0] if isinstance(steps, list) and steps and isinstance(steps[0], dict) else {}
        step_subjects = step0.get("subjects") if isinstance(step0, dict) else []
        step_objects = step0.get("objects") if isinstance(step0, dict) else []
        signals.append(
            {
                "signal_id": str(ev.get("event_id") or ""),
                "signal_class": str(ev.get("signal_class") or "unspecified"),
                "anchor": ev.get("anchor"),
                "party": str(ev.get("party") or ""),
                "party_source": str(ev.get("party_source") or ""),
                "section": str(ev.get("section") or ""),
                "text": str(ev.get("text") or ""),
                "action": str(step0.get("action") or ev.get("action") or ""),
                "subjects": list(step_subjects) if isinstance(step_subjects, list) else [],
                "objects": list(step_objects) if isinstance(step_objects, list) else [],
                "citations": list(ev.get("citations") or []),
                "sl_references": list(ev.get("sl_references") or []),
                "legal_section_markers": ev.get("legal_section_markers") if isinstance(ev.get("legal_section_markers"), dict) else {},
                "timeline_facts": list(ev.get("timeline_facts") or []),
                "purpose": step0.get("purpose") if isinstance(step0, dict) else ev.get("purpose"),
                "warnings": list(ev.get("warnings") or []),
            }
        )
    return {
        "ok": True,
        "generated_at": _utc_now_iso(),
        "source": case_url,
        "contract": {
            "kind": "observer_signals",
            "non_authoritative": True,
            "notes": [
                "Signals are derived from artifact status and sentence-local narrative AAO extraction.",
                "These records are suitable for SB observer ingestion and must not be treated as normative truth.",
            ],
        },
        "signals": signals,
    }


def _build_hca_aoo_payload(
    case_url: str,
    manifest: Dict[str, object],
    media_report: Dict[str, object],
    ingest_rows: List[Dict[str, object]],
    out_dir: Path,
    timeout: int,
    narrative_max_sentences_per_doc: int,
) -> Dict[str, object]:
    base_actor = "High Court of Australia"
    base_subjects = [base_actor]
    events: List[Dict[str, object]] = []
    fact_timeline: List[Dict[str, object]] = []

    docs = manifest.get("documents")
    rows = docs if isinstance(docs, list) else []
    event_seq = 1
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        if not label or label.lower() == "case page":
            continue
        status = str(row.get("status") or "")
        anchor = _anchor_from_date_text(row.get("date"))  # type: ignore[arg-type]
        action = _action_for_label(label, status)
        section = _section_for_label(label)
        text = f"{label} ({status or 'unknown'})"
        warnings: List[str] = []
        if status == "missing_url":
            warnings.append("missing_url")
        if status == "error":
            warnings.append("download_error")

        objects = [{"title": label, "source": "hca_case_documents_table"}]
        final_url = str(row.get("final_url") or row.get("url") or "").strip()
        if final_url:
            objects.append({"title": final_url, "source": "artifact_url"})

        purpose = None
        if status == "downloaded":
            purpose = "artifact_downloaded"
        elif status == "missing_url":
            purpose = "artifact_link_missing"
        elif status == "error":
            purpose = "artifact_download_failed"

        ev_id = f"ev:{event_seq:04d}"
        event_seq += 1
        events.append(
            {
                "event_id": ev_id,
                "signal_class": "artifact_status",
                "anchor": anchor,
                "section": section,
                "text": text,
                "actors": [{"label": base_actor, "resolved": base_actor, "role": "subject", "source": "hca_case_ingest"}],
                "action": action,
                "steps": [{"action": action, "subjects": base_subjects, "objects": [label], "purpose": purpose}],
                "chains": [],
                "objects": objects,
                "purpose": purpose,
                "warnings": warnings,
            }
        )

    # Append recording derivatives (transcripts/captions/manifests) as sentence-local event nodes.
    rec_anchor = _anchor_from_date_text("2025-08-07")
    for row in media_report.get("transcript_pages", []) if isinstance(media_report, dict) else []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "Transcript").strip() or "Transcript"
        ev_id = f"ev:{event_seq:04d}"
        event_seq += 1
        action = _action_for_label("transcript", "downloaded")
        events.append(
            {
                "event_id": ev_id,
                "signal_class": "recording_artifact",
                "anchor": rec_anchor,
                "section": "Recordings",
                "text": f"Transcript artifact extracted: {label}",
                "actors": [{"label": base_actor, "resolved": base_actor, "role": "subject", "source": "hca_case_ingest"}],
                "action": action,
                "steps": [{"action": action, "subjects": base_subjects, "objects": [label], "purpose": "recording_transcript_extracted"}],
                "chains": [],
                "objects": [
                    {"title": label, "source": "hca_av_transcript"},
                    {"title": str(row.get("path") or ""), "source": "artifact_path"},
                ],
                "purpose": "recording_transcript_extracted",
                "warnings": [],
            }
        )

    for row in media_report.get("captions", []) if isinstance(media_report, dict) else []:
        if not isinstance(row, dict):
            continue
        lang = str(row.get("lang") or "und")
        label = f"Vimeo captions ({lang})"
        ev_id = f"ev:{event_seq:04d}"
        event_seq += 1
        action = _action_for_label("caption", "downloaded")
        events.append(
            {
                "event_id": ev_id,
                "signal_class": "recording_artifact",
                "anchor": rec_anchor,
                "section": "Recordings",
                "text": f"Caption track extracted: {lang}",
                "actors": [{"label": base_actor, "resolved": base_actor, "role": "subject", "source": "hca_case_ingest"}],
                "action": action,
                "steps": [{"action": action, "subjects": base_subjects, "objects": [label], "purpose": "recording_caption_extracted"}],
                "chains": [],
                "objects": [
                    {"title": label, "source": "vimeo_text_track"},
                    {"title": str(row.get("vtt") or ""), "source": "artifact_path"},
                ],
                "purpose": "recording_caption_extracted",
                "warnings": [],
            }
        )

    for row in media_report.get("stream_manifests", []) if isinstance(media_report, dict) else []:
        if not isinstance(row, dict):
            continue
        proto = str(row.get("protocol") or "stream")
        cdn = str(row.get("cdn") or "cdn")
        label = f"{proto.upper()} manifest ({cdn})"
        ev_id = f"ev:{event_seq:04d}"
        event_seq += 1
        action = _action_for_label("manifest", "downloaded")
        events.append(
            {
                "event_id": ev_id,
                "signal_class": "recording_artifact",
                "anchor": rec_anchor,
                "section": "Recordings",
                "text": f"Streaming manifest captured: {label}",
                "actors": [{"label": base_actor, "resolved": base_actor, "role": "subject", "source": "hca_case_ingest"}],
                "action": action,
                "steps": [{"action": action, "subjects": base_subjects, "objects": [label], "purpose": "recording_stream_manifest_captured"}],
                "chains": [],
                "objects": [
                    {"title": label, "source": "vimeo_stream_manifest"},
                    {"title": str(row.get("path") or ""), "source": "artifact_path"},
                ],
                "purpose": "recording_stream_manifest_captured",
                "warnings": [],
            }
        )

    # Second lane: sentence-local narrative extraction from ingested documents.
    narrative_nlp, narrative_parser_info = _try_load_spacy_narrative("en_core_web_sm")
    narr_timeline, narr_provenance = _narrative_timeline_events(
        manifest=manifest,
        ingest_rows=ingest_rows,
        max_sentences_per_doc=max(1, int(narrative_max_sentences_per_doc)),
        nlp=narrative_nlp,
    )
    narr_parse = _extract_narrative_aoo(
        timeline_events=narr_timeline,
        out_dir=out_dir,
        timeout=timeout,
    )
    narr_rows = narr_parse.get("events")
    sl_reference_cache: Dict[str, List[Dict[str, object]]] = {}
    doc_context_cache: Dict[str, Dict[str, object]] = {}
    party_cache: Dict[str, Dict[str, object]] = {}
    if isinstance(narr_rows, list):
        for n_ev in narr_rows:
            if not isinstance(n_ev, dict):
                continue
            src_id = str(n_ev.get("event_id") or "")
            src = narr_provenance.get(src_id, {})
            label = str(src.get("label") or "").strip()
            source_pdf = str(src.get("source_pdf") or "").strip()
            document_json = str(src.get("document_json") or "").strip()
            if document_json and document_json not in doc_context_cache:
                doc_context_cache[document_json] = _collect_doc_context(document_json)
            if document_json and document_json not in party_cache:
                party_cache[document_json] = _infer_party_from_doc_context(
                    doc_context=doc_context_cache.get(document_json, {}),
                    source_label=label,
                    nlp=narrative_nlp,
                )
            party_info = party_cache.get(document_json, _infer_party_from_doc_context(doc_context={}, source_label=label, nlp=narrative_nlp))
            party = str(party_info.get("party") or "unknown")

            objects = n_ev.get("objects")
            merged_objects = list(objects) if isinstance(objects, list) else []
            base_text = str(n_ev.get("text") or "")
            citations = _extract_citations(
                base_text,
                source_document_json=document_json,
                source_pdf=source_pdf,
            )
            sl_references: List[Dict[str, object]] = []
            if document_json:
                if document_json not in sl_reference_cache:
                    sl_reference_cache[document_json] = _collect_sl_reference_rows(document_json)
                sl_references = _select_sl_references_for_sentence(
                    sl_reference_cache.get(document_json, []),
                    base_text,
                    source_document_json=document_json,
                    source_pdf=source_pdf,
                )

            filtered_objects: List[Dict[str, object]] = []
            for obj in merged_objects:
                if not isinstance(obj, dict):
                    continue
                title = str(obj.get("title") or "").strip()
                if _looks_like_citation_text(title):
                    for c in _extract_citations(
                        title,
                        source_document_json=document_json,
                        source_pdf=source_pdf,
                    ):
                        c["source"] = "object_cleanup"
                        citations.append(c)
                    continue
                filtered_objects.append(obj)
            merged_objects = filtered_objects
            dedup_citations: List[Dict[str, object]] = []
            seen_c = set()
            for c in citations:
                if not isinstance(c, dict):
                    continue
                k = (str(c.get("kind") or ""), str(c.get("text") or "").lower())
                if k in seen_c:
                    continue
                seen_c.add(k)
                dedup_citations.append(c)
            citations = dedup_citations

            doc_ctx = doc_context_cache.get(document_json, {"toc_rows": [], "metadata": {}})
            toc_context = _select_toc_entries_for_sentence(
                doc_ctx.get("toc_rows") if isinstance(doc_ctx, dict) else [],
                base_text,
                max_rows=4,
            )
            citation_prefixes = sorted(
                {
                    _collapse_ws(str(c.get("prefix") or ""))
                    for c in citations
                    if isinstance(c, dict) and _collapse_ws(str(c.get("prefix") or ""))
                }
            )
            sl_reference_lanes = sorted(
                {
                    _collapse_ws(str(r.get("lane") or ""))
                    for r in sl_references
                    if isinstance(r, dict) and _collapse_ws(str(r.get("lane") or ""))
                }
            )
            provision_ids = sorted(
                {
                    _collapse_ws(str(r.get("provision_stable_id") or ""))
                    for r in sl_references
                    if isinstance(r, dict) and _collapse_ws(str(r.get("provision_stable_id") or ""))
                }
            )
            rule_atom_ids = sorted(
                {
                    _collapse_ws(str(r.get("rule_atom_stable_id") or ""))
                    for r in sl_references
                    if isinstance(r, dict) and _collapse_ws(str(r.get("rule_atom_stable_id") or ""))
                }
            )

            if label:
                merged_objects.append({"title": label, "source": "narrative_source_label"})
            if source_pdf:
                merged_objects.append({"title": source_pdf, "source": "source_pdf"})
            if document_json:
                merged_objects.append({"title": document_json, "source": "source_document_json"})

            steps = n_ev.get("steps")
            timeline_facts = _build_timeline_facts_for_event(
                event_id=f"ev:{event_seq:04d}",
                sentence_text=base_text,
                steps=steps,
                fallback_anchor=n_ev.get("anchor") if isinstance(n_ev.get("anchor"), dict) else _anchor_from_date_text(src.get("date")),
                party=party,
                nlp=narrative_nlp,
            )
            warnings = n_ev.get("warnings")
            ev_id = f"ev:{event_seq:04d}"
            event_seq += 1
            # Rewrite fact IDs with final event_id now that it is assigned.
            fixed_facts: List[Dict[str, object]] = []
            for idx, fact in enumerate(timeline_facts, start=1):
                if not isinstance(fact, dict):
                    continue
                row = dict(fact)
                row["event_id"] = ev_id
                row["fact_id"] = f"{ev_id}:f{idx:02d}"
                fixed_facts.append(row)
            timeline_facts = fixed_facts
            fact_timeline.extend(timeline_facts)
            events.append(
                {
                    "event_id": ev_id,
                    "signal_class": "narrative_sentence",
                    "anchor": n_ev.get("anchor"),
                    "section": n_ev.get("section") or "Narrative",
                    "text": n_ev.get("text"),
                    "actors": n_ev.get("actors") if isinstance(n_ev.get("actors"), list) else [],
                    "action": n_ev.get("action"),
                    "steps": steps if isinstance(steps, list) else [],
                    "chains": n_ev.get("chains") if isinstance(n_ev.get("chains"), list) else [],
                    "objects": merged_objects,
                    "citations": citations,
                    "sl_references": sl_references,
                    "party": party,
                    "party_source": str(party_info.get("source") or ""),
                    "party_scores": dict(party_info.get("scores") or {}) if isinstance(party_info.get("scores"), dict) else {},
                    "party_evidence": list(party_info.get("evidence") or []) if isinstance(party_info.get("evidence"), list) else [],
                    "toc_context": toc_context,
                    "legal_section_markers": {
                        "citation_prefixes": citation_prefixes,
                        "sl_reference_lanes": sl_reference_lanes,
                        "provision_stable_ids": provision_ids,
                        "rule_atom_stable_ids": rule_atom_ids,
                    },
                    "timeline_facts": timeline_facts,
                    "purpose": n_ev.get("purpose") or "artifact_narrative_extracted",
                    "warnings": warnings if isinstance(warnings, list) else [],
                }
            )

    def sort_key(e: Dict[str, object]) -> tuple:
        a = e.get("anchor") if isinstance(e, dict) else {}
        if not isinstance(a, dict):
            a = {}
        y = int(a.get("year") or 0)
        m = int(a.get("month") or 99) if a.get("month") is not None else 99
        d = int(a.get("day") or 99) if a.get("day") is not None else 99
        return (y, m, d, str(e.get("event_id") or ""))

    events.sort(key=sort_key)
    fact_timeline.sort(
        key=lambda row: (
            _anchor_sort_key(row.get("anchor") if isinstance(row, dict) and isinstance(row.get("anchor"), dict) else {}),
            str(row.get("fact_id") or ""),
        )
    )
    return {
        "root_actor": {"label": "AA v Diocese (S94/2025)", "surname": "HCA"},
        "events": events,
        "fact_timeline": fact_timeline,
        "parser": {
            "kind": "hca_case_bundle_adapter",
            "non_authoritative": True,
            "non_causal": True,
            "source": case_url,
            "generated_at": _utc_now_iso(),
            "lanes": ["artifact_status", "recording_artifact", "narrative_sentence"],
            "narrative": {
                "timeline_events": len(narr_timeline),
                "extracted_events": len(narr_rows) if isinstance(narr_rows, list) else 0,
                "fact_timeline_rows": len(fact_timeline),
                "max_sentences_per_doc": int(narrative_max_sentences_per_doc),
                "timeline_path": narr_parse.get("timeline"),
                "aoo_path": narr_parse.get("aoo_path"),
                "parser": narr_parse.get("parser"),
                "sentence_filter_parser": narrative_parser_info,
                "wiki_connector": {
                    "script": str(SENSIBLAW_ROOT / "scripts" / "wiki_pull_api.py"),
                    "preferred_driver": "pywikibot",
                    "wiki": "enwiki",
                },
                "error": narr_parse.get("error"),
            },
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Download + ingest HCA case bundle and emit a demo graph.")
    ap.add_argument("--case-url", default=CASE_URL_DEFAULT, help="HCA case page URL")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("SensibLaw/demo/ingest/hca_case_s942025"),
        help="Output demo folder",
    )
    ap.add_argument("--timeout", type=int, default=60, help="Per-request timeout seconds")
    ap.add_argument(
        "--dot-bin",
        default=None,
        help="Explicit Graphviz dot binary path (or set SENSIBLAW_DOT_BIN / GRAPHVIZ_DOT).",
    )
    ap.add_argument(
        "--no-video-download",
        action="store_true",
        help="Do not download the Vimeo MP4 stream; still fetch metadata/captions when available.",
    )
    ap.add_argument(
        "--aoo-out",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json"),
        help="Write an AAO payload for the Svelte wiki-timeline visualizer.",
    )
    ap.add_argument(
        "--narrative-max-sentences-per-doc",
        type=int,
        default=14,
        help="Max narrative sentences per ingested PDF artifact for AAO narrative lane.",
    )
    ap.add_argument(
        "--sb-signals-out",
        type=Path,
        default=None,
        help="Optional observer-signal payload path for SB ingestion (default: <out-dir>/sb_signals.json).",
    )
    args = ap.parse_args(argv)

    out_dir = args.out_dir
    raw_dir = out_dir / "raw"
    ingest_dir = out_dir / "ingest"
    graph_dir = out_dir / "graph"
    media_dir = out_dir / "media"
    ingest_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    plan = _build_doc_plan(args.case_url)
    manifest: Dict[str, object] = {
        "ok": True,
        "generated_at": _utc_now_iso(),
        "case_url": args.case_url,
        "documents": [],
        "discovery": {},
        "notes": [
            "Second-pass case-page discovery used for missing URLs where possible.",
            "Missing URLs remain listed for manual follow-up.",
        ],
    }

    downloaded_paths: List[Path] = []
    case_html = ""

    # Fetch case page first for second-pass URL discovery.
    case_entry = next((x for x in plan if str(x.get("label") or "").lower() == "case page"), None)
    if case_entry and case_entry.get("url"):
        case_url = str(case_entry.get("url"))
        case_out = raw_dir / "undated_Case_page.html"
        entry = {"date": "undated", "label": "Case page", "url": case_url}
        try:
            dl = _download(case_url, case_out, timeout=int(args.timeout))
            downloaded_paths.append(case_out)
            case_html = case_out.read_text(encoding="utf-8", errors="replace")
            entry.update({"status": "downloaded", **dl})
            print(f"[downloaded] Case page -> {case_out.name} ({dl.get('bytes')} bytes)")
        except Exception as e:
            entry.update({"status": "error", "error": f"{type(e).__name__}: {e}"})
            print(f"[error] Case page: {type(e).__name__}: {e}")
        manifest["documents"].append(entry)

    # Apply case-page second pass to fill missing URLs (and align hearing links).
    discovery: Dict[str, object] = {}
    if case_html:
        discovery = _apply_case_page_discovery(plan, case_html, args.case_url)
    manifest["discovery"] = discovery

    # Download documents from plan (excluding case page already handled).
    for row in plan:
        label = str(row.get("label") or "document")
        if label.lower() == "case page":
            continue
        date = row.get("date") or "undated"
        url = row.get("url")
        entry: Dict[str, object] = {"date": date, "label": label, "url": url}
        if not url:
            entry["status"] = "missing_url"
            manifest["documents"].append(entry)
            print(f"[skip] {label}: no URL")
            continue
        try:
            fetched = _fetch(str(url), timeout=int(args.timeout))
            final_url = str(fetched["final_url"])
            content_type = str(fetched["content_type"])
            ext = _guess_ext(final_url, content_type)
            stem = _safe_name(f"{date}_{label}")
            out_path = raw_dir / f"{stem}{ext}"
            out_path.write_bytes(fetched["data"])  # type: ignore[index]
            downloaded_paths.append(out_path)
            entry.update(
                {
                    "status": "downloaded",
                    "final_url": final_url,
                    "content_type": content_type,
                    "bytes": int(fetched["bytes"]),
                    "path": str(out_path),
                }
            )
            print(f"[downloaded] {label} -> {out_path.name} ({fetched['bytes']} bytes)")
        except urllib.error.HTTPError as e:
            entry["status"] = "error"
            entry["error"] = f"HTTPError {e.code}: {e.reason}"
            print(f"[error] {label}: HTTP {e.code}")
        except Exception as e:  # pragma: no cover - defensive
            entry["status"] = "error"
            entry["error"] = f"{type(e).__name__}: {e}"
            print(f"[error] {label}: {type(e).__name__}: {e}")
        manifest["documents"].append(entry)

    # Extract Vimeo/media artifacts (recording URL, embed, captions, transcript, optional video).
    media_report: Dict[str, object] = {}
    if case_html:
        media_report = _extract_media(
            case_url=args.case_url,
            case_html=case_html,
            discovery=discovery,
            raw_dir=raw_dir,
            media_dir=media_dir,
            timeout=int(args.timeout),
            download_video=not args.no_video_download,
        )
        (media_dir / "media_report.json").write_text(json.dumps(media_report, indent=2, sort_keys=True), encoding="utf-8")

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    # Ingest PDFs and build graph.
    db_path = ingest_dir / "ingest.sqlite"
    graph = Graph()
    ingest_rows: List[Dict[str, object]] = []
    for pdf_path in sorted(_iter_pdfs(downloaded_paths)):
        try:
            doc, stored_id = process_pdf(pdf_path, db_path=db_path)
            ingest_document(doc, graph)
            out_doc = ingest_dir / f"{_safe_name(pdf_path.stem)}.document.json"
            out_doc.write_text(json.dumps(doc.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
            ingest_rows.append(
                {
                    "source_pdf": str(pdf_path),
                    "status": "ingested",
                    "doc_id": stored_id,
                    "canonical_id": doc.metadata.canonical_id,
                    "citation": doc.metadata.citation,
                    "document_json": str(out_doc),
                }
            )
            print(f"[ingested] {pdf_path.name}")
        except Exception as e:  # pragma: no cover - defensive
            ingest_rows.append({"source_pdf": str(pdf_path), "status": "error", "error": f"{type(e).__name__}: {e}"})
            print(f"[ingest-error] {pdf_path.name}: {type(e).__name__}: {e}")

    (ingest_dir / "ingest_report.json").write_text(json.dumps({"rows": ingest_rows}, indent=2, sort_keys=True), encoding="utf-8")

    graph_json = _graph_payload(graph)
    graph_json_path = graph_dir / "case_bundle.graph.json"
    graph_json_path.write_text(json.dumps(graph_json, indent=2, sort_keys=True), encoding="utf-8")

    dot_text = _graph_dot(graph_json)
    dot_path = graph_dir / "case_bundle.graph.dot"
    dot_path.write_text(dot_text, encoding="utf-8")

    svg_path = graph_dir / "case_bundle.graph.svg"
    svg_status: Dict[str, object] = {"status": "skipped"}
    dot_bin = _resolve_dot_binary(args.dot_bin)
    try:
        if not dot_bin:
            raise FileNotFoundError("dot binary not found")
        proc = subprocess.run(
            [dot_bin, "-Tsvg", str(dot_path), "-o", str(svg_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            svg_status = {"status": "rendered", "path": str(svg_path), "dot_bin": dot_bin}
        else:
            svg_status = {
                "status": "dot_error",
                "code": proc.returncode,
                "stderr": (proc.stderr or "").strip(),
                "dot_bin": dot_bin,
            }
    except FileNotFoundError:
        svg_status = {"status": "dot_not_found", "dot_bin": dot_bin}

    summary = {
        "ok": True,
        "generated_at": _utc_now_iso(),
        "out_dir": str(out_dir),
        "downloaded_total": len([d for d in manifest.get("documents", []) if isinstance(d, dict) and d.get("status") == "downloaded"]),
        "pdf_total": len(list(_iter_pdfs(downloaded_paths))),
        "ingested_total": len([r for r in ingest_rows if r.get("status") == "ingested"]),
        "graph_nodes": len(graph_json.get("nodes", [])),
        "graph_edges": len(graph_json.get("edges", [])),
        "graph_json": str(graph_json_path),
        "graph_dot": str(dot_path),
        "graph_svg": svg_status,
        "manifest": str(out_dir / "manifest.json"),
        "ingest_report": str(ingest_dir / "ingest_report.json"),
        "media_report": str(media_dir / "media_report.json") if media_report else None,
        "vimeo_players": len((media_report or {}).get("player_urls", [])) if isinstance(media_report, dict) else 0,
        "videos_downloaded": len((media_report or {}).get("videos", [])) if isinstance(media_report, dict) else 0,
        "captions_downloaded": len((media_report or {}).get("captions", [])) if isinstance(media_report, dict) else 0,
    }

    aoo_payload = _build_hca_aoo_payload(
        case_url=args.case_url,
        manifest=manifest,
        media_report=media_report or {},
        ingest_rows=ingest_rows,
        out_dir=out_dir,
        timeout=int(args.timeout),
        narrative_max_sentences_per_doc=int(args.narrative_max_sentences_per_doc),
    )
    args.aoo_out.parent.mkdir(parents=True, exist_ok=True)
    args.aoo_out.write_text(json.dumps(aoo_payload, indent=2, sort_keys=True), encoding="utf-8")
    summary["aoo_payload"] = str(args.aoo_out)
    summary["aoo_events"] = len(aoo_payload.get("events", [])) if isinstance(aoo_payload, dict) else 0
    signal_counts: Dict[str, int] = {}
    for ev in aoo_payload.get("events", []) if isinstance(aoo_payload, dict) else []:
        if not isinstance(ev, dict):
            continue
        k = str(ev.get("signal_class") or "unspecified")
        signal_counts[k] = int(signal_counts.get(k, 0)) + 1
    summary["aoo_signal_counts"] = signal_counts

    sb_signals_out = args.sb_signals_out if args.sb_signals_out else (out_dir / "sb_signals.json")
    sb_payload = _build_sb_signal_payload(args.case_url, aoo_payload)
    sb_signals_out.parent.mkdir(parents=True, exist_ok=True)
    sb_signals_out.write_text(json.dumps(sb_payload, indent=2, sort_keys=True), encoding="utf-8")
    summary["sb_signals"] = str(sb_signals_out)
    summary["sb_signal_total"] = len(sb_payload.get("signals", [])) if isinstance(sb_payload, dict) else 0

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
