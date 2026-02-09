# Lexeme Normalizer: Character-Class Layer (lexeme_normalizer_v1)

This documents the *existing* character-class separation used by the SL lexeme
layer. The purpose is to keep downstream reducers (TiRCorder/SB/ITIR overlays)
from re-implementing or guessing what "word vs number vs symbol" means.

## Where This Lives

- Normalization + classification (authoritative): `SensibLaw/src/text/lexeme_normalizer.py`
- Span token splitting for lexeme occurrences: `SensibLaw/src/text/lexeme_index.py`

## What We Classify Today

Normalization produces:

- `norm_text`: canonicalized text for lexeme dictionary identity
- `norm_kind`: coarse class label
- `flags`: bitfield of surface-case + content/anomaly indicators

### `norm_kind` (coarse class)

`normalize_lexeme(surface)` assigns exactly one of:

- `word`: contains at least one Unicode letter (after NFKC); casefolded for `norm_text`
- `number`: all non-space chars are Unicode decimal digits (`Nd`), or contains digits but no letters; case preserved for `norm_text` only via NFKC
- `punct`: all non-space chars are in Unicode punctuation categories (`Pc/Pd/Pe/Pf/Pi/Po/Ps`); `norm_text` preserves punctuation
- `symbol`: all non-space chars are in Unicode symbol categories (`Sc/Sk/Sm/So`); `norm_text` preserves symbols
- `ws`: whitespace-only; normalized to a single space `" "`
- `other`: everything else (e.g., control-ish, mixed categories without letters/digits dominance, etc.); casefolded for `norm_text`

Notes:

- Classification is *lexeme-level*, not per-character: a single token can be
  "word" while still being flagged as having digits/punct/symbols.
- Mixed tokens prefer `word` when any letter is present. Example: `"H2O"` is
  `norm_kind="word"` with `HAS_DIGIT` also set.

### `flags` (content + anomaly bits)

`LexemeFlags` includes:

- Surface case (letters only): `SURF_ALL_UPPER`, `SURF_ALL_LOWER`, `SURF_TITLE`,
  `SURF_MIXED_CASE`
- Content presence: `HAS_NON_ASCII`, `HAS_LETTER`, `HAS_DIGIT`, `HAS_PUNCT`,
  `HAS_SYMBOL`
- Input anomalies: `HAS_REPLACEMENT_CHAR` (U+FFFD), `HAS_ZERO_WIDTH` (e.g.
  U+200B/U+200C/U+200D/U+FEFF)

`HAS_PUNCT` / `HAS_SYMBOL` are currently set when the token is *entirely* punct
or *entirely* symbol (because those are the branches that return `punct` /
`symbol`). For mixed tokens, you should rely on `norm_kind` + `HAS_LETTER` /
`HAS_DIGIT` primarily.

## Token Splitting (What Becomes a "Lexeme Occurrence")

`SensibLaw/src/text/lexeme_index.py` uses:

- `_TOKEN_PATTERN = re.compile(r"\\w+|[^\\w\\s]", re.UNICODE)`

That means:

- Word-ish runs: `\\w+` (Unicode "word characters": letters/digits/underscore)
- Any single non-word, non-space character becomes its own token (punct/symbol)
- Whitespace is skipped (no lexeme occurrence is emitted for whitespace)

This is intentionally simple and deterministic.

## What We Do *Not* Have Yet

- A distinct "per-character class stream" (e.g., emitting an `LDDS` shape or
  a run-length encoding of character classes). If we want that later, it should
  be added as an *optional* derived attribute (not required for identity).
- A richer `norm_kind` taxonomy (e.g., `alnum`, `email`, `url`, `citation`).
  Those are interpretive/profile-bound and should not become canonical without
  a separate contract.

