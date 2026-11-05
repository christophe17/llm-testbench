"""A hard cap in dollars on what the harness spends (decision of 2026-11-05: $10).

Every paid run goes through a :class:`SpendLedger`: it refuses to start a call once the
money already spent (``data/results/spend.jsonl``, versioned, one line per run) plus the
money of the current run reaches the cap, and it writes its line when the run ends, even
when it ends on an error. A call whose price is unknown is refused: a cap cannot hold on a
number nobody knows. Sample mode spends nothing and has no ledger.
"""

import datetime as dt
import json
from pathlib import Path

LEDGER_PATH = Path("data") / "results" / "spend.jsonl"


class SpendCapExceededError(RuntimeError):
    """The cap is reached: the run stops before the next paid call."""


class SpendLedger:
    def __init__(self, path: Path, cap_usd: float) -> None:
        self._path = path
        self.cap_usd = cap_usd
        self.session_usd = 0.0

    def recorded_usd(self) -> float:
        if not self._path.is_file():
            return 0.0
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return sum(float(json.loads(line)["usd"]) for line in lines if line.strip())

    @property
    def spent_usd(self) -> float:
        return self.recorded_usd() + self.session_usd

    def check(self) -> None:
        if self.spent_usd >= self.cap_usd:
            raise SpendCapExceededError(
                f"spend cap reached: ${self.spent_usd:.2f} of ${self.cap_usd:.2f} "
                f"({self._path}); raise the cap in config/eval_suites.toml to go on"
            )

    def charge(self, cost_usd: float | None, what: str) -> None:
        if cost_usd is None:
            raise SpendCapExceededError(
                f"{what}: unknown price, so the cap cannot be enforced; add the model to "
                "config/llm_pricing.toml"
            )
        self.session_usd += cost_usd

    def commit(self, label: str) -> None:
        """Write what this run spent as one line of the ledger, then start from zero."""
        if self.session_usd <= 0.0:
            return
        entry = {
            "at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "label": label,
            "usd": round(self.session_usd, 6),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        self.session_usd = 0.0
