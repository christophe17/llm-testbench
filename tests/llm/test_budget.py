import pytest

from llm_testbench.llm.budget import TokenBudget, estimate_tokens
from llm_testbench.llm.errors import BudgetExceededError
from llm_testbench.llm.types import Usage


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_estimate_is_pessimistic_and_zero_for_empty() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_per_request_caps_refuse_before_the_call() -> None:
    budget = TokenBudget(max_input_tokens_per_request=100, max_output_tokens_per_request=50)
    budget.check(estimated_input_tokens=100, max_output_tokens=50)
    with pytest.raises(BudgetExceededError, match="plafond par requête 100"):
        budget.check(estimated_input_tokens=101, max_output_tokens=10)
    with pytest.raises(BudgetExceededError, match="max_output_tokens=51"):
        budget.check(estimated_input_tokens=1, max_output_tokens=51)


def test_window_budget_reserves_the_worst_case_and_forgets_old_usage() -> None:
    clock = FakeClock()
    budget = TokenBudget(max_tokens_per_window=1_000, window_s=60, clock=clock)
    budget.record(Usage(input_tokens=500, output_tokens=300))
    assert budget.spent_in_window() == 800
    budget.check(estimated_input_tokens=100, max_output_tokens=100)
    with pytest.raises(BudgetExceededError, match="800 tokens déjà consommés"):
        budget.check(estimated_input_tokens=100, max_output_tokens=101)

    clock.now = 61
    assert budget.spent_in_window() == 0
    budget.check(estimated_input_tokens=900, max_output_tokens=100)
    assert budget.snapshot() == {"spent_in_window": 0, "max_tokens_per_window": 1_000}


def test_unlimited_budget_accepts_everything() -> None:
    TokenBudget().check(estimated_input_tokens=10**9, max_output_tokens=10**9)
