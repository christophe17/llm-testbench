"""The manifest of the in-house corpus: which documents, under which license, and for
which models they are fresh.

The documents themselves are never versioned (``data/cache/``): the manifest is. It is the
contract that lets anyone rebuild the same corpus (identifiers, versions, hashes) and the
record of the two properties the corpus was chosen for:

- **freshness**: every document first became public after ``freshness_floor``, and the
  floor is after the date each listed model is known to have existed. A model cannot have
  been trained on a text published after it was released. This is a dated property:
  a newer model voids it, and :meth:`Manifest.fresh_for` says so instead of assuming;
- **difficulty**: what each document holds that a PDF extraction gets wrong, counted on
  its reference text.
"""

import datetime as dt
import hashlib
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_testbench.eval.corpus.reference import ReferenceFeatures

CORPUS_CONFIG = "corpus.toml"
MANIFEST_PATH = Path("data") / "corpus" / "arxiv-fresh" / "manifest.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class ModelFreshness(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available_by: dt.date
    """A date on which the model is known to have been available: its weights, and so its
    training data, are older than that."""
    evidence: str
    """Where that date comes from: a dated file of this repository, a release note."""


class GoldenConfig(BaseModel):
    """``[golden]`` of ``config/corpus.toml``: how the golden set is drafted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    drafter: str
    """``backend/model`` that writes the drafts: not the generator under test."""
    checker: str
    """``backend/model`` that rereads the whole paper for each draft marked unanswerable."""
    documents: int = Field(ge=1)
    per_document: int = Field(ge=1, le=6)
    seed: int = 0
    max_characters: int = Field(default=24_000, ge=1_000)
    """How much of a paper the drafter reads (the appendices are cut first)."""


class CorpusConfig(BaseModel):
    """``config/corpus.toml``: how the corpus is selected."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    freshness_floor: dt.date
    """A document is kept only if its first version was submitted on or after this day."""
    models: dict[str, ModelFreshness]
    set_spec: str = "cs"
    harvest_until: dt.date
    """Last day of the harvest window: fixed, so that the same command selects the same
    documents tomorrow."""
    categories: tuple[str, ...]
    """Primary categories kept."""
    license: str
    size: int = Field(ge=1)
    min_difficulty: int = Field(default=0, ge=0)
    min_tables: int = Field(default=0, ge=0)
    min_footnotes: int = Field(default=0, ge=0)
    min_characters: int = Field(default=0, ge=0)
    max_characters: int = Field(ge=1)
    """Bounds on the reference text: a three-page note has nothing to break, a
    hundred-page thesis costs like twenty papers."""
    golden: GoldenConfig | None = None

    @model_validator(mode="after")
    def _the_floor_is_after_every_model(self) -> "CorpusConfig":
        late = {
            name: model.available_by
            for name, model in self.models.items()
            if model.available_by >= self.freshness_floor
        }
        if late:
            raise ValueError(
                f"freshness floor {self.freshness_floor} is not after these models: {late}"
            )
        if self.harvest_until < self.freshness_floor:
            raise ValueError("the harvest window ends before the freshness floor")
        return self

    @classmethod
    def load(cls, path: Path) -> "CorpusConfig":
        with path.open("rb") as handle:
            return cls.model_validate(tomllib.load(handle))


class ManifestEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    arxiv_id: str
    version: int
    title: str
    authors: str
    """Kept for attribution: the license (CC BY 4.0) requires naming the authors."""
    categories: tuple[str, ...]
    license: str
    submitted: dt.datetime
    reference_sha256: str
    """Fingerprint of the reference text (title and sections), not of the HTML page: the
    page carries arXiv's own header and footer, which change without the paper changing."""
    pdf_sha256: str
    pdf_bytes: int
    features: ReferenceFeatures

    @property
    def doc_id(self) -> str:
        return f"{self.arxiv_id}v{self.version}"

    @property
    def url(self) -> str:
        return f"https://arxiv.org/abs/{self.doc_id}"


class Manifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    built_at: dt.datetime
    freshness_floor: dt.date
    models: dict[str, ModelFreshness]
    selection: dict[str, str | int | list[str]]
    """The rule that picked the documents, as it was configured."""
    candidates_seen: int
    """Fresh papers under the right license examined before ``size`` were kept."""
    documents: tuple[ManifestEntry, ...]

    def fresh_for(self, model: str) -> bool:
        """True only when the model is listed and the floor is after it. An unknown model
        is not fresh by default: the property has to be established, not assumed."""
        known = self.models.get(model.rpartition("/")[2])
        return known is not None and known.available_by < self.freshness_floor

    def entry(self, doc_id: str) -> ManifestEntry:
        for document in self.documents:
            if document.doc_id == doc_id:
                return document
        raise KeyError(f"unknown document: {doc_id!r}")

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=1) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
