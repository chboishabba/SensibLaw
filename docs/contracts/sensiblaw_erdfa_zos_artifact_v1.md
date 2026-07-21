# SensibLaw–eRDFa–ZOS artifact contract v1

## Scope

This contract defines how immutable SensibLaw legal artifacts are exported, published, announced, recovered, verified, and admitted for local review.

It does not define legal semantics, professional trust, or promotion policy.

## Canonical exported object

A producer emits canonical JSON bytes representing one immutable object:

```json
{
  "contractVersion": "sensiblaw/legal-semantic-build/v1",
  "kind": "artifact",
  "objectId": "legal-semantic-build:<build-hash>",
  "contentDigest": "sha256:<canonical-json-hash>",
  "producerContract": "sensiblaw/legal-semantic-build/v1",
  "semanticBuildRef": "legal-semantic-build:<build-hash>",
  "sourceRevisionRefs": ["source-revision:..."],
  "memberArtifacts": [
    "legal-ir-projection:...",
    "comparison-ledger:...",
    "legacy-witness-set:...",
    "federation-bundle:..."
  ],
  "locators": [
    "ipfs://...",
    "https://...",
    "file://..."
  ]
}
```

The canonical digest is calculated over the canonical SensibLaw bytes, not over a rendered HTML page or an enclosing archive.

## ZOS identity mapping

Map the export into ZOS canonical sync identity:

```text
kind:
  artifact or receipt

object_id:
  producer-stable SensibLaw object ref

content_digest:
  sha256 digest of canonical payload bytes

producer_contract:
  SensibLaw schema/contract version

producer_locator_set:
  one or more acknowledged replay locators
```

Reconciliation precedence is:

```text
canonical identity tuple
-> digest equality
-> acknowledged locators
-> transport/plugin label only as compatibility fallback
```

## Publication flow

```text
Legal Semantic Build
-> canonical JSON bytes
-> optional eRDFa/CBOR shard set
-> Kant, IPFS, HTTP, or file publication
-> publication receipt
-> locator set added to export metadata
-> ZOS inventory announcement
```

The eRDFa/Kant layer may add:

```text
CID
manifest CID
member-shard CIDs
sink name
published revision
retrieval URL
SHA-256 witness
container/member path
presentation metadata
```

It must preserve the canonical SensibLaw object ID and content digest.

## Recovery flow

```text
peer inventory received
-> missing object detected
-> acknowledged locator selected
-> bounded fetch
-> canonical bytes recovered
-> SHA-256 recomputed
-> object ID and contract checked
-> member availability checked
-> local availability receipt created
```

A fetched object must not enter review surfaces when its digest, contract, or object ID fails verification.

## SensibLaw import state

A valid remote import begins as:

```text
remote_artifact_available = true
content_digest_verified = true
review_state = not_started
promotion_performed = false
trust_imported = false
semantic_merge_performed = false
```

The receiver may independently:

```text
ignore
retain as an archival object
request missing members
admit the object to review
compare against local revisions
create local endorsements, rejections, contests, or supersession proposals
promote selected coordinates under local policy
```

Remote availability never commands local promotion.

## Independently syncable object classes

```text
LegalSemanticBuild
LegalIRProjection
LegalGraphRevision
FederationBundle
ReviewAttestationBundle
PublicationReceipt
VerificationReceipt
```

Each object class must have its own object ID, canonical digest, producer contract, and locator set.

## eRDFa boundary

eRDFa and CBOR shards are publication and presentation forms.

The following are prohibited:

```text
eRDFa Tree edge -> Legal IR edge
eRDFa Group role -> PNF semantic role
rendered page content -> canonical legal semantic payload
CID existence -> semantic validity
```

Any legal relation displayed by eRDFa must reference the originating SensibLaw graph revision or Legal IR observation.

## Receipt classes

### Publication receipt

Records that an immutable object was written to a sink and received a locator or CID.

### Recovery receipt

Records locator selection, fetch outcome, byte count, and recovered digest.

### Verification receipt

Records contract support, object-ID parity, digest parity, and member availability.

### Review attestation

Remains a SensibLaw governance object. ZOS may carry its immutable bytes but must not interpret it as trust policy.

## Failure states

```text
unsupported_contract
object_id_mismatch
digest_mismatch
locator_unavailable
member_artifact_missing
container_member_mismatch
malformed_canonical_payload
verified_but_unreviewed
```

Failure receipts are immutable and must not be rewritten into successful receipts.

## End-to-end acceptance test

```text
node A exports a Legal Semantic Build
-> A publishes it and records a receipt
-> ZOS peer A announces canonical inventory identity
-> ZOS peer B detects the missing object
-> B fetches from file, HTTP, or IPFS
-> B verifies SHA-256 and object identity
-> B records local availability
-> B exposes the build as unreviewed
-> no PNF, Legal IR, identity, trust, or legal promotion occurs
```

Repeat with a federation bundle, a review-attestation bundle, and a superseding graph revision.

## Non-collapse laws

```text
CID != semantic validity
digest parity != legal correctness
ZOS availability != SensibLaw admission
remote trust projection != local trust policy
eRDFa arrow != PNF or Legal IR relation
publication receipt != lawyer endorsement
remote graph revision != local promoted graph
```
