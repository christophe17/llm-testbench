"""Loaders des jeux publics du banc d'essai.

Pattern commun à tous les modules : des fonctions de parsing **pures** (testées
hors ligne sur fixtures) + un chargeur réseau mince qui télécharge, cache dans
``data/`` et délègue le parsing. Aucune donnée n'est versionnée dans le repo.
"""

from llm_testbench.eval.loaders.beir import load_beir
from llm_testbench.eval.loaders.bird_minidev import load_bird_minidev
from llm_testbench.eval.loaders.hotpotqa import load_hotpotqa
from llm_testbench.eval.loaders.qasper import load_qasper
from llm_testbench.eval.loaders.spider import load_spider
from llm_testbench.eval.loaders.squad_v2 import load_squad_v2
from llm_testbench.eval.loaders.tatqa import load_tatqa

# Sous-ensemble de démarrage (cf. docs/datasets-verification-2026-08-26.md) :
# nom -> (ce que le jeu mesure, taille approximative du téléchargement).
STARTER_DATASETS: dict[str, tuple[str, str]] = {
    "beir/scifact": ("retrieval scientifique, 300 requêtes jugées", "5 Mo"),
    "beir/nfcorpus": ("retrieval médical, 323 requêtes jugées", "3 Mo"),
    "squad_v2": ("abstention : ~50 % de questions sans réponse", "46 Mo"),
    "hotpotqa": ("multi-hop avec passages de preuve annotés", "1,3 Go"),
    "qasper": ("documents bruts entiers + spans de preuve (chunking)", "26 Mo"),
    "spider": ("text-to-SQL, vérité = résultat d'exécution", "quelques Mo"),
    "bird_minidev": ("text-to-SQL réaliste et sale, 500 instances", "~500 Mo"),
    "tatqa": ("tables financières + texte, réponses avec échelle", "17 Mo"),
}

__all__ = [
    "STARTER_DATASETS",
    "load_beir",
    "load_bird_minidev",
    "load_hotpotqa",
    "load_qasper",
    "load_spider",
    "load_squad_v2",
    "load_tatqa",
]
