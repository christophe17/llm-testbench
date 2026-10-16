# PHASE 0 — Fondations (semaine 1)

**Statut : terminée** (PR #1 fusionnée le 2026-08-26 ; clôture documentée le 2026-09-03).

Repo, outillage, CI (lint, typecheck, tests, exécution des notebooks), cluster local,
Postgres/pgvector.

Avant de commencer : questions bloquantes (clés API disponibles, budget mensuel accepté, temps
hebdomadaire réel), puis vérification de la disponibilité, de la taille et de la licence de
chaque jeu de données, et proposition du sous-ensemble de démarrage le plus petit possible.
**En phase 0 on ne construit que l'interface de chargement et UN loader de référence** — un
seul jeu, le plus petit. Les autres loaders arrivent au fil des phases qui en ont besoin.

**Notebook 0** : visite guidée de l'architecture cible et de ce que chaque module fera. Plus :
à quoi ressemble chaque jeu de données, ce qu'il mesure, ce qu'il ne mesure pas.

## Ce qui a été arbitré

- Clés API : OpenAI, Anthropic, OpenRouter ; Mistral et autres via OpenRouter tant qu'il n'y a
  pas de clé dédiée. Pas de plafond de budget a priori. Pas de calendrier.
- Loader de référence : BEIR/SciFact (ADR 001, ADR 004).
- Langfuse et modules cloud AWS reportés en phase 1 ; en phase 0, bootstrap Terraform seul
  (bucket d'état + budget 55 USD avec alertes) (ADR 002).
- CI hors ligne sans secret, notebooks en mode échantillon (ADR 003).

## Première action du brief (historique, faite le 2026-08-26)

Écrire le brief dans `CLAUDE.md`, créer `STATE.md` et `JOURNAL.md`, signaler les problèmes du
plan, vérifier les jeux de données, poser les questions bloquantes, puis attendre
`GO PHASE 0`.
