"""BIRD Mini-Dev : text-to-SQL réaliste et volontairement sale, 500 instances SQLite.

Le jeu complet fait 33,4 Go ; Mini-Dev est le sous-ensemble officiel conçu pour
itérer (500 instances SELECT sur SQLite, avec les bases). Deux pièges :
1. le champ ``evidence`` (connaissance externe) doit être fourni au modèle,
   sinon les scores s'effondrent — il fait partie du protocole officiel ;
2. le zip est servi depuis Aliyun (Pékin) — lent depuis la France, d'où le
   cache local et le téléchargement en streaming avec reprise manuelle possible.
"""

import json
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import httpx
from tqdm import tqdm

from llm_testbench.config import get_settings
from llm_testbench.eval.types import SQLDataset, SQLExample

MINIDEV_URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"

Row = Mapping[str, Any]


def parse_bird_items(items: Iterable[Row]) -> list[SQLExample]:
    return [
        SQLExample(
            example_id=str(item["question_id"]),
            db_id=item["db_id"],
            question=item["question"],
            gold_sql=item["SQL"],
            evidence=item.get("evidence") or "",
            difficulty=item.get("difficulty") or "",
        )
        for item in items
    ]


def download_bird_minidev(force: bool = False) -> Path:
    """Télécharge et extrait Mini-Dev dans ``data/bird/`` (~500 Mo, une seule fois)."""
    dest = get_settings().data_dir / "bird"
    extracted = dest / "minidev"
    if extracted.exists() and not force:
        return extracted
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "minidev.zip"
    with httpx.stream("GET", MINIDEV_URL, follow_redirects=True, timeout=60.0) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        with (
            archive.open("wb") as fh,
            tqdm(total=total, unit="B", unit_scale=True, desc="minidev.zip") as bar,
        ):
            for chunk in response.iter_bytes():
                fh.write(chunk)
                bar.update(len(chunk))
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(extracted)
    archive.unlink()
    return extracted


def load_bird_minidev() -> SQLDataset:
    root = download_bird_minidev()
    json_path = next(root.glob("**/mini_dev_sqlite.json"), None)
    if json_path is None:
        raise FileNotFoundError(
            f"mini_dev_sqlite.json introuvable sous {root} — archive incomplète ? "
            "Supprimer data/bird/ et relancer."
        )
    items: list[Row] = json.loads(json_path.read_text(encoding="utf-8"))
    databases_dir = next(root.glob("**/dev_databases"), None)
    return SQLDataset(
        name="bird_minidev",
        split="mini_dev_sqlite",
        examples=parse_bird_items(items),
        databases_dir=databases_dir,
    )
