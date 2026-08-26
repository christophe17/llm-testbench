# ADR 001 — Jeux de données du banc d'essai et jeu de démarrage

- **Date** : 2026-08-26
- **Statut** : accepté

## Contexte

Le brief liste ~15 jeux candidats, issus de la mémoire d'un modèle. Une vérification web
complète (nom, version, licence, taille, mode de récupération — détail dans
`docs/datasets-verification-2026-08-26.md`) a confirmé la plupart des entrées et invalidé
ou nuancé certaines. Contrainte outillage : `datasets` ≥ 3 n'exécute plus les scripts de
chargement HF — seuls les dépôts Parquet natifs se chargent proprement.

## Décisions

1. **Jeu de référence phase 0 : BEIR/SciFact.** 5 183 documents, 300 requêtes test,
   qrels quasi binaires, 4,5 MB, Parquet natif, littérature abondante (BM25
   nDCG@10 ≈ 0,67-0,69). NFCorpus est plus petit en disque mais ses ~134k qrels gradués
   compliquent la validation du harness — SciFact d'abord, NFCorpus et FiQA en phase 2.
2. **Natural Questions retiré.** ~145 GB pour un signal « sans réponse » indirect ;
   SQuAD 2.0 (46 MB, non-réponse explicite) couvre le besoin.
3. **τ-bench remplacé par `sierra-research/tau2-bench`** (τ³) : le dépôt original est
   officiellement déprécié. Conséquence : les chiffres du papier τ-bench 2024 ne sont
   pas comparables aux nôtres (75+ tâches corrigées depuis).
4. **BIRD via Mini-Dev** (500 instances SELECT, 11 bases, versions PostgreSQL fournies) ;
   le jeu complet (33 GB) est exclu. La conversion sqlglot SQLite→Postgres reste un
   livrable pour Spider.
5. **DocVQA via les miroirs HF** (`lmms-lab/DocVQA` pour val/test) : le site officiel
   exige une inscription et présentait un certificat TLS cassé le 2026-08-26. Évaluation
   sur le split validation (réponses test cachées partout).
6. **Licences signalées, pas de redistribution** : ChartQA est en GPL-3.0, FUNSD en
   non-commercial (images jamais redistribuées), la licence DocVQA d'origine est floue,
   et les étiquettes CC des dépôts BEIR sont la revendication de l'empaquetage, pas une
   garantie amont. Aucune donnée publique n'est versionnée dans le dépôt.
7. **Chemins fragiles documentés** : MuSiQue (Google Drive), 2WikiMultihopQA (Dropbox),
   QASPER (branche `refs/convert/parquet` uniquement), Spider (bases SQLite sur Google
   Drive — copie cachée à prévoir), HybridQA et WikiTableQuestions (dépôts HF à scripts
   morts → passer par GitHub). Chaque loader futur devra épingler sa provenance.

## Conséquences

La contamination reste un biais assumé de tous ces jeux (Spider en particulier) : c'est
un objet de mesure de la phase 2, pas un motif d'exclusion. Les harness agentiques
(tau2-bench, BFCL, AgentDojo) ne sont pas des datasets et s'intégreront comme runners
externes en phase 4 — BFCL impose Python 3.10, donc un environnement uv séparé.
