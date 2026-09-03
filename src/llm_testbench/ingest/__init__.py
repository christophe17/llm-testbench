"""Ingestion (ADR 007) : parsing → chunking → embeddings → index pgvector.

Chaque étape produit des objets figés, identifiables et traçables : un chunk porte son
document, sa section, sa position et son empreinte ; un index porte le chunker, ses
paramètres et le modèle d'embeddings qui l'ont produit.
"""
