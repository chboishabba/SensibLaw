PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type TEXT NOT NULL,
    text_block_id INTEGER REFERENCES source_text_segments(id) ON DELETE SET NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    sentence_index INTEGER NOT NULL,
    text TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sentences_document_index
    ON sentences(document_id, sentence_index);

CREATE INDEX IF NOT EXISTS idx_sentences_document_id
    ON sentences(document_id);

CREATE TABLE IF NOT EXISTS utterances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    speaker_id INTEGER REFERENCES actors(id) ON DELETE SET NULL,
    start_time REAL,
    end_time REAL,
    channel TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_utterances_document_id
    ON utterances(document_id);

CREATE INDEX IF NOT EXISTS idx_utterances_speaker_id
    ON utterances(speaker_id);

CREATE TABLE IF NOT EXISTS utterance_sentences (
    utterance_id INTEGER NOT NULL REFERENCES utterances(id) ON DELETE CASCADE,
    sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    seq_index INTEGER NOT NULL,
    PRIMARY KEY (utterance_id, sentence_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_utterance_sentences_seq
    ON utterance_sentences(utterance_id, seq_index);

CREATE INDEX IF NOT EXISTS idx_utterance_sentences_sentence
    ON utterance_sentences(sentence_id);

COMMIT;
