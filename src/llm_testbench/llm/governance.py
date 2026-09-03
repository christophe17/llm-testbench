"""Gouvernance des données : classes, métadonnées de backend, politique, décision (ADR 006).

Le principe : une requête porte une **classe de données**, un backend déclare des
**métadonnées de gouvernance**, une **politique** dit ce que chaque classe exige, et la
**décision** est prise avant tout appel réseau, par refus par défaut. Une métadonnée
inconnue (``None``) échoue à toute exigence : l'inconnu n'est jamais un laissez-passer.

Sur le banc d'essai, toutes les données sont publiques ; le mécanisme est là pour être
exercé, tracé et démontré, et pour accueillir les contraintes réelles quand elles seront
connues, sans toucher au code.
"""

import datetime as dt
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class DataClass(StrEnum):
    """Classe de données d'une requête. Sans classe explicite, une requête est refusée."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PERSONAL = "personal"
    REGULATED = "regulated"


class InferenceRegion(StrEnum):
    EU = "eu"
    US = "us"
    SELF = "self"
    """Sur notre propre machine ou notre propre cluster : le texte ne sort pas."""
    VARIABLE = "variable"
    """Courtier qui route vers des hébergeurs tiers : la région dépend de l'appel."""


class BackendGovernance(BaseModel):
    """Métadonnées de gouvernance d'un backend.

    Ce sont des affirmations relevées à ``verified_on``, pas des garanties contractuelles.
    ``zero_retention`` décrit la configuration effective de NOTRE compte chez ce fournisseur,
    pas ce qu'il propose (``zero_retention_available``).
    """

    model_config = ConfigDict(frozen=True)

    entity: str
    country: str
    inference_region: InferenceRegion
    default_retention_days: int | None = None
    zero_retention: bool | None = None
    zero_retention_available: bool | None = None
    trains_on_inputs: bool | None = None
    subprocessors: Literal["fixed", "variable"]
    certifications: tuple[str, ...] = ()
    verified_on: dt.date
    notes: str = ""


class Requirement(BaseModel):
    """Exigences d'une classe de données. Tout ce qui n'est pas exigé est permis."""

    model_config = ConfigDict(frozen=True)

    allowed_regions: tuple[InferenceRegion, ...] | None = None
    require_zero_retention: bool = False
    forbid_training: bool = False
    forbid_variable_subprocessors: bool = False


class GovernanceDecision(BaseModel):
    """Résultat de l'évaluation, destiné à la trace et à l'exception."""

    model_config = ConfigDict(frozen=True)

    data_class: DataClass
    backend: str
    allowed: bool
    reasons: tuple[str, ...] = ()
    """Vide si autorisé ; sinon, chaque exigence non satisfaite, en clair."""

    def enforce(self) -> None:
        # Import local : errors importe DataClass d'ici, on évite le cycle à l'import.
        from llm_testbench.llm.errors import GovernanceViolation

        if not self.allowed:
            raise GovernanceViolation(
                data_class=self.data_class, backend=self.backend, reasons=self.reasons
            )


class GovernancePolicy(BaseModel):
    """Politique : une exigence par classe de données, chargée depuis un fichier TOML."""

    model_config = ConfigDict(frozen=True)

    rules: dict[DataClass, Requirement]

    @model_validator(mode="after")
    def _every_class_has_a_rule(self) -> "GovernancePolicy":
        missing = [c.value for c in DataClass if c not in self.rules]
        if missing:
            raise ValueError(f"politique incomplète, classes sans règle : {missing}")
        return self

    @classmethod
    def load(cls, path: Path) -> "GovernancePolicy":
        with path.open("rb") as handle:
            return cls.model_validate(tomllib.load(handle))

    def evaluate(
        self, data_class: DataClass, backend: str, governance: BackendGovernance
    ) -> GovernanceDecision:
        rule = self.rules[data_class]
        reasons: list[str] = []

        region = governance.inference_region
        if rule.allowed_regions is not None and region not in rule.allowed_regions:
            allowed = ", ".join(r.value for r in rule.allowed_regions)
            reasons.append(f"région d'inférence {region.value!r} hors de [{allowed}]")
        if rule.require_zero_retention and governance.zero_retention is not True:
            state = "inconnue" if governance.zero_retention is None else "non configurée"
            reasons.append(f"rétention zéro exigée, {state}")
        if rule.forbid_training and governance.trains_on_inputs is not False:
            state = "inconnu" if governance.trains_on_inputs is None else "déclaré"
            reasons.append(f"entraînement sur les entrées interdit, {state}")
        if rule.forbid_variable_subprocessors and governance.subprocessors != "fixed":
            reasons.append("sous-traitants variables (courtier) interdits")

        return GovernanceDecision(
            data_class=data_class, backend=backend, allowed=not reasons, reasons=tuple(reasons)
        )
