# Vérification des jeux de données du banc d'essai — 2026-08-26

> Vérification web (sources officielles + Hugging Face) du 26 août 2026. À figer dans un ADR en phase 0 après arbitrage. Les sous-ensembles « starter » sont le plus petit point d'entrée pour itérer vite.

## Synthèse par jeu

| Jeu | Source canonique | Taille utile | Licence vérifiée | Starter | Verdict |
|---|---|---|---|---|---|
| BEIR SciFact | HF `BeIR/scifact` + `BeIR/scifact-qrels` | 5 183 docs, 300 requêtes test, <5 Mo | CC BY 4.0 + ODC-By 1.0 (upstream ; la carte HF « CC BY-SA » est inexacte) | tout | ✅ starter retrieval n°1 |
| BEIR NFCorpus | HF `BeIR/nfcorpus` (+ `-qrels`) | 3 633 docs, 323 requêtes test, 3 Mo | floue upstream (carte HF CC BY-SA non confirmée) | tout | ✅ (usage éval OK, ne pas redistribuer) |
| BEIR FiQA-2018 | HF `BeIR/fiqa` (+ `-qrels`) | 57 638 docs, 648 requêtes test, 28 Mo | floue upstream | test | ✅ idem |
| MTEB | `pip install mteb` (API v2, breaking vs 1.x) | harness, pas un jeu | Apache-2.0 (code) | `SyntecRetrieval` (90 docs, FR), puis `AlloprofRetrieval` | ✅ tâches FR confirmées : MTEB(fra) |
| HotpotQA | HF `hotpotqa/hotpot_qa` | config `distractor`, validation 7 405 q ; 1,27 Go | CC BY-SA 4.0 | 500 premières du dev | ✅ (test sans labels ; beaucoup de questions répondables en 1 hop) |
| MuSiQue | GitHub StonyBrookNLP (Google Drive) ; miroir HF `bdsaglam/musique` | MuSiQue-Ans dev 2 417 q | CC BY 4.0 | dev | ✅ complément dur de HotpotQA ; attention leakage single-hop documenté |
| 2WikiMultihopQA | GitHub Alab-NII (Dropbox, fragile) ; miroir `RUC-NLPIR/FlashRAG_datasets` | dev ~12 576 q | Apache-2.0 | 500 du dev | ✅ via miroir FlashRAG de préférence |
| SQuAD 2.0 | HF `rajpurkar/squad_v2` | validation 11 873 q (~5 900 non répondables), 46 Mo | CC BY-SA 4.0 | validation entière | ✅ starter abstention |
| Natural Questions | HF `google-research-datasets/natural_questions` | **45 Go** en complet ; config `dev` 7 830 q | CC BY-SA 3.0 | config `dev` uniquement, si besoin | ⚠️ optionnel : SQuAD 2.0 donne le même signal d'abstention à 1/1000e du coût |
| QASPER | HF `allenai/qasper` | 1 585 papiers, 5 049 q, 26 Mo ; val 281 papiers / 1 005 q | CC BY 4.0 | validation | ✅ parfait pour le chunking (flag `unanswerable` + spans de preuve) |
| Spider 1.0 | HF `xlangai/spider` (miroir du Yale/Google Drive) | dev 1 034 q / 20 bases SQLite | CC BY-SA 4.0 | dev | ✅ mais gelé depuis 2024 et saturé (~86 % frontier) → sert à valider le harness, pas à discriminer |
| BIRD | bird-bench.github.io ; **Mini-Dev** github `bird-bench/mini_dev` | complet 33,4 Go ❗ ; Mini-Dev SQLite 500 instances SELECT | CC BY-SA 4.0 | Mini-Dev SQLite | ✅ via Mini-Dev ; le champ `evidence` doit être fourni au modèle |
| τ-bench | ⚠️ original déprécié → **tau2-bench (τ³)** github sierra-research | ~220 tâches, 5 domaines ; données minuscules, coût = runtime (agent + user simulator) | MIT | domaine `mock` puis `airline` (k=1, user-sim pas cher) | ✅ sur tau2 uniquement ; Python ≥3.12 + uv (compatible notre stack) |
| BFCL | github gorilla `berkeley-function-call-leaderboard` (`pip install bfcl-eval`) — le miroir HF est périmé | V4 courant, ~4-5 K cas | Apache-2.0 | V1 AST `simple`+`multiple`+`parallel` (800) + `live_irrelevance` | ✅ ; catégorie web_search exige SerpAPI (payant) → l'éviter |
| AgentDojo | github `ethz-spylab/agentdojo` (`pip install agentdojo`) | 97 tâches / 629 injections, 4 suites | MIT | suite `workspace`, attaque `important_instructions` | ✅ |
| HybridQA | HF `wenhu/hybrid_qa` | ~70 K q ; dev ~3,5 K | CC BY 4.0 (carte auteur) | 200 du dev | ✅ ; loader à script → `datasets>=3.0` : passer par `refs/convert/parquet` |
| TAT-QA | HF `next-tat/TAT-QA` (officiel) | 16 552 q, 17 Mo ; dev ~1,6 K | CC BY 4.0 | 150–200 du dev stratifiées par type | ✅ propre ; le scorer doit normaliser scale/% |
| WikiTableQuestions | HF `stanfordnlp/wikitablequestions` | 22 033 q ; validation 2 831 | CC BY-SA 4.0 (repo officiel ; carte HF inexacte) | 200 de la validation | ✅ ; loader à script, même contournement |
| FinQA | github `czyssrs/FinQA` (JSON du repo) | ~8,3 K q ; dev 883 | MIT (repo) | 100–200 du dev | ✅ via GitHub ; miroirs HF lossy (`dreamerdeo/finqa` omet les programmes) |
| DocVQA | RRC ch.17 (inscription + TLS cassé) ; miroir de facto `lmms-lab/DocVQA` → `lmms-lab-encoder/DocVQA` | val 5 350 q | ❗ **non résolue** (pas de licence ouverte officielle ; tag Apache du miroir non autoritatif) | 200 de la validation | ⚠️ arbitrage requis (voir ci-dessous) |
| ChartQA | HF `HuggingFaceM4/ChartQA` | 32,7 K q, 964 Mo ; test-human 1 250 | GPL-3.0 (OK pour de l'éval) | 200 du test-human | ✅ ; métrique = relaxed accuracy (tolérance 5 %) ; séparer human/augmented |
| CORD | HF `naver-clova-ix/cord-v2` (officiel NAVER) | 1 000 reçus (800/100/100), 2,3 Go | CC BY 4.0 | test (100) | ✅ propre ; reçus indonésiens ; GT en JSON imbriqué |
| FUNSD | guillaumejaume.github.io/FUNSD | 199 formulaires | ❌ **non commerciale explicite, redistribution interdite** | — | ❌ retrait recommandé (voir ci-dessous) |

## Problèmes et arbitrages proposés

1. **FUNSD** : licence « non-commercial, research and educational purposes only », pas de droit de redistribution — incompatible avec un repo public de démonstration d'employabilité. **Proposition : retirer.** CORD couvre l'extraction champ par champ ; si un second jeu KIE s'impose plus tard, examiner DocILE ou SROIE (tous deux gated RRC).
2. **DocVQA** : pas de licence ouverte officielle, mur d'inscription RRC, TLS cassé. Le miroir HF `lmms-lab` est le standard de facto (lmms-eval) mais son tag Apache n'est pas autoritatif. **Proposition : garder pour l'éval (pas de redistribution, données hors git, source citée)** — à valider.
3. **τ-bench original déprécié** par ses auteurs → utiliser **tau2-bench (τ³)**.
4. **Natural Questions** : 45 Go pour un signal (abstention) que SQuAD 2.0 fournit en 46 Mo. **Proposition : NQ optionnel** (config `dev` seulement, plus tard si besoin de requêtes réalistes).
5. **Licences CC BY-SA** (Spider, BIRD, HotpotQA, SQuAD 2.0, WTQ, NQ) : copyleft sur les redistributions modifiées → **aucune donnée publique versionnée dans le repo** ; `data/` en `.gitignore`, les loaders téléchargent depuis la source. (Bonne pratique de toute façon.)
6. **Loaders à script HF** (`hybrid_qa`, `wikitablequestions`, `ibm-research/finqa`) cassent avec `datasets>=3.0` : utiliser `revision="refs/convert/parquet"` ou les fichiers upstream. Détail d'implémentation pour les loaders de la phase 0.
7. Les trois benchmarks agents (tau2, BFCL, AgentDojo) **imposent chacun leur propre runner** : le harness de la phase 2 devra les intégrer en *adapters*, pas les réimplémenter.

## Sous-ensemble de démarrage recommandé (le plus petit possible)

| Axe | Starter | Volume |
|---|---|---|
| Retrieval | BEIR SciFact (+ NFCorpus en 2e) | 5 K docs, 300 requêtes |
| Embeddings FR | MTEB `SyntecRetrieval` puis `AlloprofRetrieval` | 90 docs / 2,5 K docs |
| Abstention | SQuAD 2.0 validation | 11,9 K q |
| Multi-hop | HotpotQA distractor dev (500), puis MuSiQue-Ans dev | 500 → 2,4 K q |
| Chunking docs bruts | QASPER validation | 281 papiers, 1 K q |
| Text-to-SQL | Spider dev + BIRD Mini-Dev SQLite | 1 034 + 500 q |
| Agents / outils | BFCL V1-AST + tau2 `mock`→`airline` + AgentDojo `workspace` | 800 cas + ~50 tâches + 1 suite |
| Tableaux | TAT-QA dev (FinQA en 2e) | ~200 q stratifiées |
| Images | ChartQA test-human + CORD test (+ DocVQA val si validé) | 200 + 100 (+ 200) |
