"""Téléchargement du sous-ensemble de démarrage : ``make data-starter``.

Les petits jeux (~150 Mo) sont téléchargés par défaut ; HotpotQA (1,3 Go) et
BIRD Mini-Dev (~500 Mo, serveur à Pékin) sont derrière ``--large`` pour ne pas
pénaliser la CI et les premières itérations.
"""

import argparse

from llm_testbench.eval.loaders.beir import load_beir
from llm_testbench.eval.loaders.bird_minidev import load_bird_minidev
from llm_testbench.eval.loaders.hotpotqa import load_hotpotqa
from llm_testbench.eval.loaders.qasper import load_qasper
from llm_testbench.eval.loaders.spider import load_spider
from llm_testbench.eval.loaders.squad_v2 import load_squad_v2
from llm_testbench.eval.loaders.tatqa import load_tatqa


def download_starter(include_large: bool = False) -> None:
    for name in ("scifact", "nfcorpus"):
        ds = load_beir(name)
        print(f"beir/{name:10s} {len(ds.documents):6d} docs, {len(ds.queries):5d} requêtes jugées")
    squad = load_squad_v2()
    unanswerable = sum(1 for ex in squad.examples if not ex.is_answerable)
    print(f"squad_v2         {len(squad.examples):6d} questions, {unanswerable} non répondables")
    papers = load_qasper()
    n_questions = sum(len(p.questions) for p in papers)
    print(f"qasper           {len(papers):6d} articles, {n_questions} questions")
    spider = load_spider()
    print(f"spider           {len(spider.examples):6d} paires question-SQL (dev)")
    tatqa = load_tatqa()
    print(f"tatqa            {len(tatqa.examples):6d} questions (dev)")
    if include_large:
        hotpot = load_hotpotqa()
        print(f"hotpotqa         {len(hotpot.examples):6d} questions (distractor/validation)")
        bird = load_bird_minidev()
        print(f"bird_minidev     {len(bird.examples):6d} instances, bases : {bird.databases_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Télécharge le starter du banc d'essai.")
    parser.add_argument(
        "--large",
        action="store_true",
        help="inclut HotpotQA (1,3 Go) et BIRD Mini-Dev (~500 Mo)",
    )
    args = parser.parse_args()
    download_starter(include_large=args.large)


if __name__ == "__main__":
    main()
