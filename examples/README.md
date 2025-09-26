# Examples

## Distinguish GLJ Demo

This demo compares a short story to a simplified silhouette of the GLJ case
using the `compare_story_to_case` helper.

### Running the demo

From the repository root execute:

```bash
python examples/distinguish_glj/demo.py
```

The script loads `glj_silhouette.json` and `story.json`, compares them and
prints overlaps and differences with paragraph citations.

### Visualising results

The textual output can be further processed or visualised. For example, proof
structures can be exported to Graphviz DOT format and rendered:

```bash
dot -Tpng examples/distinguish_glj/proof_tree.dot -o proof_tree.png
```

## Legislation Showcase Pack

The `examples/legislation` folder bundles cleaned JSON excerpts from select
Queensland statutes together with a light-weight CLI for stakeholder demos.

### Contents

- `penalties_and_sentences_part_2.json` & `*.metadata.json`: sentencing
  principles distilled from Part 2 of the *Penalties and Sentences Act 1992*.
- `criminal_code_qld_s302.json` & `*.metadata.json`: a murder elements checklist
  derived from s 302 of the *Criminal Code (Qld)*.
- `query_cli.py`: helper script that answers showcase questions using the
  cleaned datasets.

### Running the showcase queries

1. List the available datasets:

   ```bash
   python examples/legislation/query_cli.py --list
   ```

2. Reproduce the governing principles briefing for sentencing:

   ```bash
   python examples/legislation/query_cli.py \
     --dataset penalties_and_sentences_part_2 \
     --query "List governing principles"
   ```

3. Generate the murder checklist and defence reminders:

   ```bash
   python examples/legislation/query_cli.py \
     --dataset criminal_code_qld_s302 \
     --query "Checklist for murder"
   ```

4. For a one-command demo (used in stakeholder walk-throughs) run:

   ```bash
   python examples/legislation/query_cli.py --demo
   ```

The CLI surfaces metadata such as source URLs and cleaning notes so reviewers
can trace each summary back to the underlying legislation. The JSON files are
structured for easy extension if additional Acts or sections need to be added to
the pack.
