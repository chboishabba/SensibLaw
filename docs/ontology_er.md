erDiagram

    %% =========================
    %% Core ontology / substrate
    %% =========================

    Actor ||--o{ Account : "owns / related via"
    Actor ||--o{ Event : "participates in"
    Actor ||--|| ActorPersonDetails : "person details"
    Actor ||--|| ActorOrgDetails : "org details"
    Actor ||--o{ ActorContactPoint : "contact points"
    Address ||--o{ ActorPersonDetails : "postal address"
    Address ||--o{ ActorOrgDetails : "registered address"

    Document ||--o{ Sentence : "contains"
    Sentence ||--o{ UtteranceSentence : "mapped to"
    Utterance ||--o{ UtteranceSentence : "segments"

    %% =========================
    %% Finance core
    %% =========================

    Account ||--o{ Transaction : "has"
    Transaction ||--o{ FinanceProvenance : "explained in"
    Sentence ||--o{ FinanceProvenance : "explains"

    Transaction ||--o{ EventFinanceLink : "linked to"
    Event ||--o{ EventFinanceLink : "uses as evidence/trigger"

    Transaction ||--o{ Transfer : "src/dst"
    Transfer }o--|| Transaction : "src_txn"
    Transfer }o--|| Transaction : "dst_txn"

    Transaction ||--o{ TransactionTag : "tagged with"

    %% =========================
    %% Evidence packs (shared with SensiBlaw)
    %% =========================

    ReceiptPack ||--o{ ReceiptPackItem : "contains"
    ReceiptPackItem }o--|| Transaction : "may include (item_kind='transaction')"
    ReceiptPackItem }o--|| Sentence : "may include (item_kind='sentence')"
    ReceiptPackItem }o--|| Event : "may include (item_kind='event')"
    ReceiptPackItem }o--|| Document : "may include (item_kind='document')"

    %% =========================
    %% Legal systems, sources, and duties
    %% =========================

    LegalSystem ||--o{ LegalSource : "issues"
    NormSourceCategory ||--o{ LegalSource : "classifies"
    LegalSource ||--o{ Provision : "contains"

    LegalSystem ||--o{ WrongType : "scopes"
    NormSourceCategory ||--o{ WrongType : "primary_category"
    WrongType ||--o{ WrongElementRequirement : "defined_by"
    WrongType ||--o{ ActorConstraint : "constrains_actor"

    %% =========================
    %% Protected interests and remedies
    %% =========================

    ValueDimension ||--o{ ProtectedInterestType : "structures"
    CulturalRegister ||--o{ ProtectedInterestType : "inflects"
    ProtectedInterestType ||--o{ HarmInstance : "harmed_in"
    Event ||--o{ HarmInstance : "causes"

    Event ||--o{ EventRemedy : "remedied_by"
    RemedyModality ||--o{ RemedyCatalog : "family"
    RemedyCatalog ||--o{ EventRemedy : "template"
    ValueFrame ||--o{ EventRemedy : "justified_by"

    %% =========================
    %% Entity definitions
    %% =========================

    Actor {
        int     id
        string  kind          "person/org/etc"
        string  label
    }

    Address {
        int     id
        string  address_line1
        string  address_line2
        string  city
        string  state_province
        string  postal_code
        string  country_code
    }

    ActorPersonDetails {
        int     actor_id
        string  given_name
        string  family_name
        date    birthdate
        string  pronouns
        string  gender
        string  ethnicity
        int     address_id
    }

    ActorOrgDetails {
        int     actor_id
        string  legal_name
        string  registration_no
        string  org_type
        int     address_id
    }

    ActorContactPoint {
        int     id
        int     actor_id
        string  kind          "email, phone, uri"
        string  value
        string  label         "home, work, registered"
    }

    Event {
        int     id
        int     wrong_type_id  "links to doctrinal wrong/offence"
        int     legal_system_id "derived from WrongType and enforced via FK"
        string  kind          "life, legal, system"
        string  label
        datetime valid_from
        datetime valid_to
    }

    Document {
        int     id
        string  doc_type      "transcript, reasons, provision, note"
        int     text_block_id
        datetime created_at
    }

    Sentence {
        int     id
        int     document_id
        int     sentence_index
        string  text
    }

    Utterance {
        int     id
        int     document_id
        int     speaker_id
        float   start_time
        float   end_time
        string  channel      "audio, video, chat"
    }

    UtteranceSentence {
        int     utterance_id
        int     sentence_id
        int     seq_index
    }

    Account {
        int     id
        int     owner_actor_id
        string  provider      "CBA, NAB, Wise, etc"
        string  account_type  "cheque,savings,business,credit"
        string  currency
        string  external_id   "masked account id / IBAN"
        string  display_name
        bool    is_primary
        datetime created_at
    }

    Transaction {
        int     id
        int     account_id
        datetime posted_at
        datetime effective_at
        int     amount_cents
        string  currency
        string  counterparty
        string  description
        string  ext_ref
        blob    raw_payload
        string  source_format "csv,ofx,mt940,camt053,json"
        datetime imported_at
    }

    Transfer {
        int     id
        int     src_txn_id
        int     dst_txn_id
        float   inferred_conf
        string  rule          "matching heuristic"
    }

    EventFinanceLink {
        int     id
        int     event_id
        int     transaction_id
        string  link_kind     "caused,evidence,context"
        float   confidence
    }

    FinanceProvenance {
        int     transaction_id
        int     sentence_id
        string  note
    }

    TransactionTag {
        int     transaction_id
        string  tag_code      "RENT,GROCERIES,UNCLASSIFIED_OK"
        string  source        "user,rule,ml_suggestion"
        float   confidence
    }

    ReceiptPack {
        int     id
        string  pack_hash
        datetime created_at
        string  signer_key_id
        blob    signature
    }

    ReceiptPackItem {
        int     pack_id
        string  item_kind     "transaction,sentence,event,document"
        int     item_id
    }

    LegalSystem {
        int     id
        string  code           "AU.COMMON, NZ.TIKANGA, etc"
        string  tradition      "common, tikanga, indigenous, civil"
        string  community      "community or state anchor"
        string  source_form    "statute, case, tikanga_rule"
    }

    NormSourceCategory {
        int     id
        string  code           "STATUTE, CASE, TREATY, CUSTOM"
        string  label
    }

    LegalSource {
        int     id
        int     legal_system_id
        int     norm_source_category_id
        string  citation       "[1992] HCA 23, Crimes Act 1961"
        string  title
    }

    Provision {
        int     id
        int     legal_source_id
        string  ref_path       "section/paragraph path"
        string  heading
    }

    WrongType {
        int     id
        int     legal_system_id
        int     norm_source_category_id
        string  code           "OFFENCE code / doctrinal tag"
        string  label
    }

    WrongElementRequirement {
        int     id
        int     wrong_type_id
        string  element_kind   "duty, breach, causation, defence"
        string  description
        int     issue_id
    }

    ActorConstraint {
        int     id
        int     wrong_type_id
        string  constraint_kind "actor capability / role"
        string  description
    }

    ValueDimension {
        int     id
        string  family         "integrity, status, control"
        string  aspect         "body, reputation, information"
    }

    CulturalRegister {
        int     id
        string  label          "mana, face, izzat"
        string  community
    }

    ProtectedInterestType {
        int     id
        int     value_dimension_id
        int     cultural_register_id
        string  description
    }

    HarmInstance {
        int     id
        int     event_id
        int     protected_interest_type_id
        string  severity       "low, medium, high"
        string  note
    }

    ValueFrame {
        int     id
        string  frame_code     "gender_equality, tikanga_balance"
        string  description
    }

    RemedyModality {
        int     id
        string  modality_code  "MONETARY, STATUS_CHANGE, SYMBOLIC"
        string  description
    }

    RemedyCatalog {
        int     id
        int     remedy_modality_id
        int     legal_system_id
        int     cultural_register_id
        string  remedy_code     "COMPENSATION, INJUNCTION"
        string  terms           "template terms"
        string  note
    }

    EventRemedy {
        int     id
        int     event_id
        int     harm_instance_id
        int     remedy_catalog_id
        int     remedy_modality_id
        int     value_frame_id
        string  terms          "amount/conditions"
        string  note
    }
