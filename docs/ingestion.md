# Ingestion Dispatcher

The ingestion dispatcher coordinates fetching of primary legal materials
based on `data/foundation_sources.json`.  Each source entry describes the
jurisdiction, location and available formats.  The dispatcher maps entries to
fetcher functions such as AustLII, PDF extraction or official registers and
applies any throttling rules supplied in the configuration.

## Configuration

`foundation_sources.json` contains an array named `sources`.  Relevant fields
used by the dispatcher include:

- `base_url` – used to determine which fetcher to invoke.
- `formats` – a list of available formats.  `"HTML"` triggers the official
  register fetcher while `"PDF"` invokes the PDF extractor.
- `throttle` – optional settings controlling request rate.  `crawl_delay_sec`
  specifies a delay in seconds before fetching, while `respect_robots` applies a
  default one‑second pause.

## Usage

```python
from pathlib import Path
from src.ingestion.dispatcher import SourceDispatcher

dispatcher = SourceDispatcher(Path("data/foundation_sources.json"))
results = dispatcher.dispatch()
```

`results` is a list containing the source name and the fetchers that were
invoked.  The dispatcher can be limited to specific sources by providing a list
of names:

```python
dispatcher.dispatch(names=["Federal Register of Legislation"])
```

This mechanism allows tests or scripts to run targeted ingestion workflows while
still respecting throttling and format preferences.

## PDF parsing logic (src/pdf_ingest.py)

The PDF pipeline streams pages via pdfminer (`extract_pages`) so only the active
page is materialised in memory. Parsing follows these steps:

- **Table of contents detection and filtering.** `_parse_multi_column_toc()` and
  `_parse_toc_page()` detect TOC pages using “contents” markers, dot leaders, and
  trailing page numbers. Parsed entries become `DocumentTOCEntry` trees and the
  same lookup is used to strip TOC pages before section splitting.
- **Section splitting with parser fallback.** If an optional `section_parser`
  plugin is present, `parse_sections()` defers to it. Otherwise it falls back to
  `_fallback_parse_sections()`, which splits on `Section/Part/Division` headers
  and reattaches any preamble text ahead of the first section.
- **TOC noise removal.** `_strip_leading_table_of_contents()` and
  `_strip_embedded_table_of_contents()` drop inline TOC blocks and headings with
  page references or dot leaders before any splitting occurs.
- **Guarding against false positives.** TOC-like headings (page refs, dot
  leaders, page words) are ignored during regex splitting so the parser does not
  emit empty provisions or misclassify contents pages as sections.

See `docs/nlp_pipelines.md` for the subsequent rule extraction flow once sections
are available.

## PDF ingest persistence (default paths)

`src/pdf_ingest.py` writes JSON artifacts by default:

- Output JSON path: `data/pdfs/<pdf_stem>.json` (relative to repo root)
- SQLite persistence: defaults to `data/corpus/ingest.sqlite`

Notes:
- Pass a custom DB with `--db-path /tmp/my_ingest.sqlite`.
- Pass an empty string `--db-path ''` to skip DB persistence and emit JSON only.

```
# Default (JSON + DB at data/corpus/ingest.sqlite)
python -m src.pdf_ingest path/to.pdf

# Custom DB
python -m src.pdf_ingest path/to.pdf --db-path /tmp/custom.sqlite

# JSON-only (no DB write)
python -m src.pdf_ingest path/to.pdf --db-path ''
```

## Compression statistics at ingest

Ingest now computes lexeme-based compression stats on the canonical body and
stores them in `DocumentMetadata.compression_stats`:

- `token_count`
- `unique_lexemes`
- `rr5_lexeme`
- `mvd_lexeme`
- `compression_ratio`
- `tokenizer_id`

These stats are deterministic, non-semantic, and span-safe.
