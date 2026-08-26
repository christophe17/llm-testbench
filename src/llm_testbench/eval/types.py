"""Types partagés par tous les loaders de jeux de données.

Chaque famille de jeu (retrieval, QA, text-to-SQL, table-QA) a un modèle de
sortie unique : les runners de la phase 2 consomment ces types et rien d'autre.
C'est la frontière qui isole le harness des formats bruts hétérogènes.
"""

from pathlib import Path

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- retrieval


class Document(BaseModel):
    doc_id: str
    title: str = ""
    text: str


class Query(BaseModel):
    query_id: str
    text: str


class RetrievalDataset(BaseModel):
    """Corpus + requêtes + jugements de pertinence (format BEIR généralisé).

    ``qrels`` : query_id -> {doc_id: niveau de pertinence}. Un niveau > 0 signifie
    pertinent ; certains jeux ont des niveaux gradués (utile pour nDCG).
    """

    name: str
    documents: list[Document]
    queries: list[Query]
    qrels: dict[str, dict[str, int]]


# --------------------------------------------------------------------------- QA


class QAExample(BaseModel):
    """Question + contextes fournis par le jeu + réponses de référence.

    ``answers`` vide <=> ``is_answerable`` False : le comportement attendu du
    système est alors un refus explicite, et le harness mesurera le taux de
    refus correct / abusif.
    """

    example_id: str
    question: str
    contexts: list[Document] = Field(default_factory=list)
    answers: list[str] = Field(default_factory=list)
    is_answerable: bool
    # Ids des passages de preuve quand le jeu les annote (HotpotQA).
    supporting_doc_ids: list[str] = Field(default_factory=list)
    # Textes de preuve quand le jeu annote du texte, pas des ids (QASPER).
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class QADataset(BaseModel):
    name: str
    split: str
    examples: list[QAExample]


# ------------------------------------------------------------------ QASPER (document entier)


class PaperSection(BaseModel):
    section_name: str
    paragraphs: list[str]


class QasperPaper(BaseModel):
    """Article scientifique complet + questions ancrées sur des preuves.

    Contrairement aux jeux à passages pré-découpés, le document entier est
    conservé : c'est le support du duel de stratégies de chunking (phase 3).
    """

    paper_id: str
    title: str
    abstract: str
    sections: list[PaperSection]
    questions: list[QAExample]


# --------------------------------------------------------------------------- text-to-SQL


class SQLExample(BaseModel):
    example_id: str
    db_id: str
    question: str
    gold_sql: str
    # BIRD : connaissance externe à fournir au modèle, sinon les scores s'effondrent.
    evidence: str = ""
    difficulty: str = ""


class SQLDataset(BaseModel):
    name: str
    split: str
    examples: list[SQLExample]
    # Répertoire des bases SQLite quand elles sont téléchargées (BIRD Mini-Dev).
    databases_dir: Path | None = None


# --------------------------------------------------------------------------- table-QA


class TableQAExample(BaseModel):
    """TAT-QA : question sur table + paragraphes, réponse typée avec échelle.

    ``scale`` ("thousand", "million", "percent"…) fait partie de la réponse :
    un scorer qui l'ignore compte faux des résultats justes, et inversement.
    """

    example_id: str
    question: str
    table: list[list[str]]
    paragraphs: list[str]
    answers: list[str]
    answer_type: str  # span | multi-span | arithmetic | count
    scale: str = ""
    derivation: str = ""


class TableQADataset(BaseModel):
    name: str
    split: str
    examples: list[TableQAExample]
