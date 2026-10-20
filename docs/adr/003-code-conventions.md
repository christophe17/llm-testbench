# ADR 003 — Conventions de code et d'outillage

- **Date** : 2026-08-26
- **Statut** : accepté

## Contexte

Décisions figées du brief (§4) à matérialiser en configuration exécutable, plus quelques
arbitrages laissés ouverts.

## Décisions

- **Python 3.12 exclusivement** (`requires-python = ">=3.12,<3.13"`), géré par `uv`
  (lockfile versionné, `uv sync --frozen` en CI). Exception connue : BFCL (phase 4)
  impose 3.10 → environnement séparé, ADR 001.
- **Package `llm_testbench`**, layout `src/`, `py.typed`. Prose en français, identifiants
  et code en anglais ; docstrings en français car le premier lecteur est l'apprenant.
- **ruff** (lint + format, ligne 100, règles E/W/F/I/UP/B/SIM/RUF/PT/T20) ; **mypy strict**
  sur tout `src/` et `tests/`.
- **Tests hors ligne par défaut** : le marqueur `network` isole tout test qui télécharge ;
  la CI n'exécute que `-m "not network"`. Les loaders acceptent un répertoire de fixtures
  (`LLM_TESTBENCH_FIXTURES_DIR`) pour que la même logique de jointure tourne sur fixtures
  et données réelles — on ne teste pas un mock de la logique, on rejoue la vraie logique
  sur des données minuscules.
- **Mode échantillon** : `LLM_TESTBENCH_SAMPLE=1` + `sampled=True` porté par les données
  elles-mêmes. Tout chiffre issu d'un jeu `sampled` est non publiable, par construction.
- **CI GitHub Actions sans secret** : lint, typecheck, tests hors ligne, notebooks via
  nbmake en mode échantillon sur fixtures. Les exécutions complètes (chiffres publiés)
  sont manuelles et archivées.
- **pre-commit** : hooks fichiers + ruff + mypy. `check-added-large-files` à 2 MB pour
  bloquer un commit de données par accident.

## Conséquences

`make check` reproduit la CI localement. Le coût : mypy strict impose des annotations
partout, y compris dans les tests — assumé, c'est le niveau attendu du code de prod.
