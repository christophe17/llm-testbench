# STATE

> État courant du projet. Mis à jour à chaque session de travail. Lu en début de session avec `CLAUDE.md`, `JOURNAL.md` et les 3 derniers ADR.

## Phase en cours

**Phase 0 — Fondations** : construite le 2026-08-26, PR ouverte, en attente de relecture par Christophe.

## Fait

- 2026-08-26 : brief sauvegardé, fichiers de pilotage créés, datasets vérifiés (`docs/datasets-verification-2026-08-26.md`, figé dans ADR-001).
- 2026-08-26 : **phase 0 construite** — repo public `llm-testbench`, outillage (uv, ruff, mypy strict, pytest, pre-commit), CI GitHub Actions (lint + typecheck + tests + nbmake), 7 loaders de datasets avec 18 tests offline, cluster k3d local avec Postgres + pgvector 0.8.6 vérifié, squelette Terraform AWS (non appliqué), 3 ADR, notebook 0 exécuté de bout en bout.

## Chiffres actuels

Pas de chiffres de qualité (baseline en phase 2). Volumétries starter vérifiées :
SciFact 5 183 docs / 300 requêtes jugées · NFCorpus 3 633 docs / 323 requêtes ·
SQuAD 2.0 : 11 873 questions dont 50 % non répondables · QASPER 281 articles / 1 005 questions ·
Spider dev 1 034 · TAT-QA dev 1 644 · HotpotQA dev 7 405.

## Questions ouvertes

1. Compte AWS : à créer par Christophe avant le premier `terraform apply` (phase 1). Checklist : SSO, alerte budget, région `eu-west-3`.
2. Décisions arbitrées : repo `llm-testbench` ; Langfuse différé au premier appel LLM instrumenté (phase 1) — cf. ADR-002.

## Risques suivis

- Phase 4 (9 sous-blocs en 3 semaines) : la phase la plus chargée du plan — arbitrage de coupe à préparer.
- Notebooks avec appels LLM dans la CI (`nbmake`) : coût + flakiness — stratégie replay/cache à décider en phase 0/1.
- Langfuse v3 self-hosted est une stack lourde (ClickHouse, Redis, S3) : à dimensionner pour le local.
