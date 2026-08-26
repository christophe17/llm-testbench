# ADR-003 — Conventions de code : package racine unique, parsing pur, MIT

- **Statut** : accepté
- **Date** : 2026-08-26
- **Phase** : 0

## Contexte

La structure du brief liste `src/app`, `src/llm`, `src/eval`… Il faut la
traduire en packaging Python réel, et fixer le pattern des loaders avant que le
harness ne grossisse.

## Options considérées

1. **Packages top-level** (`import eval`, `import llm`) — colle à la lettre du
   brief, mais `eval` masque la builtin Python, et `app`/`llm` sont des noms de
   modules à collision quasi garantie.
2. **Package racine unique** `src/llm_testbench/` avec les mêmes sous-modules —
   un préfixe d'import en plus, zéro collision, `py.typed` propre.

## Décision

- Option 2 : `from llm_testbench.eval.loaders import load_beir`. La structure
  du brief est respectée un niveau plus bas.
- **Pattern loader** : fonctions de parsing **pures** (testées hors ligne sur
  fixtures synthétiques) + chargeur réseau mince qui télécharge et délègue.
  Les tests réseau existent mais sont marqués `network` et exclus par défaut —
  la suite tourne hors ligne, comme l'exige le brief.
- **Licence du code : MIT** — standard, compatible avec l'objectif vitrine.
  Les données gardent leurs licences (cf. ADR-001).
- Config centralisée (`pydantic-settings`, préfixe `LTB_`), `data_dir` ancré à
  la racine du repo (pas au CWD — les notebooks s'exécutent depuis
  `notebooks/`).

## Conséquences

- Toute nouvelle source de données suit le même pattern : parse pur + loader.
- mypy strict passe sur l'ensemble ; `datasets` (non typé) est le seul override.
- Si le projet était un jour installé non-editable, l'ancrage `data_dir`
  devrait être revu (documenté dans `config.py`).
