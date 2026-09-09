# OALC PG env precedence test matrix

The SLR PostgreSQL persistence adapter should implement this configuration
precedence without treating configuration as semantic state.

| Case | Process `DATABASE_URL` | Explicit env file | Local `.env` | Expected result |
|---|---|---|---|---|
| 1 | set | present | present | process value wins |
| 2 | unset | present with value | present | explicit env-file value |
| 3 | unset | absent/not selected | present with value | local `.env` value |
| 4 | unset | selected but missing | any | explicit configuration residual |
| 5 | unset | present but no `DATABASE_URL` | absent | configuration residual |
| 6 | unset | none | none | configuration residual |

Requirements:

- Env-file loading must not overwrite an existing process `DATABASE_URL`.
- `DATABASE_URL` values must not be logged in full.
- Test fixtures should use synthetic URLs only.
- Database configuration failure remains operational state and never becomes
  source absence, negative legal evidence, or semantic closure.
