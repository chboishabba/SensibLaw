# P5991 -> P14143 climate pilot pack

This is the first pinned live `MigrationPack v0.1` artifact for the bounded
`P5991 -> P14143` review lane.

Materialization path:
- script:
  `SensibLaw/scripts/materialize_wikidata_migration_pack.py`
- manifest:
  `manifest.json`
- bounded slice:
  `slice.json`
- derived migration pack:
  `migration_pack.json`

Selected QIDs:
- `Q56404383` (`Handelsbanken`)
- `Q10651551` (`Swedish Inspectorate of Auditors`)
- `Q10416948` (`Swedish Agency for Government Employers`)
- `Q10403939` (`Akademiska Hus`)
- `Q10422059` (`Atrium Ljungberg`)

Revision basis:
- each entity uses the newest two live revisions available at materialization
  time
- the exact revision pairs are recorded in `manifest.json`

Observed bucket distribution:
- `safe_with_reference_transfer`: 2
- `ambiguous_semantics`: 55

Current interpretation:
- the first live pressure in this lane is temporal/multi-value ambiguity
- the next policy question is whether some of these cases should graduate from
  `ambiguous_semantics` to a more explicit `split_required` bucket
