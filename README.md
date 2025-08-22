# SensibLaw

[![CI](https://github.com/SensibLaw/SensibLaw/actions/workflows/ci.yml/badge.svg)](https://github.com/SensibLaw/SensibLaw/actions/workflows/ci.yml)

Like coleslaw, it just makes sense.

## Installation

Install the package in editable mode to develop locally:

```bash
pip install -e .
```

## Development

Create and activate a virtual environment, then install the development
dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Run the test suite and pre-commit hooks:

```bash
pytest
pre-commit run --all-files
```

Test fixtures are located in `tests/fixtures`, and reusable templates live in
`tests/templates`.


## CLI Commands

Graph rendering relies on the Graphviz toolchain. Install the system
package separately, for example:

```bash
sudo apt-get install graphviz  # Debian/Ubuntu
# or
brew install graphviz          # macOS
```

## CLI

### CLI Commands

#### Retrieve document revisions

Retrieve a document revision as it existed on a given date:

```bash
sensiblaw get --id 1 --as-at 2023-01-01
```

Fetch how later authorities have treated a given case:

```bash
sensiblaw query treatment --case case123
```

See [docs/versioning.md](docs/versioning.md) for details on the versioned
storage layer and available provenance metadata.

## Data ingestion

Download legislation from the Federal Register of Legislation and build a
subgraph for use in proof-tree demos:

```bash
sensiblaw extract frl --act NTA1993 --out data/frl/nta1993.json
```

The command writes a JSON representation of the Native Title Act 1993 to
`data/frl/nta1993.json`.

```bash
python -m src.cli graph subgraph --graph-file data/frl/nta1993.json --seeds Provision#NTA:s223 --hops 1 --dot
```

This prints a DOT description of the one-hop neighbourhood around
`Provision#NTA:s223`. The JSON graph and DOT output feed into proof-tree demos
that visualise how provisions connect.

### Examples

Distinguish two cases and highlight overlapping reasoning:

```bash
sensiblaw distinguish --base base.json --candidate cand.json
```

The command outputs JSON with shared paragraphs under `"overlaps"` and
unmatched paragraphs under `"missing"`.

Run declarative tests against a story:

```bash
sensiblaw tests run --ids glj:permanent_stay --story story.json
```

The result includes the test name, evaluated factors, and whether the test
`"passed"`.

Extract a portion of the legal knowledge graph:

```bash
sensiblaw graph subgraph --seed case123 --hops 2
```

This returns a JSON object with arrays of `"nodes"` and `"edges"` representing
the subgraph around the seed node.

### Distinguish cases

Compare a candidate story against the reported case `[2002] HCA 14`:

```bash
sensiblaw distinguish --case '[2002] HCA 14' --story tests/fixtures/glj_permanent_stay_story.json
```

The command returns JSON with:

* `overlaps` – factors or holdings present in both cases, each with `base` and `candidate` paragraph references.
* `missing` – factors from the cited case absent in the story.
* Paragraph references identify supporting passages via indices and text.

A sample story and silhouette are provided at [tests/fixtures/glj_permanent_stay_story.json](tests/fixtures/glj_permanent_stay_story.json) and [examples/distinguish_glj/glj_silhouette.json](examples/distinguish_glj/glj_silhouette.json).
The comparison is driven by factor packs such as [tests/templates/glj_permanent_stay.json](tests/templates/glj_permanent_stay.json), which encodes the GLJ permanent-stay cues.

#### Query case treatment

Summarise how later decisions treat a case:

```bash
sensiblaw query treatment --case '[1992] HCA 23'
```

Sample output ordered by weighting of the citing court:

```
FOLLOWS       5
APPLIES       3
CONSIDERS     2
DISTINGUISHES 1
OVERRULES     0
```

Each count represents the weighted sum of citing judgments, with higher courts
contributing more than lower courts. The summary aggregates these weights to
convey the overall reception of the case.
