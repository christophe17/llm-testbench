"""TAT-QA : questions sur tables financières + paragraphes, réponses avec échelle.

La réponse brute est hétérogène (chaîne, nombre, liste) et vient avec un champ
``scale`` (« thousand », « percent »…) qui fait partie de la vérité : « 42 » à
l'échelle « million » n'est pas « 42 ». La normalisation vit ici, pas dans le
scorer. Source : les JSON bruts du repo officiel ``next-tat/TAT-QA`` sur le hub
(le viewer HF est cassé pour ce repo, les fichiers se téléchargent très bien).
"""

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download

from llm_testbench.config import get_settings
from llm_testbench.eval.types import TableQADataset, TableQAExample

_FILES = {
    "train": "tatqa_dataset_train.json",
    "dev": "tatqa_dataset_dev.json",
    "test": "tatqa_dataset_test.json",
}

Row = Mapping[str, Any]


def normalise_answer(answer: object) -> list[str]:
    """Aplatit la réponse brute (str | nombre | liste) en liste de chaînes."""
    if isinstance(answer, list):
        return [str(a) for a in answer]
    return [str(answer)]


def parse_tatqa_blocks(blocks: Iterable[Row]) -> list[TableQAExample]:
    examples: list[TableQAExample] = []
    for block in blocks:
        table = [[str(cell) for cell in row] for row in block["table"]["table"]]
        paragraphs = [p["text"] for p in sorted(block["paragraphs"], key=lambda p: int(p["order"]))]
        for q in block["questions"]:
            examples.append(
                TableQAExample(
                    example_id=str(q["uid"]),
                    question=q["question"],
                    table=table,
                    paragraphs=paragraphs,
                    answers=normalise_answer(q.get("answer", "")),
                    answer_type=q.get("answer_type") or "",
                    scale=str(q.get("scale") or ""),
                    derivation=str(q.get("derivation") or ""),
                )
            )
    return examples


def build_tatqa_dataset(split: str, blocks: Iterable[Row]) -> TableQADataset:
    return TableQADataset(name="tatqa", split=split, examples=parse_tatqa_blocks(blocks))


def load_tatqa(split: str = "dev") -> TableQADataset:
    if split not in _FILES:
        raise ValueError(f"Split TAT-QA inconnu : {split!r} (choix : {sorted(_FILES)})")
    path = hf_hub_download(
        repo_id="next-tat/TAT-QA",
        filename=_FILES[split],
        repo_type="dataset",
        cache_dir=str(get_settings().hf_cache_dir),
    )
    blocks: list[Row] = json.loads(Path(path).read_text(encoding="utf-8"))
    return build_tatqa_dataset(split, blocks)
