# Vérification des jeux de données du banc d'essai — 2026-08-26

Vérification web (nom, version, licence, taille, mode de récupération) de chaque entrée du tableau
de la section 4 de `CLAUDE.md`. Contexte outillage : les scripts de chargement Hugging Face sont
dépréciés (`datasets` ≥ 3.x ne les exécute plus) — le critère « se charge proprement aujourd'hui »
signifie : dépôt HF en Parquet natif, ou téléchargement direct versionné.

## Retrieval et embeddings

### BEIR — SciFact, NFCorpus, FiQA-2018
- **Hébergement** : org HF `BeIR` (convertie en Parquet natif ~2026) : `BeIR/scifact` + `BeIR/scifact-qrels` (idem nfcorpus, fiqa). Aussi : zips UKP Darmstadt, paquet `beir` v2.2.0, `ir_datasets`.
- **Licence** : CC BY-SA 4.0 sur les cartes HF — mais le README BEIR précise qu'ils ne garantissent pas les licences amont. À noter dans l'ADR.
- **Tailles** : SciFact 5 183 docs / 1 109 requêtes (300 test) / 1 258 qrels quasi binaires / 4,55 MB. NFCorpus 3 633 docs / 323 requêtes test / ~134k qrels gradués / 3,25 MB. FiQA 57 638 docs / 648 requêtes test / 28 MB.
- **Chargement** : `load_dataset("BeIR/scifact", "corpus")` — script-free. Les qrels sont dans un dépôt séparé : le loader joint 3 dépôts.
- **Problèmes** : aucun bloquant.

### MTEB
- Paquet `mteb` v2.20.2 (2026-08-25), très actif. **API v2 cassante** vs v1 (`mteb.get_benchmark(...)` / `mteb.evaluate(...)`) — les tutoriels anciens sont périmés.
- **Français : oui** — benchmark intégré `MTEB(fra, v1)`, 22 tâches (Ciancone et al. 2024, arXiv:2405.20468).
- Licence code Apache-2.0 ; les datasets de tâches se téléchargent de HF à la demande.

## QA / multi-hop / sans réponse / documents bruts

### HotpotQA — OK
- HF `hotpotqa/hotpot_qa`, configs `distractor` et `fullwiki`, Parquet natif. CC BY-SA 4.0. 90 447 train / 7 405 val, ~1,27 GB. Réponses du test cachées → évaluer sur validation.

### SQuAD 2.0 — OK, le plus propre
- HF `rajpurkar/squad_v2`, Parquet natif. CC BY-SA 4.0. 130 319 train / 11 873 val (~50k non répondables), 46,5 MB. Pas de flag booléen : non répondable = liste `answers.text` vide.

### QASPER — OK avec une réserve
- HF `allenai/qasper` (allenai.org redirige vers HF). CC BY 4.0. 1 585 articles complets / ~5 049 questions / ~26 MB, avec spans de preuve.
- **Piège** : le dépôt principal ne contient que le script `qasper.py` → `load_dataset` échoue avec `datasets` ≥ 3. Charger via `revision="refs/convert/parquet"` (branche vérifiée présente) ou vendorer le JSONL.

### MuSiQue — fragile
- Canonique : GitHub `StonyBrookNLP/musique`, données via **Google Drive** (quotas gdown = panne connue). CC BY 4.0. ~25k questions (variante ans). Miroir HF communautaire `dgslibisey/MuSiQue` (Parquet, provenance non officielle, sans tag de licence, sans split test).

### 2WikiMultihopQA — fragile
- Canonique : GitHub `Alab-NII/2wikimultihop`, données en **zip Dropbox**. Apache-2.0. 192 606 exemples. Non maintenu depuis ~2021. Miroir HF communautaire `framolfese/2WikiMultihopQA` (Parquet, provenance non vérifiée) ; `xanhho/...` à script → cassé.

### Natural Questions — impraticable en entier
- HF `google-research-datasets/natural_questions`. CC BY-SA 3.0. **45 GB téléchargés / ~100 GB générés** pour le config complet ; chaque exemple embarque une page Wikipédia tokenisée. Le « sans réponse » est indirect (moins de 2 annotateurs sur 5 trouvent une réponse — logique à implémenter soi-même). Config `dev` seul praticable. **Décision proposée : SQuAD 2.0 couvre le besoin « sans réponse », NQ retiré du banc.**

## Text-to-SQL et agents

### Spider 1.0 — OK avec contamination assumée
- Questions+SQL : HF `xlangai/spider` (Parquet, 7 000 train / 1 030 dev). **Les bases SQLite ne sont que sur Google Drive** (lien du site Yale) → prévoir une copie cachée. CC BY-SA 4.0. ~200 DBs. Repo d'éval gelé depuis 2020 ; test gated ; contamination d'entraînement massive et documentée (c'est précisément un des sujets du banc). Spider 2.0 = autre benchmark (Snowflake/BigQuery, comptes payants) — hors périmètre.

### BIRD — passer par Mini-Dev
- Complet : 12 751 questions / 95 DBs / **33,4 GB**. Dev 1 534 exemples, zips directs (OSS Alibaba, lent depuis l'UE).
- **Mini-Dev** (`github.com/bird-bench/mini_dev`, HF `birdsql/bird_mini_dev`) : 500 instances SELECT sur 11 DBs (+270 CRUD) — **livre les bases en SQLite, MySQL ET PostgreSQL**, ce qui réduit le travail de conversion sqlglot prévu (reste utile pour Spider). CC BY-SA 4.0. Maintenu.

### τ-bench — DÉPRÉCIÉ, remplacer
- `sierra-research/tau-bench` porte un avertissement explicite de dépréciation. Successeur : **`sierra-research/tau2-bench`** (τ²→τ³ : banking, voice, 75+ corrections de tâches). MIT, Python ≥3.12 <3.14 (compatible). C'est un harness complet (agent LLM + utilisateur simulé LLM → coût double), pas un dataset. Les chiffres publiés du papier τ-bench 2024 ne sont plus comparables après les corrections.

### BFCL — V4, conflit Python
- Monorepo `ShishirPatil/gorilla`, `pip install bfcl-eval` (pas `bfcl`). Apache-2.0. **Pin Python 3.10** → environnement uv séparé obligatoire (seul conflit dur avec notre 3.12). La catégorie web_search V4 exige une clé SerpAPI payante. Scores comparables uniquement à version BFCL identique.

### AgentDojo — OK
- `pip install agentdojo` v0.1.35 (2025-10-27), MIT, Python 3.10–3.12. 4 suites (workspace, Slack, banking, travel), 97 tâches / 27 injections → 629 cas. API pré-1.0, instable par nature.

**Note transverse** : τ²/τ³, BFCL et AgentDojo sont des harness à installer et piloter, pas des datasets chargeables — ils n'entrent pas dans l'interface de loaders de la phase 0 et seront intégrés comme runners externes en phase 4.

## Tableaux et raisonnement numérique

- **TAT-QA** — le meilleur du lot : GitHub `NExTplusplus/TAT-QA` + HF `next-tat/TAT-QA`, JSON brut sans script, CC BY 4.0, 16 552 questions / 17 MB, vérité du test publiée depuis 2024.
- **WikiTableQuestions** — v1.0.2 (2016). Dépôt HF `stanfordnlp/wikitablequestions` à script seul → passer par le GitHub `ppasupat/WikiTableQuestions` (tout en dépôt). Licence : **CC BY-SA 4.0** d'après le dépôt d'origine (la carte HF dit CC BY 4.0 — erreur du miroir).
- **HybridQA** — 69 611 questions, données éclatées sur 3 sources (repo + WikiTables-WithLinks + S3), dépôt HF à script. CC BY 4.0 / MIT. Utilisable mais coûteux à intégrer — optionnel.
- **FinQA** — GitHub `czyssrs/FinQA`, MIT, ~8,3k questions (chiffre papier), non maintenu depuis 2022. **Piège** : bug pré-2022 dans `table_row_to_text` qui gonflait des exactitudes publiées — ne comparer qu'aux chiffres post-correction.

## Images

- **DocVQA (Task 1)** — site officiel RRC : inscription obligatoire **et certificat TLS cassé constaté ce jour**. Passer par les miroirs HF non gated : `pixparse/docvqa-single-page-questions` (complet, 12,4 GB, réponses test absentes) ou `lmms-lab/DocVQA` (val+test, léger). Licence d'origine non standard ; les licences des miroirs (MIT/Apache) sont auto-attribuées — à signaler dans le README. Évaluer sur validation.
- **ChartQA** — HF `ahmed-masry/ChartQA`, Parquet, 32 719 questions / 1,45 GB. **Licence GPL-3.0** (copyleft sur des données, juridiquement bancal — acceptable pour un banc d'essai, à signaler). Séparer splits humain vs augmenté dans les résultats, comme la littérature.
- **CORD v2** — HF `naver-clova-ix/cord-v2`, Parquet, CC BY 4.0, 2,31 GB. **Seuls 1 000 reçus publiés** sur les 11 000+ du papier → comparabilité partielle avec les chiffres publiés.
- **FUNSD** — zip direct sur le site officiel, sans inscription. 199 formulaires (tout petit). **Licence custom non commerciale**, images RVL-CDIP avec responsabilité de licence reportée sur l'utilisateur : ne jamais redistribuer les images dans le repo. Annotations bruitées documentées (FUNSD-r existe).

## Synthèse des drapeaux

| Drapeau | Jeux concernés |
|---|---|
| Chargement HF propre aujourd'hui | BEIR×3, HotpotQA, SQuAD 2.0, TAT-QA, ChartQA, CORD v2, BIRD Mini-Dev, Spider (questions), miroirs DocVQA |
| Chemin de récupération fragile (Drive/Dropbox/script) | MuSiQue, 2WikiMultihopQA, QASPER (branche parquet), HybridQA, WikiTableQuestions, Spider (DBs), FUNSD (zip direct : ok) |
| Licence à signaler | ChartQA (GPL-3.0), FUNSD (non commercial), DocVQA (floue), BEIR (non garantie amont), WTQ (share-alike + carte HF fausse) |
| Volumes | NQ 145 GB (retiré), BIRD complet 33 GB (→ Mini-Dev), DocVQA 12,4 GB (→ échantillon val), le reste < 2,5 GB |
| Remplacement | τ-bench → **tau2-bench (τ³)** ; NQ → SQuAD 2.0 suffit |

## Sous-ensemble de démarrage recommandé (phase 0)

**Un seul loader de référence : BEIR/SciFact.** 5 183 docs, 300 requêtes test, qrels quasi binaires,
4,55 MB, Parquet natif sur HF, scores publiés abondants (nDCG@10 BM25 ≈ 0,67–0,69 dans la littérature
BEIR) — le repère objectif le plus simple à valider. NFCorpus est plus petit en disque (3,25 MB) mais
ses ~134k qrels gradués compliquent la validation du harness ; FiQA est 6× plus gros.
