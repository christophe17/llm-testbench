"""Prompts versionnés en fichiers (brief §4, ADR 006).

Un prompt est un fichier ``prompts/<nom>.md`` : un en-tête entre ``---`` (nom, version,
description) puis un corps Jinja2. Deux règles non négociables :

- **variables strictes** : une variable manquante est une erreur, pas une chaîne vide —
  un prompt silencieusement tronqué produit des chiffres faux sans le dire ;
- **empreinte** : chaque rendu porte le SHA-256 du texte exact envoyé au modèle, inscrit
  dans la trace. Six mois plus tard, on sait quel texte a produit quel chiffre.
"""

import hashlib
import re
from pathlib import Path

from jinja2 import Environment, StrictUndefined, TemplateError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from llm_testbench.config import Settings, get_settings
from llm_testbench.llm.errors import PromptError

_FRONTMATTER = re.compile(r"\A---\n(?P<header>.*?)\n---\n?(?P<body>.*)\Z", re.DOTALL)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PromptTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: int = Field(ge=1)
    description: str
    body: str
    source_sha256: str
    """Empreinte du fichier entier : change dès qu'un caractère du prompt change."""
    path: Path


class RenderedPrompt(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: int
    text: str
    sha256: str
    """Empreinte du texte rendu, variables incluses : ce qui est réellement parti."""
    template_sha256: str

    def trace_metadata(self) -> dict[str, str]:
        """Ce que la façade copie dans ``CompletionRequest.metadata``."""
        return {
            "prompt.name": self.name,
            "prompt.version": str(self.version),
            "prompt.sha256": self.sha256,
            "prompt.template_sha256": self.template_sha256,
        }


def _parse_header(header: str, path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in header.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise PromptError(f"{path} : ligne d'en-tête invalide {line!r} (attendu clé: valeur)")
        fields[key.strip()] = value.strip()
    return fields


def parse_prompt_file(path: Path) -> PromptTemplate:
    if not path.is_file():
        raise PromptError(f"prompt introuvable : {path}")
    source = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(source)
    if match is None:
        raise PromptError(f"{path} : en-tête ``---`` absent ou mal fermé")
    fields = _parse_header(match.group("header"), path)
    if fields.get("name") != path.stem:
        raise PromptError(
            f"{path} : le champ name ({fields.get('name')!r}) doit valoir le nom du fichier "
            f"({path.stem!r})"
        )
    try:
        return PromptTemplate(
            name=path.stem,
            version=int(fields.get("version", "")),
            description=fields.get("description", ""),
            body=match.group("body").strip("\n"),
            source_sha256=_sha256(source),
            path=path,
        )
    except (ValueError, ValidationError) as error:
        raise PromptError(f"{path} : en-tête invalide ({error})") from None


class PromptRegistry:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._env = Environment(
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )
        self._cache: dict[str, PromptTemplate] = {}

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "PromptRegistry":
        settings = settings if settings is not None else get_settings()
        return cls(settings.resolved_prompts_dir())

    @property
    def root(self) -> Path:
        return self._root

    def names(self) -> list[str]:
        return sorted(p.stem for p in self._root.glob("*.md"))

    def get(self, name: str) -> PromptTemplate:
        if name not in self._cache:
            self._cache[name] = parse_prompt_file(self._root / f"{name}.md")
        return self._cache[name]

    def render(self, prompt: str, /, **variables: object) -> RenderedPrompt:
        """Le nom du prompt est positionnel-seul : un prompt peut avoir une variable
        ``name`` sans collision avec ce paramètre."""
        template = self.get(prompt)
        try:
            text = self._env.from_string(template.body).render(**variables)
        except TemplateError as error:
            raise PromptError(f"prompt {prompt!r} v{template.version} : {error}") from None
        return RenderedPrompt(
            name=template.name,
            version=template.version,
            text=text,
            sha256=_sha256(text),
            template_sha256=template.source_sha256,
        )
