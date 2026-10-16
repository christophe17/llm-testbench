import datetime as dt
from pathlib import Path

import pytest

from llm_testbench.llm.errors import GovernanceViolation
from llm_testbench.llm.governance import (
    BackendGovernance,
    DataClass,
    GovernancePolicy,
    InferenceRegion,
    Requirement,
)
from llm_testbench.llm.registry import Registry

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config"


@pytest.fixture(scope="module")
def policy() -> GovernancePolicy:
    return GovernancePolicy.load(CONFIG / "governance_policy.toml")


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.load(CONFIG / "llm_backends.toml")


def _decide(policy: GovernancePolicy, registry: Registry, data_class: DataClass, backend: str):  # type: ignore[no-untyped-def]
    return policy.evaluate(data_class, backend, registry.get(backend).governance)


def test_public_data_is_allowed_everywhere(policy: GovernancePolicy, registry: Registry) -> None:
    for backend in registry.backends:
        decision = _decide(policy, registry, DataClass.PUBLIC, backend)
        assert decision.allowed, decision.reasons


SENSITIVE = [DataClass.CONFIDENTIAL, DataClass.PERSONAL, DataClass.REGULATED]


@pytest.mark.parametrize("data_class", SENSITIVE)
def test_sensitive_data_refuses_us_providers_and_brokers_but_allows_eu_and_self(
    policy: GovernancePolicy, registry: Registry, data_class: DataClass
) -> None:
    anthropic = _decide(policy, registry, data_class, "anthropic")
    assert not anthropic.allowed
    assert any("région" in r for r in anthropic.reasons)
    assert any("rétention zéro" in r for r in anthropic.reasons)

    openrouter = _decide(policy, registry, data_class, "openrouter")
    assert not openrouter.allowed
    assert any("courtier" in r for r in openrouter.reasons)
    assert any("inconnu" in r for r in openrouter.reasons)

    for compliant in ("bedrock", "local"):
        decision = _decide(policy, registry, data_class, compliant)
        assert decision.allowed, decision.reasons


def test_internal_data_only_requires_no_training(
    policy: GovernancePolicy, registry: Registry
) -> None:
    assert _decide(policy, registry, DataClass.INTERNAL, "anthropic").allowed
    assert _decide(policy, registry, DataClass.INTERNAL, "openai").allowed
    broker = _decide(policy, registry, DataClass.INTERNAL, "openrouter")
    assert not broker.allowed
    assert broker.reasons == ("entraînement sur les entrées interdit, inconnu",)


def test_unknown_metadata_fails_closed() -> None:
    policy = GovernancePolicy(
        rules={
            **{c: Requirement() for c in DataClass},
            DataClass.REGULATED: Requirement(require_zero_retention=True, forbid_training=True),
        }
    )
    unknown = BackendGovernance(
        entity="x",
        country="x",
        inference_region=InferenceRegion.EU,
        subprocessors="fixed",
        verified_on=dt.date(2026, 9, 3),
    )
    decision = policy.evaluate(DataClass.REGULATED, "x", unknown)
    assert decision.reasons == (
        "rétention zéro exigée, inconnue",
        "entraînement sur les entrées interdit, inconnu",
    )


def test_policy_must_cover_every_data_class() -> None:
    with pytest.raises(ValueError, match="classes sans règle"):
        GovernancePolicy(rules={DataClass.PUBLIC: Requirement()})


def test_enforce_raises_a_typed_violation_with_context(
    policy: GovernancePolicy, registry: Registry
) -> None:
    decision = _decide(policy, registry, DataClass.REGULATED, "openrouter")
    with pytest.raises(GovernanceViolation, match="openrouter") as info:
        decision.enforce()
    assert info.value.data_class is DataClass.REGULATED
    assert info.value.backend == "openrouter"
    assert info.value.reasons == decision.reasons
    _decide(policy, registry, DataClass.PUBLIC, "openrouter").enforce()
