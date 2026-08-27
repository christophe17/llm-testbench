"""Types communs des jeux d'évaluation de retrieval.

Le contrat central du banc d'essai : quel que soit le jeu public chargé, un loader
produit un :class:`RetrievalDataset` — corpus, requêtes, jugements de pertinence
(qrels) — dont l'intégrité référentielle est validée à la construction. Un loader
qui joint mal ses fichiers échoue ici, bruyamment, pas trois phases plus tard dans
un score de retrieval faussé.

Vocabulaire (celui de la littérature IR, gardé tel quel pour que les scores soient
comparables aux papiers) :

- *corpus* : les documents dans lesquels on cherche ;
- *queries* : les requêtes posées ;
- *qrels* (« query relevance judgments ») : pour chaque requête, les documents
  jugés pertinents et leur niveau de pertinence (entier, 0 = non pertinent).
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

# query_id -> (doc_id -> niveau de pertinence). Les niveaux sont des entiers >= 0 ;
# la plupart des jeux BEIR sont binaires (1), certains sont gradués (NFCorpus : 0-2).
Qrels = dict[str, dict[str, int]]


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    text: str
    title: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class Query(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_id: str
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)


class DatasetInfo(BaseModel):
    """Carte d'identité d'un jeu : de quoi tracer la provenance de chaque chiffre."""

    model_config = ConfigDict(frozen=True)

    key: str
    """Identifiant court utilisé partout dans le banc (ex. ``beir/scifact``)."""

    name: str
    homepage: str
    license: str
    """Licence telle qu'affichée par la source de distribution — voir la vérification
    du 2026-08-26 dans docs/ : pour BEIR, c'est la revendication de l'empaquetage,
    pas une garantie amont."""

    source: str
    """D'où les données sont effectivement chargées (dépôts Hugging Face, URL...)."""


class RetrievalDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    info: DatasetInfo
    split: str
    documents: tuple[Document, ...]
    queries: tuple[Query, ...]
    qrels: Qrels

    sampled: bool = False
    """True si le jeu a été tronqué (mode échantillon). Un jeu échantillonné vérifie
    la mécanique ; il ne produit JAMAIS un chiffre publiable."""

    @model_validator(mode="after")
    def _check_referential_integrity(self) -> "RetrievalDataset":
        doc_ids = {d.doc_id for d in self.documents}
        query_ids = {q.query_id for q in self.queries}

        if len(doc_ids) != len(self.documents):
            raise ValueError("doc_id en double dans le corpus")
        if len(query_ids) != len(self.queries):
            raise ValueError("query_id en double dans les requêtes")

        orphan_queries = set(self.qrels) - query_ids
        if orphan_queries:
            raise ValueError(
                f"qrels référencent des requêtes absentes : {sorted(orphan_queries)[:5]}"
            )
        orphan_docs = {doc_id for judged in self.qrels.values() for doc_id in judged} - doc_ids
        if orphan_docs:
            raise ValueError(f"qrels référencent des documents absents : {sorted(orphan_docs)[:5]}")

        unjudged = query_ids - set(self.qrels)
        if unjudged:
            raise ValueError(
                f"requêtes sans aucun jugement : {sorted(unjudged)[:5]} — "
                "le loader doit filtrer les requêtes hors split"
            )
        return self

    def document_by_id(self, doc_id: str) -> Document:
        try:
            return self._documents_by_id[doc_id]
        except KeyError:
            raise KeyError(f"document inconnu : {doc_id!r}") from None

    def relevant_doc_ids(self, query_id: str, min_relevance: int = 1) -> set[str]:
        return {
            doc_id for doc_id, rel in self.qrels.get(query_id, {}).items() if rel >= min_relevance
        }

    @property
    def _documents_by_id(self) -> dict[str, Document]:
        # Index paresseux, caché sur l'instance (autorisé malgré frozen car hors modèle).
        cached: dict[str, Document] | None = self.__dict__.get("_doc_index")
        if cached is None:
            cached = {d.doc_id: d for d in self.documents}
            object.__setattr__(self, "_doc_index", cached)
        return cached

    def describe(self) -> dict[str, int | str | bool]:
        """Résumé compact — ce qu'affiche le notebook, ce que loggera le harness."""
        judgments = sum(len(j) for j in self.qrels.values())
        return {
            "dataset": self.info.key,
            "split": self.split,
            "documents": len(self.documents),
            "queries": len(self.queries),
            "judgments": judgments,
            "sampled": self.sampled,
        }
