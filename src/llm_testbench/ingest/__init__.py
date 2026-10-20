"""Ingestion (ADR 007): parsing → chunking → embeddings → pgvector index.

Each step produces frozen, identifiable and traceable objects: a chunk carries its
document, its section, its position and its fingerprint; an index carries the chunker,
its parameters and the embedding model that produced it.
"""
