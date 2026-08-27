# E0d substantive certification

The E0d promotion gate compares a migration-179 legacy replay with migration 180 by portable semantic identity rather than database-local BIGINT allocation.

Its receipt follows the reusable delta-fed shape:

`source delta -> projection atoms -> affected keys -> local reducer -> authority`

The hard gate covers source pronouns, mention/object supports, demand authority, export/lookup/provenance surfaces, candidates/resolutions, and affected/document interface authority. Multiplicity is preserved in every comparison.

Run `scripts/certify_e0d_anaphor_delta_projection.py` with a legacy 179 database and an E0d 180 database. Supplying replay commands also enables PostgreSQL function accounting for compatibility-adaptor calls, actual E0d semantic-projector calls, wall time, and function self/total time. Timing is evidence only and does not automatically assert a performance win.

Exit code 2 means semantic parity failed. Exit code 3 means the fixture did not contain at least two anaphor occurrences/demands. Zero means the substantive parity gate passed; it does not by itself claim a speedup.
