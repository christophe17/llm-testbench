-- Schéma de l'ingestion (ADR 007). Idempotent : rejoué à chaque démarrage.
--
-- documents et chunks sont partagés par tous les index d'une même source ; les vecteurs
-- vivent dans une table par index (emb_<clé>, créée par le code avec sa dimension), et
-- la table indexes est le registre qui relie chaque index au chunker et au modèle qui
-- l'ont produit — le début du lineage de la phase 3.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    source_key  text        NOT NULL,
    doc_id      text        NOT NULL,
    title       text        NOT NULL DEFAULT '',
    uri         text,
    checksum    text        NOT NULL,
    char_count  integer     NOT NULL,
    metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_key, doc_id)
);

CREATE TABLE IF NOT EXISTS chunks (
    source_key     text    NOT NULL,
    chunk_id       text    NOT NULL,
    doc_id         text    NOT NULL,
    ordinal        integer NOT NULL,
    section_title  text    NOT NULL DEFAULT '',
    section_order  integer NOT NULL,
    start_char     integer NOT NULL,
    end_char       integer NOT NULL,
    text           text    NOT NULL,
    checksum       text    NOT NULL,
    token_estimate integer NOT NULL,
    PRIMARY KEY (source_key, chunk_id),
    FOREIGN KEY (source_key, doc_id) REFERENCES documents (source_key, doc_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS chunks_by_document ON chunks (source_key, doc_id, ordinal);

CREATE TABLE IF NOT EXISTS indexes (
    index_key       text        PRIMARY KEY,
    source_key      text        NOT NULL,
    embedding_model text        NOT NULL,
    dimensions      integer     NOT NULL,
    chunker         jsonb       NOT NULL,
    description     text        NOT NULL DEFAULT '',
    created_at      timestamptz NOT NULL DEFAULT now()
);
