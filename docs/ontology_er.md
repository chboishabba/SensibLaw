erDiagram

    %% =========================
    %% Core ontology / substrate
    %% =========================

    Actor ||--o{ Account : "owns / related via"
    Actor ||--o{ Event : "participates in"

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
    %% Entity definitions
    %% =========================

    Actor {
        int     id
        string  kind          "person/org/etc"
        string  label
    }

    Event {
        int     id
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
