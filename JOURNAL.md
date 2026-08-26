# JOURNAL

> Historique daté du projet, en ordre antéchronologique (le plus récent en haut).
> Une entrée par session de travail significative. Format :
>
> ```markdown
> ## AAAA-MM-JJ — Phase N — titre court
>
> **Fait** : ce qui a été produit (code, notebook, infra, mesure).
> **Décidé** : arbitrages pris, avec lien ADR si structurant.
> **Chiffres** : métriques produites ou mises à jour (avant → après quand pertinent).
> **Appris / cassé** : ce qui a surpris, ce qui a échoué, matière pour les posts et les entretiens.
> **Prochain pas** : la première chose à faire à la session suivante.
> ```

---

## 2026-08-26 — Phase 0 — Fondations construites

**Fait** : repo public `llm-testbench` (branche `phase-0`, PR ouverte) ; outillage Python complet ; CI (lint, mypy strict, tests, nbmake) ; 7 loaders (`beir`, `squad_v2`, `hotpotqa`, `qasper`, `spider`, `bird_minidev`, `tatqa`) en pattern « parsing pur + chargeur mince », 18 tests offline sur fixtures synthétiques ; cluster k3d + Postgres/pgvector 0.8.6 vérifié ; Terraform AWS écrit non appliqué ; notebook 0 exécuté de bout en bout sur données réelles.
**Décidé** : ADR-001 (datasets : FUNSD retiré, DocVQA hors git, BIRD→Mini-Dev, τ-bench→tau2), ADR-002 (k3d d'abord, AWS et Langfuse différés phase 1), ADR-003 (package racine unique, MIT, données jamais versionnées).
**Chiffres** : volumétries starter validées contre les sources (SciFact 5 183/300, SQuAD 50 % non répondables, QASPER 281/1 005, Spider 1 034, TAT-QA 1 644, HotpotQA 7 405).
**Appris / cassé** : `allenai/qasper` héberge encore un script de chargement refusé par `datasets>=3.0` → branche `refs/convert/parquet` ; un kernelspec Jupyter utilisateur (`python3` → Homebrew 3.10) masquait le venv → kernel dédié `llm-testbench` enregistré par `make install` et par la CI ; `data_dir` relatif au CWD cassait depuis `notebooks/` → ancré à la racine du repo.
**Prochain pas** : relecture de la PR par Christophe, puis `GO PHASE 1` (couche LLM + interface `Source` + ingestion + API `/chat`).

## 2026-08-26 — Pré-phase 0 — Prise en main du brief

**Fait** : brief sauvegardé dans `CLAUDE.md`, création de `STATE.md` et `JOURNAL.md`, vérification de la disponibilité, taille et licence des jeux de données du banc d'essai.
**Décidé** : rien de figé — questions bloquantes posées (clés API, budget, temps hebdo).
**Chiffres** : aucun.
**Appris / cassé** : —
**Prochain pas** : attendre `GO PHASE 0`, puis plan d'une page pour la phase 0.
