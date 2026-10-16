# ADR 007 — Interface `Source`, ingestion et stockage vectoriel

- **Date** : 2026-09-03
- **Statut** : accepté

## Contexte

Le brief (phase 1) impose une interface `Source` générique dès maintenant — capacités
déclarées, provenance uniforme, citation homogène quelle que soit l'origine — pour que la
phase 4 (SQL, API, données structurées, images) soit un branchement et non un refactor. Il
impose aussi une ingestion « parsing → chunking naïf → embeddings → index pgvector » avec
métadonnées de traçabilité, et un `/chat` à citations obligatoires et refus explicite. La
phase 3 produira **plus d'une centaine d'index** (jeu × chunking × embeddings × paramètres)
sur ce même stockage.

## Options considérées

**Stockage des vecteurs.**

1. **Une table d'embeddings unique** avec une colonne `vector` sans dimension fixée.
   Simple, mais pgvector n'indexe (HNSW) qu'une colonne à dimension fixée : dès qu'on
   compare deux modèles d'embeddings de dimensions différentes, plus d'index.
2. **Un index = une table** `emb_<clé>` à dimension fixée, créée par le code, plus une
   table de registre qui décrit chaque index (jeu, chunker et ses paramètres, modèle
   d'embeddings, dimension, date). **Retenu** : c'est exactement la matrice d'expériences
   de la phase 3, et le *lineage* de chaque chiffre commence ici.
3. Un service vectoriel dédié (Qdrant, Weaviate). Refusé par le brief : Postgres + pgvector.

**Forme de la réponse de `/chat`.**

1. **Sortie structurée** (`{answer, citations, refused}`) : propre, mesurable, mais
   incompatible avec le streaming de tokens (un JSON ne se lit pas à moitié).
2. **Texte avec marqueurs `[n]` et phrase-sentinelle de refus**, parsés après coup, pour
   les deux transports (JSON et SSE). **Retenu** : un seul prompt, un seul parseur, deux
   transports ; le refus reste explicite et mesurable (taux de refus correct/abusif en
   phase 2). Les sorties structurées de l'ADR 006 servent l'extraction (phase 4), pas le
   chat.

**Chunking.** Découpage récursif par séparateurs (paragraphe → ligne → phrase → mot), en
caractères, avec chevauchement. Volontairement naïf : c'est la baseline que la phase 3
doit battre. Réimplémenté (~60 lignes) plutôt qu'importé : le notebook doit pouvoir le
lire en entier.

## Décision

- **Types** (`sources/types.py`) : `Provenance` (clé de source, identifiant de document,
  identifiant de chunk, localisateur lisible, titre, URI, empreinte du texte, date
  d'ingestion), `Evidence` (texte, score, rang, provenance), `Citation` (numéro, libellé
  homogène `[n] source › document › localisateur`, provenance), `SearchQuery` (texte, k,
  filtres, **classe de données** — l'embedding de la question part dehors aussi).
- **Protocole `Source`** : `key`, `kind`, `capabilities` (ensemble déclaré : recherche,
  récupération par identifiant, filtrage… étendu en phase 4 par SQL, API), `search()`,
  `fetch()`. Une seule implémentation en phase 1 : `DocumentSource` sur pgvector.
- **Ingestion** (`ingest/`) : `ParsedDocument` en sections (texte, markdown, et le texte
  intégral QASPER déjà sectionné — pas de PDF en phase 1, ADR de phase 3) ; `Chunk` avec
  identifiant déterministe, empreinte et position ; `RecursiveChunker` ; pipeline qui
  embarque par lots via `LLMClient.embed` (gouvernance et coût inclus) et écrit dans
  Postgres ; idempotence par empreinte de chunk et par index.
- **Schéma Postgres** (`ingest/sql/`) : `documents`, `chunks`, `indexes` (registre), et une
  table `emb_<clé>` par index avec `vector(dim)` et index HNSW cosinus. Création
  idempotente au démarrage.
- **Recherche** : distance cosinus pgvector (`<=>`), score = 1 − distance, `k` borné.
- **Réponse** : prompt versionné `chat_answer` (citations `[n]` obligatoires, sentinelle
  de refus exacte), parseur commun aux deux transports.

## Conséquences

Chaque ligne du futur tableau maître pourra citer sa clé d'index, donc son chunker, son
modèle et sa date. Le coût : une table par index (des dizaines, puis des centaines), ce
qui est le prix d'une matrice d'expériences honnête et que Postgres supporte sans peine.
Les tests de stockage exigent une base ; ils sont marqués `db` et sautés sans
`LLM_TESTBENCH_DATABASE_URL` (CI hors ligne inchangée), exécutés localement sur le k3d.
