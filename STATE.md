# STATE

> Instantané de l'état du projet. Mis à jour à chaque session de travail.
> Historique détaillé dans `JOURNAL.md`, décisions dans `docs/adr/`.

## Phase en cours

**Phase 1 — Squelette de production : construite, en cours de finition** (démarrée le
2026-09-03, branche `phase-1`, 15 commits). PR #2 (docs : phase 5B + clôture phase 0) toujours
ouverte — `phase-1` est branchée dessus, à rebaser sur `main` si le merge est fait en squash.

## Fait en phase 1 (2026-09-03)

- **Couche LLM** (`src/llm_testbench/llm/`, ADR 006) : types neutres, gouvernance des données
  (classes, métadonnées de backend datées, politique TOML par refus par défaut, décision tracée),
  registre `config/llm_backends.toml` (anthropic, openai, openrouter, bedrock, local), table de
  prix datée (Anthropic + OpenAI relevés le 03/09), prompts versionnés Jinja2 strict avec
  empreinte, retry/backoff/gigue, circuit breaker, délai, budget, cache exact et sémantique,
  providers Anthropic (dont Bedrock) et compatible OpenAI sur SDK officiels (`max_retries=0`),
  embeddings, sorties structurées avec réparation bornée, façade `LLMClient`, traces OTel
  (attributs `gen_ai.*` + `llm_testbench.*`), simulateur réseau pour tests et notebooks.
- **Sources et ingestion** (ADR 007) : `Source`/`Evidence`/`Provenance`/`Citation` homogènes,
  parsing (texte, markdown, sections), chunker récursif (baseline phase 3), schéma Postgres
  (documents, chunks, registre d'index, une table de vecteurs HNSW par index), store psycopg
  asynchrone, pipeline idempotent, loader QASPER (Parquet HF, 281 papiers validation),
  `DocumentSource`, réponse citée (`prompts/chat_answer.md`, sentinelle de refus).
- **API** : `/chat` JSON et `/chat/stream` SSE, `/healthz`, `/readyz` (503 avec raison),
  `/sources`, erreurs typées → codes HTTP, CLI d'ingestion (`make ingest-scifact|qasper`).
- **Infra** : Dockerfile multi-arch non-root, chart Helm (probes, HPA, PDB, sécurité,
  ExternalSecret), Tiltfile, Terraform `envs/dev` (VPC, EKS 1.33 + Pod Identity + add-ons
  managés, RDS pg16 pgvector, ECR, S3, Secrets Manager, rôles) validé, lock providers
  3 plateformes, `make infra-*`/`deploy`/`cluster-addons`. Vérifié sur k3d : image poussée,
  pod en marche, readiness 503 « index absent » tant que rien n'est ingéré (voulu).
- **Langfuse v4 sur k3d** (Helm, ClickHouse mono-nœud maison, init headless) : OTLP accepté,
  événements en ClickHouse avec tous nos attributs, coût recalculé par Langfuse
  (0,00187 $ = le nôtre) ; API legacy désactivée en mode `events_only` (guide 07 en cours).
- **Guides infra** `docs/infra/` : README, 00 bootstrap, 01 dev local, 02 réseau, 03 EKS,
  04 RDS, 05 secrets, 06 chart Helm, 08 coûts (07 observabilité en cours).
- **Notebook 1** `01_appel_llm_robuste.ipynb` (39 cellules, exécuté en mode échantillon, CI).
- Tests : 151 hors ligne, 6 sur base (`make test-db`), 2 réseau ; mypy strict ; CI verte
  attendue (deux notebooks en nbmake).

## Reste à faire en phase 1

- Guide 07 (observabilité) ; notebook 2 (du document au chunk indexé, avec la comparaison
  des trois embeddings via `mteb` sur SciFact — nécessite les clés et `sentence-transformers`).
- Exécution complète des notebooks avec clés (`.env`), ingestion SciFact réelle, `/chat` réel.
- Bootstrap AWS et `make infra-up` par Christophe (guides 00 et 03), déploiement EKS.
- Traces, ADR de clôture, debrief, PR `phase-1`.

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
