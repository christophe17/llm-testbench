# STATE

> État courant du projet. Mis à jour à chaque session de travail. Lu en début de session avec `CLAUDE.md`, `JOURNAL.md` et les 3 derniers ADR.

## Phase en cours

**Phase 0 — Fondations** : `GO` reçu le 2026-08-26. Plan soumis, en attente du feu vert.

## Fait

- 2026-08-26 : brief sauvegardé dans `CLAUDE.md`, `STATE.md` et `JOURNAL.md` créés.
- 2026-08-26 : vérification disponibilité / taille / licence des jeux de données → `docs/datasets-verification-2026-08-26.md` (à figer dans un ADR en phase 0).

## Chiffres actuels

Aucun. La baseline chiffrée arrive en phase 2.

## Questions ouvertes

Répondues le 2026-08-26 → voir « Décisions figées » dans `CLAUDE.md`. Restent ouvertes (plan phase 0) :

1. Nom du repo public.
2. Langfuse en local : docker-compose complet dès la phase 0, ou différé au cloud en phase 1 ?
3. Création du compte AWS : pendant la phase 0 (Terraform appliqué en fin de phase) ou au début de la phase 1 ?

## Risques suivis

- Phase 4 (9 sous-blocs en 3 semaines) : la phase la plus chargée du plan — arbitrage de coupe à préparer.
- Notebooks avec appels LLM dans la CI (`nbmake`) : coût + flakiness — stratégie replay/cache à décider en phase 0/1.
- Langfuse v3 self-hosted est une stack lourde (ClickHouse, Redis, S3) : à dimensionner pour le local.
