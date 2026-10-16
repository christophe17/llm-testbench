import datetime as dt
from pathlib import Path

import pytest

from llm_testbench.llm.cost import ModelPrice, PricingTable
from llm_testbench.llm.types import Usage

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pricing() -> PricingTable:
    return PricingTable.load(REPO_ROOT / "config" / "llm_pricing.toml")


def test_known_model_cost_is_input_plus_output(pricing: PricingTable) -> None:
    usage = Usage(input_tokens=1_000, output_tokens=500)
    assert pricing.cost_usd("claude-sonnet-5", usage) == pytest.approx(0.002 + 0.005)


def test_cache_tokens_are_priced_separately(pricing: PricingTable) -> None:
    usage = Usage(input_tokens=1_000, output_tokens=0, cache_read_tokens=10_000)
    assert pricing.cost_usd("claude-sonnet-5", usage) == pytest.approx(0.002 + 0.002)


def test_openrouter_style_id_falls_back_to_last_segment(pricing: PricingTable) -> None:
    assert pricing.price_for("anthropic/claude-sonnet-5") is pricing.price_for("claude-sonnet-5")


def test_unknown_model_cost_is_none_not_zero(pricing: PricingTable) -> None:
    assert pricing.cost_usd("gpt-unknown", Usage(input_tokens=10, output_tokens=10)) is None
    assert pricing.price_for("vendor/") is None


def test_cache_usage_without_cache_price_is_unknown() -> None:
    table = PricingTable(
        verified_on=dt.date(2026, 9, 3),
        source="test",
        models={"m": ModelPrice(input_per_mtok=1.0, output_per_mtok=1.0)},
    )
    assert table.cost_usd("m", Usage(input_tokens=10, output_tokens=10)) == pytest.approx(2e-5)
    assert table.cost_usd("m", Usage(input_tokens=10, cache_read_tokens=10)) is None
