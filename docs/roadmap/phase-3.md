# PHASE 3 — RAG avancé (semaines 7–8)

**Chaque technique est derrière un flag et mesurée sur les jeux publics.** Gain non significatif
→ on retire et on documente pourquoi. Une technique retirée avec preuve chiffrée vaut mieux que
dix techniques empilées.

Ordre de rentabilité constatée :

1. recherche hybride BM25 + dense avec fusion RRF ;
2. re-ranking cross-encoder ;
3. comparaison de 4 stratégies de chunking (recursive, sémantique, parent-document, late
   chunking) sur **documents bruts** avec QASPER — et parsing PDF, reporté de la phase 1 et
   mesuré ici ;
4. contextual retrieval ;
5. transformation de requête (HyDE, multi-query, décomposition multi-hop, routage) ;
6. filtrage par métadonnées ;
7. **GraphRAG** (extraction d'un graphe d'entités du corpus, retrieval par graphe) — en dernier :
   coût d'indexation élevé pour des gains incertains dans la littérature ; c'est le candidat le
   plus sérieux au retrait chiffré, et c'est très bien ainsi.

## Le pipeline d'ingestion opéré — livrable nommé

C'est lui qui répond au mot « pipeline » des offres AI Engineer ; « aller vite dessus » veut
dire ne pas s'y perdre, pas le bâcler.

L'ingestion devient un pipeline orchestré. Sa raison d'être n'est pas la fraîcheur du corpus,
statique sur les jeux publics, mais la **matrice d'expériences** : chaque combinaison jeu de
données × stratégie de chunking × modèle d'embeddings × paramètres de retrieval produit un index
distinct, et il y en aura plus d'une centaine entre les phases 2 et 3.

Ce que tu construis : jobs paramétrés et partitionnés sur ces dimensions, idempotence, cache des
étapes coûteuses (les embeddings se paient), relance de ce qui a changé uniquement, reprise
après échec, **lineage** reliant chaque chiffre du tableau de résultats à l'index et au code qui
l'ont produit, et **validation des données en entrée avec Pandera** (schéma des fichiers de
benchmark, encodage, doublons, champs manquants).

Trois obligations :

- un **ADR orchestrateur** : Dagster contre Airflow contre Prefect ;
- une ligne du tableau maître « **régénération d'une ligne depuis zéro** : durée, coût, part
  servie par le cache » ;
- le notebook (5) ci-dessous, entièrement consacré au pipeline.

**Critère d'acceptation** : je dois pouvoir régénérer n'importe quelle ligne du tableau maître à
partir de zéro, avec une seule commande. C'est ce qui sépare « j'ai fait un RAG » de « j'ai
opéré un RAG ».

**Sur le petit corpus maison de la phase 2**, démontre en plus le cas vivant : ajout, mise à
jour et suppression de documents, détection de changement, réindexation incrémentale sans tout
reconstruire.

## Livrables

**Livrable clé** : tableau « technique → gain qualité avec intervalle de confiance → coût
latence p95 → coût € », plus l'écart à la littérature.

**Notebooks** : (1) pourquoi le hybrid search sauve les acronymes et le jargon ; (2) le duel des
stratégies de chunking sur documents bruts ; (3) transformation de requête : quand ça aide,
quand ça coûte pour rien ; (4) notre pipeline contre **LlamaIndex** out-of-the-box sur le même
jeu BEIR — où le framework fait gagner du temps, où il plafonne, chiffré (le nôtre d'abord, puis
la comparaison ; le port LlamaIndex vit dans le matériel de benchmark, pas dans `src/`) ; (5) la
matrice d'expériences : régénérer cent index sans tout recalculer — partitions, taux de cache,
backfill, reprise après échec et lineage visibles en sortie.
