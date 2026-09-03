# STATE

> Instantané de l'état du projet. Mis à jour à chaque session de travail.
> Historique détaillé dans `JOURNAL.md`, décisions dans `docs/adr/`.

## Phase en cours

**Phase 1 — Squelette de production : en cours** (démarrée le 2026-09-03, branche `phase-1`,
plan validé le même jour). Phase 0 terminée (PR #1 mergée le 2026-08-27). PR #2 (docs :
phase 5B + clôture phase 0) en attente de merge — `phase-1` est branchée dessus, à rebaser
sur `main` avant l'ouverture de sa PR si le merge est fait en squash.

Ordre de construction : bootstrap AWS (guide `docs/infra/00-bootstrap.md`, exécuté par
Christophe) → couche LLM + gouvernance + prompts versionnés → sources, ingestion, pgvector →
API `/chat` SSE → Langfuse/OTel → Terraform `envs/dev` + Helm → notebooks 1 et 2 → traces.

## Fait

- Brief consolidé dans `CLAUDE.md` (+ §8 décisions au fil de l'eau), fichiers de pilotage.
- Vérification web des jeux de données : `docs/datasets-verification-2026-08-26.md`.
  À retenir : τ-bench déprécié → `tau2-bench` ; NQ retiré (145 GB) ; BIRD via Mini-Dev
  (bases PostgreSQL incluses) ; licences à signaler : ChartQA GPL-3.0, FUNSD non
  commercial, DocVQA floue.
- Outillage : uv + Python 3.12, ruff, mypy strict, pytest, pre-commit, Makefile.
- Interface de chargement (`eval/types.py`, validation d'intégrité à la construction,
  flag `sampled`) + loader de référence BEIR/SciFact, testé hors ligne sur fixtures
  (13 tests) et validé contre le vrai dépôt HF (5 183 docs / 300 requêtes, conformes
  au papier BEIR).
- CI GitHub Actions hors ligne : lint, mypy strict, tests, notebook via nbmake en mode
  échantillon (kernel Jupyter dédié `llm-testbench`, enregistré par `make setup`).
- Cluster local : k3d (mis à jour en 5.9.0) + Postgres 16 + pgvector 0.8.6, vérifié de
  bout en bout (`make k3d-up` → extension active), Tiltfile minimal.
- Terraform `bootstrap/` : bucket d'état S3 chiffré/versionné (verrouillage natif S3),
  budget 55 USD avec alertes 80/100 % réel + 100 % prévisionnel. **Non appliqué** — voir
  questions ouvertes.
- Notebook 0 exécuté et versionné avec ses sorties (mode complet ET mode échantillon).
- ADR 001 (datasets), 002 (report AWS/Langfuse), 003 (conventions), 004 (interface loaders),
  005 (phase 5B).
- 2026-08-27 : audit marché (offres AI Engineer France 2026) → roadmap étendue à 10
  phases : GraphRAG (phase 3), mémoire d'agent (4.10), UI de chat minimale (phase 5),
  phase 9 Voice, phase 10 Browser/computer use (optionnelle). Frameworks en comparaison
  chiffrée bornée : même agent porté sur smolagents, OpenAI Agents SDK et CrewAI (4.1),
  LlamaIndex vs notre pipeline (phase 3). Détail dans `CLAUDE.md` §8 et `JOURNAL.md`.
- 2026-08-31 : amendement — phase 5B « Le pont » (ML classique vs LLM vs hybride, ~1 semaine,
  entre 5 et 6, six bras dont l'hybride classique GBM + n-grams), règle §6 reformulée avec
  exception bornée (trois verrous), ADR 005. Jeux arbitrés : `fake_job_postings2` + Banking77.

## Chiffres actuels

Aucun score encore (normal : les métriques arrivent en phase 2). Repère cible noté :
BM25 ≈ 0,67 nDCG@10 sur SciFact (papier BEIR).

## Décisions en attente d'arbitrage

- **Bootstrap AWS à appliquer par Christophe** en suivant `docs/infra/00-bootstrap.md`
  (compte AWS existant, région eu-west-3, aucun budget ni bucket d'état à ce jour — le
  bucket `eks-foundations-terraform-chris` appartient à un autre projet, on n'y touche pas).
  Les modules `envs/dev` en dépendent.
- Merge de la PR #2.
- Contraintes réelles de gouvernance des données : inconnues à ce jour, mécanisme construit
  en phase 1 avec une politique permissive sur données publiques ; à durcir quand elles se
  préciseront (CLAUDE.md §8, 2026-09-03).
- Candidat d'extension post-phase 10 (noté le 2026-09-01, décision GO/NO-GO **après la
  phase 5**, pas avant) : la boucle de données LLMOps — traces de la phase 5 → échantillonnage
  → étiquetage par le juge calibré (phase 2) → curation → extension du golden set et jeu
  d'entraînement du LoRA (phase 6). Pas de phase « pipeline de données » au sens data
  engineering (Kafka/Spark/dbt/CDC) : hors positionnement, données statiques, doublon de la
  phase 3 — voir `JOURNAL.md` 2026-09-01.

## Contraintes actées

- Clés API : OpenAI, Anthropic, OpenRouter (Mistral via OpenRouter).
- Budget : pas de plafond a priori ; alerte AWS à 55 USD/mois ; chaque poste documenté.
- Rythme : pas de calendrier, les « semaines » du brief sont des unités d'effort.
