from collections.abc import Callable
from typing import Any

from llm_testbench.eval.loaders.bird_minidev import parse_bird_items
from llm_testbench.eval.loaders.spider import build_sql_dataset


def test_spider_examples_are_indexed(fixture_json: Callable[[str], Any]) -> None:
    ds = build_sql_dataset("validation", fixture_json("spider.json"))

    # Spider n'a pas d'identifiant : l'index dans le split fait foi.
    assert [ex.example_id for ex in ds.examples] == ["0", "1"]
    assert ds.examples[0].db_id == "concert_singer"
    assert ds.examples[0].gold_sql == "SELECT count(*) FROM singer"
    assert ds.examples[0].evidence == ""


def test_bird_evidence_is_carried(fixture_json: Callable[[str], Any]) -> None:
    examples = parse_bird_items(fixture_json("bird_minidev.json"))

    # Le champ evidence fait partie du protocole BIRD : il doit survivre au parsing.
    assert examples[0].evidence.startswith("loan amount refers to")
    assert examples[0].difficulty == "moderate"


def test_bird_missing_evidence_defaults_to_empty(fixture_json: Callable[[str], Any]) -> None:
    examples = parse_bird_items(fixture_json("bird_minidev.json"))

    assert examples[1].example_id == "1"
    assert examples[1].evidence == ""
