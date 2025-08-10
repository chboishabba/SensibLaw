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
