#!/usr/bin/env node
/**
 * Offline parity checker for wiki timeline routes.
 *
 * Extracts embedded payloads from checkpoint HTML files, normalises them to the
 * same shape as the Svelte route loader, and compares sha256 hashes against the
 * current deterministic artifacts.
 *
 * Default checkpoints:
 *   checkpoints/page_20260304_214705/wiki-timeline.html
 *   checkpoints/page_20260304_214705/wiki-timeline-aoo.html
 *   checkpoints/page_20260304_214705/wiki-timeline-aoo-all.html
 *
 * Default artifacts:
 *   SensibLaw/.cache_local/wiki_timeline_gwb.json
 *   SensibLaw/.cache_local/wiki_timeline_gwb_aoo.json
 *   SensibLaw/.cache_local/wiki_timeline_gwb_aoo_all.json
 *
 * Usage:
 *   node SensibLaw/scripts/check_wiki_timeline_parity_offline.js
 *
 * Optional env:
 *   CHECKPOINT_BASE=checkpoints/page_20260304_214705
 *   ARTIFACT_BASE=SensibLaw/.cache_local
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const CHECKPOINT_BASE = process.env.CHECKPOINT_BASE || "checkpoints/page_20260304_214705";
const ARTIFACT_BASE = process.env.ARTIFACT_BASE || "SensibLaw/.cache_local";

const ROUTES = [
  { html: "wiki-timeline.html", artifact: "wiki_timeline_gwb.json" },
  { html: "wiki-timeline-aoo.html", artifact: "wiki_timeline_gwb_aoo.json" },
  { html: "wiki-timeline-aoo-all.html", artifact: "wiki_timeline_gwb_aoo_all.json" },
];

const PAYLOAD_RE = /payload:\s*(\{[\s\S]*?\})\s*,relPath:/;

const hash = (obj) => crypto.createHash("sha256").update(JSON.stringify(obj)).digest("hex");

function loadArtifact(relPath) {
  const raw = fs.readFileSync(relPath, "utf8");
  const parsed = JSON.parse(raw);
  const snapshot = parsed.snapshot || {};
  const events = Array.isArray(parsed.events) ? parsed.events : [];

  const outEvents = [];
  for (const e of events) {
    if (!e || typeof e !== "object") continue;
    const event_id = String(e.event_id ?? "").trim();
    const text = String(e.text ?? "").trim();
    if (!event_id || !text) continue;
    const section = String(e.section ?? "").trim() || "(unknown)";
    const a = e.anchor || {};
    const anchor = {
      year: Number(a.year ?? 0) || 0,
      month: Number.isFinite(Number(a.month)) ? Number(a.month) : null,
      day: Number.isFinite(Number(a.day)) ? Number(a.day) : null,
      precision: a.precision === "day" || a.precision === "month" ? a.precision : "year",
      text: String(a.text ?? ""),
      kind: String(a.kind ?? ""),
    };
    const links = Array.isArray(e.links) ? e.links.map((x) => String(x)).filter(Boolean) : [];
    outEvents.push({ event_id, anchor, section, text, links });
  }

  outEvents.sort((a, b) => {
    const ka = (a.anchor.year || 9999) * 10000 + (a.anchor.month ?? 99) * 100 + (a.anchor.day ?? 99);
    const kb = (b.anchor.year || 9999) * 10000 + (b.anchor.month ?? 99) * 100 + (b.anchor.day ?? 99);
    return ka - kb || a.event_id.localeCompare(b.event_id);
  });

  return {
    snapshot: {
      title: typeof snapshot.title === "string" ? snapshot.title : null,
      wiki: typeof snapshot.wiki === "string" ? snapshot.wiki : null,
      revid: Number.isFinite(Number(snapshot.revid)) ? Number(snapshot.revid) : null,
      source_url: typeof snapshot.source_url === "string" ? snapshot.source_url : null,
    },
    events: outEvents,
  };
}

function extractPayload(htmlPath) {
  const src = fs.readFileSync(htmlPath, "utf8");
  const match = PAYLOAD_RE.exec(src);
  if (!match) {
    throw new Error(`payload not found in ${htmlPath}`);
  }
  return vm.runInNewContext(`(${match[1]})`, { __proto__: null });
}

function normalizeSnapshot(raw) {
  const events = Array.isArray(raw.events) ? raw.events : [];
  const snapshot = raw.snapshot || {};
  const outEvents = [];
  for (const e of events) {
    if (!e || typeof e !== "object") continue;
    const event_id = String(e.event_id ?? "").trim();
    const text = String(e.text ?? "").trim();
    if (!event_id || !text) continue;
    const section = String(e.section ?? "").trim() || "(unknown)";
    const a = e.anchor || {};
    const anchor = {
      year: Number(a.year ?? 0) || 0,
      month: Number.isFinite(Number(a.month)) ? Number(a.month) : null,
      day: Number.isFinite(Number(a.day)) ? Number(a.day) : null,
      precision: a.precision === "day" || a.precision === "month" ? a.precision : "year",
      text: String(a.text ?? ""),
      kind: String(a.kind ?? ""),
    };
    const links = Array.isArray(e.links) ? e.links.map((x) => String(x)).filter(Boolean) : [];
    outEvents.push({ event_id, anchor, section, text, links });
  }

  outEvents.sort((a, b) => {
    const ka = (a.anchor.year || 9999) * 10000 + (a.anchor.month ?? 99) * 100 + (a.anchor.day ?? 99);
    const kb = (b.anchor.year || 9999) * 10000 + (b.anchor.month ?? 99) * 100 + (b.anchor.day ?? 99);
    return ka - kb || a.event_id.localeCompare(b.event_id);
  });

  return {
    snapshot: {
      title: typeof snapshot.title === "string" ? snapshot.title : null,
      wiki: typeof snapshot.wiki === "string" ? snapshot.wiki : null,
      revid: Number.isFinite(Number(snapshot.revid)) ? Number(snapshot.revid) : null,
      source_url: typeof snapshot.source_url === "string" ? snapshot.source_url : null,
    },
    events: outEvents,
  };
}

function main() {
  let failures = 0;
  for (const route of ROUTES) {
    const htmlPath = path.resolve(CHECKPOINT_BASE, route.html);
    const artifactPath = path.resolve(ARTIFACT_BASE, route.artifact);
    const snap = normalizeSnapshot(extractPayload(htmlPath));
    const cur = loadArtifact(artifactPath);
    const hSnap = hash(snap);
    const hCur = hash(cur);
    const ok = hSnap === hCur;
    console.log(
      `${route.html} :: events snap=${snap.events.length} cur=${cur.events.length} hash_equal=${ok ? "YES" : "NO"}`
    );
    if (!ok) {
      console.log(`  snap=${hSnap}`);
      console.log(`  cur =${hCur}`);
      failures += 1;
    }
  }
  if (failures > 0) {
    console.error(`parity FAILED for ${failures} route(s)`);
    process.exit(1);
  }
  console.log("parity OK");
}

main();
