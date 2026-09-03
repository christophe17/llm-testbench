"""Coût d'un appel à partir de l'usage et d'une table de prix datée (ADR 006).

Règle : un modèle sans prix connu donne ``None``, jamais une estimation. Un chiffre absent
se voit ; un chiffre inventé se propage jusqu'au tableau maître.
"""

import datetime as dt
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from llm_testbench.config import Settings, get_settings
from llm_testbench.llm.types import Usage

PRICING_FILENAME = "llm_pricing.toml"
_TOKENS_PER_UNIT = 1_000_000


class ModelPrice(BaseModel):
    """USD par million de tokens. Les prix de cache sont optionnels : s'ils manquent alors
    que l'usage en contient, le coût devient inconnu plutôt qu'approximatif."""

    model_config = ConfigDict(frozen=True)

    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float | None = None
    cache_write_per_mtok: float | None = None


class PricingTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    verified_on: dt.date
    source: str
    models: dict[str, ModelPrice]

    @classmethod
    def load(cls, path: Path) -> "PricingTable":
        with path.open("rb") as handle:
            return cls.model_validate(tomllib.load(handle))

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "PricingTable":
        settings = settings if settings is not None else get_settings()
        return cls.load(settings.resolved_config_dir() / PRICING_FILENAME)

    def price_for(self, model: str) -> ModelPrice | None:
        """Correspondance exacte, sinon sur le dernier segment (``anthropic/claude-x`` chez
        OpenRouter → ``claude-x``). Jamais de correspondance floue au-delà."""
        if model in self.models:
            return self.models[model]
        _, _, tail = model.rpartition("/")
        return self.models.get(tail) if tail else None

    def cost_usd(self, model: str, usage: Usage) -> float | None:
        price = self.price_for(model)
        if price is None:
            return None
        cost = usage.input_tokens * price.input_per_mtok
        cost += usage.output_tokens * price.output_per_mtok
        if usage.cache_read_tokens:
            if price.cache_read_per_mtok is None:
                return None
            cost += usage.cache_read_tokens * price.cache_read_per_mtok
        if usage.cache_write_tokens:
            if price.cache_write_per_mtok is None:
                return None
            cost += usage.cache_write_tokens * price.cache_write_per_mtok
        return cost / _TOKENS_PER_UNIT
