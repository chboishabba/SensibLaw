**SensiBlaw Developer Blueprint**

---

### Overview
SensiBlaw is a versioned legal knowledge and reasoning platform designed for embedding legal narratives, citations, decisions, and evidentiary provenance into a structured, explorable system. This document integrates the foundational logic from "SENSIBLAW - Database working.txt" with architectural, feature, and UX intentions from related roadmap and visualization design materials.

---

### 1. **Core Concepts & Entities**

- **NarrativeEvent**: Anchored moment in time in a person or group's story.
  - Fields: `id`, `datetime`, `location`, `participants`, `narrative_text`, `tags`, `linked_documents`, `linked_accounts`, `trustworthiness_score`

- **LegalElement**: Citable concept from law (e.g. tort, duty, standard).
  - Types: `StatuteProvision`, `CasePrinciple`, `LegalTest`, `ChecklistItem`, `Category`, `Definition`
  - Fields: `id`, `name`, `description`, `jurisdiction`, `source_url`, `precedent_case`, `applicable_date_range`, `linked_narratives`

- **ReceiptPack**: Cryptographically signed bundle of a document, its version, timestamp, and any transformation metadata.
  - Fields: `id`, `version`, `created_at`, `doc_type`, `source`, `digest`, `signature`, `provenance_links`

- **Entity**: Person, org, or agent appearing in narratives or documents.
  - Fields: `id`, `name`, `role`, `contacts`, `tags`, `relationships`

- **AccountFlow**: Thread of financial activity from a source account.
  - Fields: `flow_id`, `account_id`, `start_date`, `end_date`, `flow_segments`

- **FlowSegment**: A single income/expense transfer portion.
  - Fields: `segment_id`, `amount`, `timestamp`, `target_account`, `linked_event`, `tags`, `category`

- **TaxonomyTag**: Structured keyword/category mapping narrative to legal/semantic domains.
  - Fields: `id`, `label`, `type`, `related_legal_elements`, `severity_rating`


---

### 2. **Storage & Retrieval Logic**

- **Versioned Storage Layer**:
  - Implemented using content-hash (SHA256) versioning of documents.
  - Support `as-at` queries (e.g. "what was valid on 2023-01-01?").
  - MinSign (Ed25519) for cryptographic integrity of ReceiptPacks.

- **Search & Matching**:
  - SQLite FTS5 for text search across narratives and legal content.
  - pyahocorasick for structured phrase spotting in transcripts.
  - rapidfuzz for fallbacks in fuzzy matching.

- **Timeline & Interval Logic**:
  - Use `intervaltree` for querying events/legal provisions over time.
  - Temporal anchors (valid_from/to, asserted_at, recorded_at) on most entities.


---

### 3. **Ingestion & Integration Pipelines**

- **Narrative Ingest (Voice/Text)**:
  - Input: transcripts (from TiRCorder), annotated docs, user entries.
  - Outputs: normalized NarrativeEvent objects, optionally diarized.

- **Legal Element Harvesting**:
  - Sources: AustLII, FRL API, manually curated taxonomies.
  - Normalized to LegalElement model and tagged with provenance.

- **Finance Adapter Plugins**:
  - Formats supported: CSV, JSON, OFX/QFX, MT940, XML (ISO 20022).
  - Parsed and mapped into AccountFlows + FlowSegments.

- **Codebook/QDA Adapter**:
  - REFI-QDA import/export for coded concepts and tags.


---

### 4. **Visualization Architecture**

- **Core View: Ribbon Timeline + Event Threads**
  - Vertical ribbon = main income stream (width = amount).
  - Colored threads curve out = siphons to other accounts.
  - Layered z-depth to distinguish account types.
  - Event callouts hover along ribbon (e.g., "rent paid").

- **Graph Visualization**:
  - NetworkX + Graphviz for legal citation and reasoning graphs.
  - Cytoscape.js/elk.js frontend for proof trees, definitions, and case structure.

- **Timeline UI Integration**:
  - All events map to a timeline (NarrativeEvent + FlowSegment).
  - Tooltips/clickable cards show transcript excerpts, legal relevance, financial metadata.


---

### 5. **Ethics, Privacy & Consent Enforcement**

- Use of Open Policy Agent (OPA/Rego) to gate data queries and disclosures.
- All transformations logged in ReceiptPack metadata.
- Signed exports include transcript, derived conclusions, citations, and hash proofs.
- Support for redaction layers using pdf-redactor, scrubadub.


---

### 6. **Next Dev Tasks (Q4–Q1)**

| Area | Milestone | Notes |
|------|-----------|-------|
| Timeline | Implement SVG+JS visual ribbon timeline prototype | Based on visualization brief |
| Finance | Adapter scaffolds for OFX, CSV | Normalize to internal flow format |
| NLP | Pyahocorasick + fuzzy tagging | Legal trigger spotting on transcripts |
| QDA | REFI import parser | For thematic codebooks |
| Graphs | Narrative-event to legal-element mapping explorer | Interact with citations & arguments |
| Infra | SQLite schema finalization | + Indexes & versioning support |
| Redaction | Audio + doc redaction pipeline | Deterministic & reproducible |
| Docs | Developer setup README + schema diagrams | Onboarding first contributors |


---

### 7. **Further Work (Stretch Goals)**
- Full 3D interactive ribbon-timeline with D3.js or Three.js.
- Visual querying: filter timeline by legal tags or spending category.
- Natural language queries (e.g. "Show moments of medical-related spending after 2022").
- Consent receipts API + visual signer with QR verification.

---

**SensiBlaw** reflects a modular, narratively anchored, and legally traceable vision for structured legal knowledge. The dev path is now unified across ingestion, analysis, and story visualization.