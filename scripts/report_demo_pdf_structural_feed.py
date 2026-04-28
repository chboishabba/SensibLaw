#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cli_runtime import build_progress_callback, configure_cli_logging

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.pdf_ingest import extract_pdf_text, iter_process_pdf
from src.sensiblaw.interfaces import collect_canonical_structural_ir_feed


DEFAULT_PDFS = (
    _SENSIBLAW_ROOT / "Mabo [No 2] - [1992] HCA 23.pdf",
    _SENSIBLAW_ROOT / "Plaintiff S157_2002 v Commonwealth - [2003] HCA 2.pdf",
    _SENSIBLAW_ROOT / "test_generic_docs" / "JavaCrust Project Idea.pdf",
)


def _emit(progress_callback, stage: str, **details: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, details)


@dataclass
class _TimedEmitter:
    interval_seconds: float
    last_emit_monotonic: float = 0.0

    def should_emit(self, *, force: bool = False) -> bool:
        if force:
            self.last_emit_monotonic = time.monotonic()
            return True
        now = time.monotonic()
        if self.last_emit_monotonic == 0.0 or (now - self.last_emit_monotonic) >= self.interval_seconds:
            self.last_emit_monotonic = now
            return True
        return False


def _safe_rate(numerator: int | float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    if numerator <= 0:
        return None
    return float(numerator) / float(denominator)


def _safe_eta(remaining: int | float, rate: float | None) -> float | None:
    if rate is None or rate <= 0:
        return None
    if remaining <= 0:
        return 0.0
    return float(remaining) / rate


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def _preflight_pdf_counts(
    pdf: Path,
    progress_callback,
    *,
    progress_interval_seconds: float,
    pdf_index: int | None = None,
    pdf_total: int | None = None,
) -> dict[str, int]:
    started = time.monotonic()
    total_pages = 0
    total_words = 0
    total_chars = 0
    pdf_page_total = None
    try:
        from src.pdf_ingest import _count_pdf_pages  # local import to keep script surface narrow

        pdf_page_total = _count_pdf_pages(pdf)
    except Exception:
        pdf_page_total = None
    emitter = _TimedEmitter(interval_seconds=max(0.1, progress_interval_seconds))
    for page in extract_pdf_text(pdf):
        total_pages += 1
        heading_text = str(page.get("heading") or "")
        body_text = str(page.get("text") or "")
        combined = f"{heading_text} {body_text}"
        total_chars += len(heading_text) + len(body_text)
        total_words += len([token for token in combined.split() if token.strip()])
        if emitter.should_emit():
            elapsed_seconds = round(time.monotonic() - started, 3)
            page_value = int(page.get("page") or total_pages)
            page_rate = _safe_rate(page_value, elapsed_seconds)
            eta_seconds = _safe_eta(
                (pdf_page_total - page_value) if pdf_page_total is not None else 0,
                page_rate,
            )
            _emit(
                progress_callback,
                "demo_pdf_preflight",
                section="demo_pdf_feed",
                completed=total_words,
                total=None,
                status="preflight",
                message=f"{pdf.name}: preflight page={page.get('page')} words={total_words}",
                pdf=str(pdf),
                pdf_index=pdf_index,
                pdf_total=pdf_total,
                page=page_value,
                total_pages=total_pages,
                pdf_page_total=pdf_page_total,
                total_words=total_words,
                total_chars=total_chars,
                elapsed_seconds=elapsed_seconds,
                eta_seconds=round(eta_seconds, 3) if eta_seconds is not None else None,
            )
    return {
        "total_pages": total_pages,
        "total_words": total_words,
        "total_chars": total_chars,
    }


def _preflight_all_pdfs(
    pdfs: tuple[Path, ...],
    progress_callback,
    *,
    progress_interval_seconds: float,
) -> tuple[dict[Path, dict[str, int]], dict[str, int]]:
    totals_by_pdf: dict[Path, dict[str, int]] = {}
    overall_pages = 0
    overall_words = 0
    overall_chars = 0
    pdf_total = len(pdfs)
    for pdf_index, pdf in enumerate(pdfs, start=1):
        _emit(
            progress_callback,
            "demo_pdf_preflight_started",
            section="demo_pdf_feed",
            completed=pdf_index - 1,
            total=pdf_total,
            status="preflight",
            message=f"Preflighting {pdf.name}",
            pdf=str(pdf),
            pdf_index=pdf_index,
            pdf_total=pdf_total,
        )
        pdf_totals = _preflight_pdf_counts(
            pdf,
            progress_callback,
            progress_interval_seconds=progress_interval_seconds,
            pdf_index=pdf_index,
            pdf_total=pdf_total,
        )
        totals_by_pdf[pdf] = pdf_totals
        overall_pages += pdf_totals["total_pages"]
        overall_words += pdf_totals["total_words"]
        overall_chars += pdf_totals["total_chars"]
        _emit(
            progress_callback,
            "demo_pdf_preflight_finished",
            section="demo_pdf_feed",
            completed=pdf_index,
            total=pdf_total,
            status="ok",
            message=(
                f"{pdf.name}: preflight totals pages={pdf_totals['total_pages']} "
                f"words={pdf_totals['total_words']} chars={pdf_totals['total_chars']} "
                f"overall_docs={pdf_index}/{pdf_total}"
            ),
            pdf=str(pdf),
            pdf_index=pdf_index,
            pdf_total=pdf_total,
            total_pages=pdf_totals["total_pages"],
            total_words=pdf_totals["total_words"],
            total_chars=pdf_totals["total_chars"],
            overall_total_pages=overall_pages,
            overall_total_words=overall_words,
            overall_total_chars=overall_chars,
        )
    return totals_by_pdf, {
        "total_pages": overall_pages,
        "total_words": overall_words,
        "total_chars": overall_chars,
    }


def _build_entry(
    pdf: Path,
    output_json: Path,
    progress_callback,
    *,
    totals: dict[str, int],
    overall_totals: dict[str, int],
    completed_words_before: int,
    completed_chars_before: int,
    batch_started_at: float,
    progress_interval_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    document = None
    stored_id = None
    emitter = _TimedEmitter(interval_seconds=max(0.1, progress_interval_seconds))
    last_emitted_words_seen = 0
    extract_started = time.monotonic()
    for stage, payload in iter_process_pdf(pdf, output=output_json, db_path=None):
        if stage == "extraction_progress":
            words_seen = int(payload.get("words_seen") or 0)
            chars_seen = int(payload.get("char_count") or 0)
            page = payload.get("page")
            pages_seen = payload.get("pages_seen")
            total_pages = payload.get("total_pages")
            if emitter.should_emit():
                delta_words = max(0, words_seen - last_emitted_words_seen)
                overall_words_seen = completed_words_before + words_seen
                overall_chars_seen = completed_chars_before + chars_seen
                elapsed_seconds = round(time.monotonic() - extract_started, 3)
                word_rate = _safe_rate(words_seen, elapsed_seconds)
                eta_seconds = _safe_eta(totals["total_words"] - words_seen, word_rate)
                overall_elapsed_seconds = round(time.monotonic() - batch_started_at, 3)
                overall_word_rate = _safe_rate(overall_words_seen, overall_elapsed_seconds)
                overall_eta_seconds = _safe_eta(
                    overall_totals["total_words"] - overall_words_seen,
                    overall_word_rate,
                )
                _emit(
                    progress_callback,
                    "demo_pdf_extracting",
                    section="demo_pdf_feed",
                    completed=words_seen,
                    total=totals["total_words"] or None,
                    status="extracting",
                    message=(
                        f"{pdf.name}: page={page} pages={pages_seen}/{total_pages} "
                        f"words={words_seen}/{totals['total_words']} (+{delta_words}) "
                        f"chars={chars_seen}/{totals['total_chars']} "
                        f"overall_words={overall_words_seen}/{overall_totals['total_words']} "
                        f"eta~{round(overall_eta_seconds, 1) if overall_eta_seconds is not None else '?'}s"
                    ),
                    pdf=str(pdf),
                    page=page,
                    pages_seen=pages_seen,
                    total_pages=total_pages,
                    words_seen=words_seen,
                    delta_words=delta_words,
                    total_words=totals["total_words"],
                    char_count=chars_seen,
                    total_chars=totals["total_chars"],
                    elapsed_seconds=elapsed_seconds,
                    words_per_second=round(word_rate, 3) if word_rate is not None else None,
                    eta_seconds=round(eta_seconds, 3) if eta_seconds is not None else None,
                    overall_words_seen=overall_words_seen,
                    overall_total_words=overall_totals["total_words"],
                    overall_chars_seen=overall_chars_seen,
                    overall_total_chars=overall_totals["total_chars"],
                    overall_elapsed_seconds=overall_elapsed_seconds,
                    overall_words_per_second=round(overall_word_rate, 3) if overall_word_rate is not None else None,
                    overall_eta_seconds=round(overall_eta_seconds, 3) if overall_eta_seconds is not None else None,
                )
                last_emitted_words_seen = words_seen
            continue
        if stage == "build":
            document = payload.get("document")
        elif stage == "persist":
            document = payload.get("document") or document
            stored_id = payload.get("stored_doc_id")
        elif stage == "save":
            document = payload.get("document") or document
            stored_id = payload.get("stored_doc_id", stored_id)
        _emit(
            progress_callback,
            "demo_pdf_stage",
            section="demo_pdf_feed",
            status=stage,
            message=f"{pdf.name}: stage={stage}",
            pdf=str(pdf),
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
    if document is None:
        raise RuntimeError(f"PDF ingest yielded no document for {pdf}")
    ingest_elapsed = round(time.monotonic() - started, 3)

    feed_started = time.monotonic()
    _emit(
        progress_callback,
        "demo_pdf_feed_started",
        section="demo_pdf_feed",
        status="feed",
        message=f"{pdf.name}: structural feed started",
        pdf=str(pdf),
        body_chars=len(document.body),
        sentence_count=len(document.sentences),
        provision_count=len(document.provisions),
    )
    feed_progress_started = time.monotonic()

    def feed_progress_callback(stage: str, details: dict[str, Any]) -> None:
        if stage != "structural_feed_progress":
            return
        feed_elapsed_seconds = round(time.monotonic() - feed_progress_started, 3)
        work_fraction_complete = details.get("work_fraction_complete")
        stage_fraction_complete = details.get("stage_fraction_complete")
        eta_seconds = details.get("eta_seconds")
        work_unit = details.get("work_unit")
        work_completed = details.get("work_completed")
        work_total = details.get("work_total")
        has_work_progress = (
            work_unit is not None
            and work_completed is not None
            and work_total is not None
        )
        sentence_progress = ""
        if details.get("total_sentences") is not None:
            sentence_progress = (
                f" sentences={details.get('sentences_done')}/{details.get('total_sentences')}"
            )
        word_progress = ""
        if details.get("total_words") is not None and work_unit != "words":
            word_progress = f" words={details.get('words_done')}/{details.get('total_words')}"
        work_progress = ""
        if has_work_progress:
            work_progress = (
                f" {work_unit}={work_completed}/{work_total}"
            )
        progress_text = ""
        if work_fraction_complete is not None:
            progress_text = f" progress={round(float(work_fraction_complete) * 100, 1)}%"
        elif stage_fraction_complete is not None:
            progress_text = f" stage_progress={round(float(stage_fraction_complete) * 100, 1)}%"
        step_text = ""
        if not has_work_progress and details.get("completed_steps") is not None and details.get("total_steps") is not None:
            step_text = f" step={details.get('completed_steps')}/{details.get('total_steps')}"
        _emit(
            progress_callback,
            "demo_pdf_feed_progress",
            section="demo_pdf_feed",
            status="feed",
            message=(
                f"{pdf.name}: feed stage={details.get('stage')} "
                f"{step_text}{sentence_progress}{word_progress}{work_progress} "
                f"predicates={details.get('predicate_atom_count') or 0} "
                f"signals={details.get('signal_atom_count') or 0} "
                f"{progress_text} "
                f"eta~{round(float(eta_seconds), 1) if eta_seconds is not None else '?'}s"
            ),
            pdf=str(pdf),
            feed_stage=details.get("stage"),
            completed_steps=details.get("completed_steps"),
            total_steps=details.get("total_steps"),
            stage_fraction_complete=stage_fraction_complete,
            work_fraction_complete=work_fraction_complete,
            sentences_done=details.get("sentences_done"),
            total_sentences=details.get("total_sentences"),
            words_done=details.get("words_done"),
            total_words=details.get("total_words"),
            batch_index=details.get("batch_index"),
            total_batches=details.get("total_batches"),
            work_unit=details.get("work_unit"),
            work_completed=details.get("work_completed"),
            work_total=details.get("work_total"),
            predicate_atom_count=details.get("predicate_atom_count"),
            legal_signal_count=details.get("legal_signal_count"),
            operational_signal_count=details.get("operational_signal_count"),
            signal_atom_count=details.get("signal_atom_count"),
            provenance_ref_count=details.get("provenance_ref_count"),
            relation_count=details.get("relation_count"),
            atom_count=details.get("atom_count"),
            body_chars=details.get("body_chars"),
            feed_elapsed_seconds=feed_elapsed_seconds,
            eta_seconds=eta_seconds,
        )

    feed = collect_canonical_structural_ir_feed(
        document.body,
        progress_callback=feed_progress_callback,
    )
    feed_elapsed = round(time.monotonic() - feed_started, 3)
    _emit(
        progress_callback,
        "demo_pdf_feed_finished",
        section="demo_pdf_feed",
        status="ok",
        message=f"{pdf.name}: structural feed finished in {feed_elapsed}s",
        pdf=str(pdf),
        feed_elapsed_seconds=feed_elapsed,
        predicate_atom_count=len(feed.get("predicate_atoms", ())),
        signal_atom_count=len(feed.get("signal_atoms", ())),
        provenance_ref_count=len(feed.get("provenance_refs", ())),
    )

    return {
        "pdf": str(pdf),
        "output_json": str(output_json),
        "stored_id": stored_id,
        "title": document.metadata.title,
        "citation": document.metadata.citation,
        "body_chars": len(document.body),
        "sentence_count": len(document.sentences),
        "provision_count": len(document.provisions),
        "ingest_elapsed_seconds": ingest_elapsed,
        "feed_elapsed_seconds": feed_elapsed,
        "predicate_atom_count": len(feed.get("predicate_atoms", ())),
        "signal_atom_count": len(feed.get("signal_atoms", ())),
        "provenance_ref_count": len(feed.get("provenance_refs", ())),
        "constraint_receipt": dict(feed.get("constraint_receipt", {})),
        "predicate_atom_sample": list(feed.get("predicate_atoms", ()))[:3],
        "signal_atom_sample": list(feed.get("signal_atoms", ()))[:3],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded SensibLaw structural feed against demo PDFs with progress reporting."
    )
    parser.add_argument(
        "pdfs",
        nargs="*",
        type=Path,
        help="PDF paths to evaluate. Defaults to a bounded demo set.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report output path. Defaults to stdout only.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Emit progress to stderr.",
    )
    parser.add_argument(
        "--progress-format",
        choices=("human", "json", "bar"),
        default="human",
        help="Progress renderer for stderr output.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (default: %(default)s).",
    )
    parser.add_argument(
        "--progress-interval-seconds",
        type=float,
        default=1.0,
        help="Minimum time between progress emissions during preflight/extraction.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_cli_logging(str(args.log_level))
    base_progress_callback = build_progress_callback(
        enabled=bool(args.progress),
        fmt=str(args.progress_format),
    )
    partial_output = None
    if args.output:
        partial_output = args.output.with_name(args.output.name + ".partial.json")
    run_state: dict[str, Any] = {
        "status": "starting",
        "report": [],
        "last_event": None,
        "last_updated_epoch_seconds": None,
    }

    def persist_state() -> None:
        if partial_output is None:
            return
        _atomic_write_json(partial_output, run_state)

    def progress_callback(stage: str, details: dict[str, Any]) -> None:
        run_state["last_event"] = {
            "stage": stage,
            "details": details,
        }
        run_state["last_updated_epoch_seconds"] = round(time.time(), 3)
        persist_state()
        if base_progress_callback is not None:
            base_progress_callback(stage, details)

    def _handle_termination(signum, _frame) -> None:
        run_state["status"] = "interrupted"
        run_state["termination_signal"] = signum
        persist_state()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _handle_termination)
    signal.signal(signal.SIGINT, _handle_termination)

    pdfs = tuple(args.pdfs) if args.pdfs else DEFAULT_PDFS
    missing = [str(path) for path in pdfs if not path.exists()]
    if missing:
        raise SystemExit(f"Missing demo PDFs: {', '.join(missing)}")

    report: list[dict[str, Any]] = []
    total = len(pdfs)
    _emit(
        progress_callback,
        "demo_feed_started",
        section="demo_pdf_feed",
        completed=0,
        total=total,
        status="starting",
        message="Starting bounded demo PDF structural-feed evaluation.",
    )
    run_state["status"] = "preflighting"
    run_state["pdfs"] = [str(pdf) for pdf in pdfs]
    batch_started_at = time.monotonic()
    try:
        totals_by_pdf, overall_totals = _preflight_all_pdfs(
            pdfs,
            progress_callback,
            progress_interval_seconds=float(args.progress_interval_seconds),
        )
        run_state["overall_totals"] = overall_totals
        persist_state()
        _emit(
            progress_callback,
            "demo_feed_preflight_finished",
            section="demo_pdf_feed",
            completed=overall_totals["total_words"],
            total=overall_totals["total_words"],
            status="ok",
            message=(
                f"Preflight complete: docs={total} pages={overall_totals['total_pages']} "
                f"words={overall_totals['total_words']} chars={overall_totals['total_chars']}"
            ),
            overall_total_pages=overall_totals["total_pages"],
            overall_total_words=overall_totals["total_words"],
            overall_total_chars=overall_totals["total_chars"],
        )

        with tempfile.TemporaryDirectory(prefix="itir_demo_pdf_feed_") as tmp_dir:
            tmp_root = Path(tmp_dir)
            completed_words = 0
            completed_chars = 0
            run_state["status"] = "running"
            for index, pdf in enumerate(pdfs, start=1):
                _emit(
                    progress_callback,
                    "demo_pdf_started",
                    section="demo_pdf_feed",
                    completed=index - 1,
                    total=total,
                    status="running",
                    message=f"Processing {pdf.name}",
                    pdf=str(pdf),
                )
                output_json = tmp_root / f"{index:02d}_{pdf.stem}.json"
                entry = _build_entry(
                    pdf,
                    output_json,
                    progress_callback,
                    totals=totals_by_pdf[pdf],
                    overall_totals=overall_totals,
                    completed_words_before=completed_words,
                    completed_chars_before=completed_chars,
                    batch_started_at=batch_started_at,
                    progress_interval_seconds=float(args.progress_interval_seconds),
                )
                report.append(entry)
                run_state["report"] = report
                persist_state()
                completed_words += totals_by_pdf[pdf]["total_words"]
                completed_chars += totals_by_pdf[pdf]["total_chars"]
                _emit(
                    progress_callback,
                    "demo_pdf_finished",
                    section="demo_pdf_feed",
                    completed=index,
                    total=total,
                    status="ok",
                    message=(
                        f"{pdf.name}: predicates={entry['predicate_atom_count']} "
                        f"signals={entry['signal_atom_count']}"
                    ),
                    pdf=str(pdf),
                    overall_words_seen=completed_words,
                    overall_total_words=overall_totals["total_words"],
                    overall_chars_seen=completed_chars,
                    overall_total_chars=overall_totals["total_chars"],
                    predicate_atom_count=entry["predicate_atom_count"],
                    signal_atom_count=entry["signal_atom_count"],
                    provenance_ref_count=entry["provenance_ref_count"],
                )

        rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        run_state["status"] = "complete"
        run_state["report"] = report
        persist_state()
        _emit(
            progress_callback,
            "demo_feed_finished",
            section="demo_pdf_feed",
            completed=total,
            total=total,
            status="complete",
            message="Demo PDF structural-feed evaluation complete.",
        )
        return 0
    except KeyboardInterrupt:
        run_state["status"] = "interrupted"
        persist_state()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
