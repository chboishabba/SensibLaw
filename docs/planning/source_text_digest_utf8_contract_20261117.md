# Source-text digest convergence — SLR / SensibLaw

**Canonical rule:** SHA-256 over the exact UTF-8 bytes of the *decoded source text*.

    source_sha256(text) = SHA256(UTF8(text))

A JSON (or MCP) envelope is a transport only. Decode it first; do not hash
JSON string quotation, backslash escaping, whitespace, key ordering, or
serialized framing. Equivalent JSON transport encodings must yield identical
source-content identities. This matches the existing SLR source digest and
`src/policy/numeric_pnf_compilation.py::canonical_text_sha256`.

## Code in this working PR

`src/policy/entity_resolution.py` now uses `_source_text_sha256` for
P0b `canonical_text_sha256` and the dependent mention-expansion,
alias-expansion and grammar-expansion carrier coordinates. It does **not**
change `_canonical_digest` for *structured carrier identities*; those are
different commitments with independent framing/serialization contracts.
Do not infer that hashing a JSON-serialized object defines a source digest.

The mention-expansion interface rejects a carrier whose source digest
does not match the raw UTF-8 text and names legacy JSON-string digests
explicitly. It does not silently rewrite immutable carrier IDs or
semantic receipts.

## Uploaded GWB historical TAR

Wikipedia revision `1385850169` source text (93,577 Unicode code points):

- Canonical raw source: `a88ef63b9c109f0f09c2fc2a266373a9ecaae855104cb0e11c4e6c53d90d3233`.
- Archived 16,034 P0b licence carrier's **legacy JSON-string digest**:
  `c1ae7a8b93b70050f27b64524211d624e3053b1b59f28491ca3db45320c985a1`.
- The uploaded TAR's older P0b record is internally consistent **as
  historical evidence only**. Its `canonical_text_sha256` does not
  satisfy the new direct source hash rule, despite decoding to the same
  text. Do not turn it into a new carrier by changing the hash in place:
  `carrier_ref` and downstream references also depend on the old identity.

For a current carrier, reissue P0b from the **exact same source/revision
and original token evidence**, using the canonical SensibLaw runtime or the
Rust-backed pipeline, then recompute dependent carrier references and
reverify original source coordinates. Do not require re-parsing the text
merely to rehash it.

The archived regression auditor in JMD PR #111 now explicitly reports
`p0b_legacy_hash_reissue_required=true` and
`p0b_matches_current_utf8_source_hash=false`, rather than accepting
JSON-string digest as the canonical content hash.

## Tests and acceptance

- Source with quotes, newline, and non-ASCII text: P0b SHA must equal
  direct SHA-256(UTF-8 text) and be invariant under alternate JSON escapes.
- P0b mention expansion must reject a legacy JSON-string source digest,
  even if it was consistent with a historical carrier.
- Existing deterministic P0b and expansion tests must continue to pass.
- The source hashing rule applies to every content-based identity;
  structured receipt/content-addressed **object** hashes must separately
  disclose their exact stable encoding if retained.

The original TAR's legacy P0b contract was inspected directly and its raw
and JSON-string digests independently reproduced. The newly committed
SensibLaw test functions still require full execution under the project's
pinned test environment. This is a source-identity fix, not an event/person
semantic-licence or world-truth proof.
