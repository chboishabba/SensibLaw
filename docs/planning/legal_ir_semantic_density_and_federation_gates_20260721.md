# Legal IR semantic density and federation gates

## Current measured baseline

The full parser-model legal-PNF probe produced:

```text
236 PNF factors
0 Legal IR observations
6 legacy witnesses
9 comparison rows
4 PNF coverage demands
0 Wikidata lookup demands
0 identity closure
```

Present in generic PNF:

```text
actor
conduct
object
```

Missing generic compositions:

```text
modality
condition
exception
temporal validity
```

The comparison ledger is the development scoreboard. The probe must be rerun after each composition tranche using the same fixture and parser model.

## Gate 1: modality

Target forms include:

```text
must P
must not P
may P
is required to P
has power to P
is entitled to P
```

Required PNF output:

```text
modal operator
scope proposition or event
bearer candidate
polarity
source span refs
sense and scope residuals
```

Required composition:

```text
obligation + negative polarity
-> prohibition candidate
```

This must be generic PNF composition, not a legal parser or keyword-to-Legal-IR shortcut.

Acceptance:

- a normative relation factor exists;
- its scope points to the underlying event/proposition;
- actor/bearer remains explicitly linked;
- ambiguity between normative and non-normative `may` remains a branch or residual;
- Legal IR projects the factor without adding semantics.

## Gate 2: condition attachment

Target forms include:

```text
if C, N
where C, N
provided that C, N
when C, N
```

Required PNF output:

```text
condition proposition
host norm/event/state
attachment relation
scope evidence
source spans
attachment residuals
```

Acceptance:

- the condition is not flattened into the host predicate;
- ambiguous attachment remains explicit;
- Legal IR receives the PNF condition relation only after reconstruction.

## Gate 3: exception attachment

Target forms include:

```text
unless E
except where E
does not apply if E
without lawful excuse
```

Required PNF output:

```text
exception proposition
base relation
exception attachment candidate
source spans
burden unresolved unless independently supported
```

Acceptance:

- exception and activation condition remain distinct;
- exception attachment is traceable to parser observations;
- burden is not inferred from syntax alone;
- legacy-only exception gaps disappear from the comparison ledger.

## Gate 4: temporal validity and transitions

Target forms include:

```text
commences
is repealed
is amended
takes effect
ceases to have effect
```

Required PNF output:

```text
legal object
prior state
new state
effective time
instrument or authority candidate
source spans
temporal residuals
```

Acceptance:

- transitions are versioned and do not overwrite prior legal objects;
- effective dates remain separate from document publication dates;
- Legal IR can project commencement, amendment, and repeal chains.

## Probe convergence target

After Gates 1–4:

```text
modality: PNF reconstructed and Legal IR projected
condition: PNF reconstructed and Legal IR projected
exception: PNF reconstructed and Legal IR projected
temporal validity: PNF reconstructed and Legal IR projected
```

The target is not zero residuals. Jurisdiction, legal time, authority identity, exception burden, and applicability may remain unresolved.

## Gate 5: SensibLaw artifact export/import

Export must provide:

```text
canonical JSON bytes
SHA-256 digest
stable object ID
producer contract
member artifact refs
acknowledged locator set
```

Import must verify:

```text
supported contract
object ID parity
digest parity
member availability or explicit missing-member state
```

Accepted imports start as verified but unreviewed. Import never performs semantic merge or promotion.

## Gate 6: eRDFa/Kant publication

Required proof:

```text
Legal Semantic Build
-> eRDFa/CBOR shard manifest
-> CID and SHA-256 witness
-> publication receipt
-> read-back verification
```

The first product view should expose:

```text
source text and spans
PNF factors
Legal IR observations
legacy comparison
coverage gaps
review attestations
trust projections
revision history
```

Every displayed legal relation must point back to the originating SensibLaw graph revision or Legal IR observation.

## Gate 7: ZOS convergence

Required two-peer proof:

```text
node A publishes one Legal Semantic Build
-> peer A announces inventory
-> peer B detects missing artifact
-> B fetches from an acknowledged locator
-> B verifies SHA-256
-> B records availability
-> SensibLaw exposes the build as unreviewed
-> no promotion occurs
```

Use dynamic or isolated ports so the harness does not depend on fixed workspace ports.

## Gate 8: federated review replication

Repeat Gate 7 for:

```text
FederationBundle
ReviewAttestationBundle
superseding LegalGraphRevision
```

Acceptance:

- endorsements and rejections coexist;
- superseded attestations remain historical but inactive;
- institution-scoped trust projections are recomputed locally;
- remote trust projections do not command local promotion;
- disagreement remains first-class.

## Wikidata position

Wikidata is called only when an unresolved entity identity materially blocks a Legal IR coordinate, such as court, statutory office, party, institution, jurisdiction, or authority.

A proper noun alone is insufficient.

Wikidata candidates remain candidate evidence and never close legal identity, jurisdiction, applicability, violation, or liability.

## Work order

```text
1. modality
2. condition attachment
3. exception attachment
4. temporal validity/transitions
5. rerun legal-PNF probe
6. implement canonical artifact export/import
7. add eRDFa/Kant publication
8. prove ZOS two-peer convergence
9. replicate federation and review bundles
10. build public and institution-scoped Legal IR product views
```

## Prohibited shortcuts

```text
legacy observation -> direct PNF factor
Legal IR keyword matcher -> legal meaning
CID -> semantic validity
ZOS trust score -> SensibLaw promotion
eRDFa edge -> legal relation
remote review majority -> local truth
Wikidata candidate -> legal identity closure
```
