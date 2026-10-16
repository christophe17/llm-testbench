# STATE

> Instantané de l'état du projet. Mis à jour à chaque session de travail.
> Historique détaillé dans `JOURNAL.md`, décisions dans `docs/adr/`.

## Phase en cours

**Phase 1 — Squelette de production : construite** (2026-09-03), fusionnée dans `main` le
2026-10-16 avec la PR #2 (PR #3). Depuis, tout se fait sur `main`, sans branche ni PR
(ADR 008). Ce qui reste demande des actions de Christophe (clés, compte AWS), pas du code.

## Fait en phase 1 (2026-09-03)

- **Couche LLM** (`src/llm_testbench/llm/`, ADR 006) : types neutres ; gouvernance des données
  (classes, métadonnées de backend datées, politique TOML par refus par défaut, décision
  tracée) ; registre `config/llm_backends.toml` (anthropic, openai, openrouter, bedrock,
  local) ; table de prix datée ; prompts versionnés Jinja2 strict avec empreinte ;
  retry/backoff/gigue, circuit breaker, délai, budget, cache exact et sémantique ; providers
  Anthropic (dont Bedrock) et compatible OpenAI sur SDK officiels ; embeddings ; sorties
  structurées avec réparation bornée ; façade `LLMClient` ; traces OTel (`gen_ai.*` +
  `llm_testbench.*`) ; simulateurs réseau (transport scripté, embedders jouet et haché).
- **Sources et ingestion** (ADR 007) : `Source`/`Evidence`/`Provenance`/`Citation` homogènes ;
  parsing (texte, markdown, sections) ; chunker récursif (baseline phase 3) ; schéma Postgres
  (documents, chunks, registre d'index, une table de vecteurs HNSW par index) ; store psycopg
  asynchrone ; pipeline idempotent ; loader QASPER ; `DocumentSource` ; réponse citée avec
  sentinelle de refus.
- **API** : `/chat` JSON, `/chat/stream` SSE, `/healthz`, `/readyz` (503 avec raison),
  `/sources`, erreurs typées → HTTP ; CLI d'ingestion.
- **Infra** : Dockerfile, chart Helm (probes, HPA, PDB, sécurité, ExternalSecret), Tilt,
  Terraform `envs/dev` validé (VPC, EKS 1.33 + Pod Identity, RDS pg16 pgvector, ECR, S3,
  secrets, rôles), vérifié sur k3d ; Langfuse v4 sur k3d (OTLP → ClickHouse prouvé, coût
  recalculé identique au nôtre) ; 9 guides `docs/infra/` (README + 00→08).
- **Notebooks** : 1 (appel LLM robuste, 39 cellules) et 2 (document → index, 26 cellules),
  exécutés en mode échantillon, en CI avec Postgres en service.
- **Première mesure** (`data/results/embeddings_scifact.json`, mteb, SciFact nDCG@10) :
  bge-base-en-v1.5 **0,740** (publié 0,7404 — écart nul) ; all-MiniLM-L6-v2 **0,645**
  (< BM25 publié 0,665) ; text-embedding-3-small à produire avec une clé.
- Tests : 155 hors ligne, 6 sur base, 2 réseau ; mypy strict ; hooks pre-commit alignés.

## Reste à faire en phase 1 (actions Christophe)

1. Relire la phase 1 sur `main` (fusionnée le 2026-10-16 sans relecture formelle de la PR #3).
2. `.env` avec les clés (`.env.example`) → `make ingest-scifact`, `make api` ou `tilt up`,
   `make notebooks-full` (section « vrai provider » du notebook 1, vrais embeddings et vraie
   génération du notebook 2), `make bench-embeddings` (ajoute text-embedding-3-small).
3. Guide 00 (bootstrap, 15 min) puis guides 02→05 : `make infra-up`, `make cluster-addons`,
   secrets, `make deploy` — l'API sur EKS (≈ 6 $/jour allumé, `make infra-down` le soir).

## Chiffres actuels

Premier chiffre du banc (protocole mteb, pas encore notre harness). Repères :
BM25 = 0,665 nDCG@10 sur SciFact (papier BEIR) ; embeddings mesurés le 2026-09-03 : bge-base-en-v1.5 0,740 (= publié), all-MiniLM-L6-v2 0,645.

## Décisions en attente d'arbitrage

- **Bootstrap AWS à appliquer par Christophe** en suivant `docs/infra/00-bootstrap.md`
  (compte AWS existant, région eu-west-3, aucun budget ni bucket d'état à ce jour — le
  bucket `eks-foundations-terraform-chris` appartient à un autre projet, on n'y touche pas).
  Les modules `envs/dev` en dépendent.
- Contraintes réelles de gouvernance des données : inconnues à ce jour, mécanisme construit
  en phase 1 avec une politique permissive sur données publiques ; à durcir quand elles se
  préciseront (`docs/decisions.md`, 2026-09-03).
- Candidat d'extension post-phase 10 (noté le 2026-09-01, décision GO/NO-GO **après la
  phase 5**, pas avant) : la boucle de données LLMOps — traces de la phase 5 → échantillonnage
  → étiquetage par le juge calibré (phase 2) → curation → extension du golden set et jeu
  d'entraînement du LoRA (phase 6). Pas de phase « pipeline de données » au sens data
  engineering (Kafka/Spark/dbt/CDC) : hors positionnement, données statiques, doublon de la
  phase 3 — voir `JOURNAL.md` 2026-09-01.

## Amendements inscrits pour les phases à venir (2026-10-15)

Pas de roadmap « pipeline » séparée (`JOURNAL.md` 2026-10-15 et 2026-09-01). Les trois
obligations ajoutées (Dagster livrable nommé en phase 3, file + worker en phase 5, manifeste de
run en 5B et 6) sont intégrées dans `docs/roadmap/phase-3.md`, `phase-5.md`, `phase-5b.md` et
`phase-6.md`.

## Organisation du brief (2026-10-16)

`CLAUDE.md` ne garde que le contrat de travail ; roadmap dans `docs/roadmap/` (un fichier par
phase), registre des décisions dans `docs/decisions.md`. Reprise de session : `STATE.md`,
`JOURNAL.md`, `docs/decisions.md`, 3 derniers ADR, fichier de la phase en cours.

## Contraintes actées

- Clés API : OpenAI, Anthropic, OpenRouter (Mistral via OpenRouter).
- Budget : pas de plafond a priori ; alerte AWS à 55 USD/mois ; chaque poste documenté.
- Rythme : pas de calendrier, les « semaines » du brief sont des unités d'effort.
