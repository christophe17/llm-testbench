# PHASE 1 — Squelette de production (semaines 2–3)

**Statut : construite** (fusionnée dans `main` le 2026-10-16) ; restent les actions de
Christophe listées dans `STATE.md` (clés, exécutions complètes, bootstrap AWS).

La qualité n'est pas encore le sujet : on construit la structure qu'on mesurera ensuite.

**Couche LLM** : abstraction provider, structured outputs avec validation et réparation,
timeouts, retry/backoff, circuit breaker, budget de tokens, cache exact et sémantique,
streaming SSE annulable. **Gouvernance des données** dès cette phase, comme propriété de la
couche : classe de données portée par chaque requête, registre de backends avec métadonnées
(entité, région, rétention, entraînement, sous-traitants), politique qui refuse par défaut,
décision tracée dans l'audit, appliquée aussi aux embeddings et au juge. Les contraintes
réelles ne sont pas encore connues : politique initiale permissive sur données publiques, à
durcir quand elles se préciseront (ADR 006).

**Abstraction des sources dès maintenant.** Le système interrogera à terme des documents, une
base SQL, des API, des données structurées et des images (phase 4). Interface `Source`
générique — capacités déclarées, métadonnées, provenance uniforme, citation homogène quelle
que soit l'origine — et d'abord le connecteur documentaire. La phase 4 devient un branchement
au lieu d'un refactor (ADR 007).

**Ingestion** : parsing soigné (le parsing fait la moitié de la qualité d'un RAG), chunking
recursive volontairement naïf comme baseline à battre, métadonnées de traçabilité, comparaison
chiffrée d'au moins 3 modèles d'embeddings via MTEB.

**API** : `/chat` avec citations obligatoires et refus explicite quand le contexte ne permet
pas de répondre. Déployé sur le cluster, pas seulement en local.

**Infra** : Langfuse (reporté de la phase 0, ADR 002) et modules AWS. Chaque brique expliquée
dans un guide `docs/infra/`.

**Notebooks** : (1) anatomie d'un appel LLM robuste — ce qui casse en prod et comment on
l'encaisse ; (2) du document au chunk indexé, avec toutes les sorties intermédiaires visibles.

## Arbitrages du plan (2026-09-03)

- Providers : Anthropic natif (+ Bedrock) et compatible OpenAI ; générateur par défaut
  `anthropic/claude-sonnet-5` ; OpenAI second provider et juge de la phase 2 (ADR 006).
- Documents longs : QASPER (texte intégral déjà structuré, CC BY 4.0) ; parsing PDF reporté en
  phase 3, où il sera mesuré.
- Embeddings comparés via `mteb` sur SciFact : OpenAI text-embedding-3-small,
  BAAI/bge-base-en-v1.5 (local), all-MiniLM-L6-v2 (témoin « tutoriel »). Les nDCG@10 obtenus
  sont un repère que le harness de la phase 2 devra reproduire.
- Langfuse par Helm sur k3d (VM Docker à 12 GB).
- Déploiement cloud manuel par `make`, pas de pipeline OIDC.
- psycopg 3 en SQL brut, index HNSW.
