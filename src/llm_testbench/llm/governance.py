"""Data governance: classes, backend metadata, policy, decision (ADR 006).

The principle: a request carries a **data class**, a backend declares
**governance metadata**, a **policy** says what each class requires, and the
**decision** is made before any network call, deny by default. An unknown metadata
value (``None``) fails every requirement: the unknown is never a free pass.

On the testbench, all data is public; the mechanism is there to be
exercised, traced and demonstrated, and to take in the real constraints once they are
known, without touching the code.
"""

import datetime as dt
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class DataClass(StrEnum):
    """Data class of a request. Without an explicit class, a request is refused."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PERSONAL = "personal"
    REGULATED = "regulated"


class InferenceRegion(StrEnum):
    EU = "eu"
    US = "us"
    SELF = "self"
    """On our own machine or our own cluster: the text does not leave."""
    VARIABLE = "variable"
    """Broker that routes to third-party hosts: the region depends on the call."""


class BackendGovernance(BaseModel):
    """Governance metadata of a backend.

    These are claims recorded on ``verified_on``, not contractual guarantees.
    ``zero_retention`` describes the effective configuration of OUR account with this provider,
    not what it offers (``zero_retention_available``).
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
    """Requirements of a data class. Everything not required is allowed."""

    model_config = ConfigDict(frozen=True)

    allowed_regions: tuple[InferenceRegion, ...] | None = None
    require_zero_retention: bool = False
    forbid_training: bool = False
    forbid_variable_subprocessors: bool = False


class GovernanceDecision(BaseModel):
    """Result of the evaluation, intended for the trace and the exception."""

    model_config = ConfigDict(frozen=True)

    data_class: DataClass
    backend: str
    allowed: bool
    reasons: tuple[str, ...] = ()
    """Empty if allowed; otherwise, each unmet requirement, in plain words."""

    def enforce(self) -> None:
        # Local import: errors imports DataClass from here, this avoids the import cycle.
        from llm_testbench.llm.errors import GovernanceViolation

        if not self.allowed:
            raise GovernanceViolation(
                data_class=self.data_class, backend=self.backend, reasons=self.reasons
            )


class GovernancePolicy(BaseModel):
    """Policy: one requirement per data class, loaded from a TOML file."""

    model_config = ConfigDict(frozen=True)

    rules: dict[DataClass, Requirement]

    @model_validator(mode="after")
    def _every_class_has_a_rule(self) -> "GovernancePolicy":
        missing = [c.value for c in DataClass if c not in self.rules]
        if missing:
            raise ValueError(f"incomplete policy, classes without a rule: {missing}")
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
            reasons.append(f"inference region {region.value!r} outside [{allowed}]")
        if rule.require_zero_retention and governance.zero_retention is not True:
            state = "unknown" if governance.zero_retention is None else "not configured"
            reasons.append(f"zero retention required, {state}")
        if rule.forbid_training and governance.trains_on_inputs is not False:
            state = "unknown" if governance.trains_on_inputs is None else "declared"
            reasons.append(f"training on inputs forbidden, {state}")
        if rule.forbid_variable_subprocessors and governance.subprocessors != "fixed":
            reasons.append("variable subprocessors (broker) forbidden")

        return GovernanceDecision(
            data_class=data_class, backend=backend, allowed=not reasons, reasons=tuple(reasons)
        )
