"""Spider 1.0 (dev) : text-to-SQL académique, requêtes propres sur 20 bases.

Le miroir Hugging Face ``xlangai/spider`` fournit questions + SQL de référence
mais **pas les bases SQLite** — elles seront téléchargées et converties vers
Postgres en phase 4 (la vérité de référence est le résultat d'exécution, pas la
chaîne SQL). Attention aux attentes : Spider est gelé depuis 2024 et saturé par
les modèles frontière (~86 %) — il valide le harness, il ne discrimine pas.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from datasets import load_dataset

from llm_testbench.config import get_settings
from llm_testbench.eval.types import SQLDataset, SQLExample

Row = Mapping[str, Any]


def parse_spider_rows(rows: Iterable[Row]) -> list[SQLExample]:
    # Spider n'a pas d'identifiant d'exemple : l'index dans le split fait foi.
    return [
        SQLExample(
            example_id=str(i),
            db_id=row["db_id"],
            question=row["question"],
            gold_sql=row["query"],
        )
        for i, row in enumerate(rows)
    ]


def build_sql_dataset(split: str, rows: Iterable[Row]) -> SQLDataset:
    return SQLDataset(name="spider", split=split, examples=parse_spider_rows(rows))


def load_spider(split: str = "validation") -> SQLDataset:
    rows = load_dataset("xlangai/spider", split=split, cache_dir=str(get_settings().hf_cache_dir))
    return build_sql_dataset(split, rows)
