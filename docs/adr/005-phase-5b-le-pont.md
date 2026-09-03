# ADR 005 — Phase 5B « Le pont » : mesurer l'arbitrage ML classique / LLM

- **Date** : 2026-08-31
- **Statut** : accepté

## Contexte

Le banc mesure des techniques LLM entre elles ; il ne dit jamais quand un LLM est la
mauvaise réponse face à un modèle classique, alors que c'est la première question posée
en entretien de system design et la décision la plus coûteuse en production. La section 6
du brief interdit la prédiction et la modélisation métier — règle protectrice contre la
dérive vers un second projet, mais qui, lue à la lettre, interdit aussi de mesurer cet
arbitrage. Le brief exige par ailleurs un seul harness et un seul système.

## Options considérées

1. **Ne rien faire** — cohérent avec la règle, mais laisse un trou dans l'argumentaire
   « je choisis une architecture sur preuve » ; l'arbitrage resterait une opinion.
2. **Une phase courte (5B) qui étend le harness** — le modèle classique n'existe que
   comme bras de comparaison ; règle de la section 6 reformulée avec une exception
   nommée et trois verrous. Coût : ~1 semaine, ~20–50 $ d'API avec un modèle « mini »
   (~300 $ avec un modèle frontier — d'où un seul modèle, échantillonnage stratifié du
   test s'il est cher), une dépendance (xgboost + shap, roues arm64 disponibles).
3. **Un repo séparé « ML classique vs LLM »** — viole « jamais un second projet » et
   perdrait l'instrumentation coût/latence et le bootstrap du harness.

## Décision

Option 2. Phase 5B après la phase 5 (elle consomme son instrumentation coût/latence —
elle en est le premier client externe, ce qui teste l'abstraction), avant la phase 6
(qui rejouera son bras LLM en self-hosted). Numérotation conservée : renuméroter 6–10
casserait les références des ADR 001–003, du JOURNAL et de STATE pour un gain nul ; le
« B » signifie « insérée après coup », pas « sous-partie de 5 ».

Deux tâches, une tabulaire à texte libre et une classification de texte, sur jeux
publics à référence publiée. Bras obligatoires : baseline stupide, règle simple, GBM
texte ignoré, **GBM + n-grams TF-IDF** (sans lui l'hybride LLM serait comparé à un homme
de paille — Shi et al. 2021 mesurent sur fake_job_postings : GBM sans texte AUC 0,697,
GBM + n-grams 0,968, GBM + embeddings 0,926), LLM zéro-coup et few-shot en contexte,
hybride embeddings → GBM. Un seul modèle LLM par bras. Axes : qualité avec IC bootstrap,
latence p95, coût/1 000, déterminisme, reproductibilité, auditabilité, défendabilité
(les deux derniers en grille discrète déclarée qualitative + un proxy mesuré chacun).
Livrable : `docs/decision-tree-ml-vs-llm.md`, chaque branche adossée à un chiffre.
Module `src/llm_testbench/classic/`, testé et typé, jamais exposé par l'API ni appelé
par l'agent.

## Jeux de données — vérification du 2026-08-31, arbitrés le même jour

Protocole de la phase 0 (disponibilité, taille, licence, redistribution). Aucune donnée
n'est versionnée dans le dépôt. **Retenus : `fake_job_postings2` et Banking77.** Les
autres colonnes restent comme substituts documentés si un chemin de chargement casse.

**Tabulaire à texte libre** (référence : benchmark multimodal AutoGluon, Shi et al.
2021, NeurIPS D&B ; copies hébergées sur S3 `automl-mm-bench`, HEAD 200 vérifié, sha1
dans le loader d'origine ; licence des copies CC BY-NC-SA) :

| | fake_job_postings2 (EMSCAD) — **recommandé** | women_clothing_review | employee_salaries |
|---|---|---|---|
| Tâche | binaire (fraude, ~5 % positifs), ROC-AUC | régression note 1–5, R² | régression salaire, R² |
| Taille | 12 725 / 3 182, 21 MB | 18 788 / 4 698, 4 MB | 9 228 lignes, 1,3 MB |
| Texte | titre, description, exigences (long, réel) | titre + avis | intitulé de poste (385 valeurs courtes) |
| Licence | copie NC ; site EMSCAD d'origine mort (page d'hébergement générique) ; copie Kaggle non vérifiable sans compte | copie NC ; original Kaggle annoncé CC0 ; miroir HF `Censius-AI` Parquet | **CC0 confirmé** (API OpenML 42125) |
| Références | GBM sans texte 0,697 · + n-grams 0,968 · pre-embedding 0,926 · Text-Net 0,963 · stack 0,964 | sans texte 0,001 · + n-grams 0,654 · pre-embedding 0,642 · stack 0,751 | skrub docs : MinHash + HGB R² 0,911 ± 0,014 |
| Verdict | seul jeu où tabulaire **et** texte portent du signal ; fraude → axes audit/régulateur sensés ; contamination probable (2014) | tabulaire seul ≈ 0 : l'hybride mesure texte contre texte | « texte » de 3 mots ; régression |

Rejeté : `product_sentiment_machine_hack` (tabulaire = une colonne, licence introuvable).
Référence méthodologique du bras zéro-coup : TabLLM (Hegselmann 2023, AISTATS) — son
few-shot est du fine-tuning, **non comparable** à notre few-shot en contexte.

**Classification de texte** :

| | Banking77 — **recommandé** | MASSIVE fr-FR | AG News |
|---|---|---|---|
| Tâche | 77 intentions bancaires, 10 003 / 3 080 | 60 intentions, ~11,5 k / 2 k / 3 k (locale fr-FR) | 4 thèmes, 120 k / 7,6 k |
| Licence | CC BY 4.0 | CC BY 4.0 | « non-commercial research », HF : unknown |
| Chargement | HF `PolyAI/banking77` à script → cassé (`datasets` ≥ 3) ; PR Parquet `refs/pr/6` (2025-08), miroir `gtfintechlab/banking77`, ou CSV GitHub PolyAI | `AmazonScience/massive`, Parquet natif | Parquet natif |
| Références | BERT fine-tuné 93,66 % (83,42 % à 10 ex./intention), USE 92,81 % ; LLM zéro-coup 10–25 pts en dessous | XLM-R base 86,3 %, mT5 87,2 % ; MTEB `MassiveIntentClassification (fr)` : embeddings + linéaire publiés par modèle | n-grams TF-IDF 92,36 % (Zhang 2015) |
| Verdict | littérature LLM-vs-fine-tuné la plus riche ; 77 étiquettes dans le prompt amplifient l'écart de coût et rendent le cache de prompt mesurable | seule tâche francophone du banc ; référence directe pour le bras « embeddings + linéaire » | trop facile, licence floue — rejeté |

## Conséquences

Le README gagne l'argument « quand ne pas utiliser de LLM », chiffré. La section 6
porte une exception explicite ; toute réutilisation du module `classic/` hors 5B est
une violation, pas une extension. Les jeux choisis sont anciens et omniprésents :
contamination mesurée (phase 2), pas ignorée. Attente déclarée avant mesure pour la
tâche texte (écart qualité faible, écart coût de plusieurs ordres de grandeur) — la
littérature sur Banking77 laisse penser qu'elle ne tiendra pas telle quelle sur 77
intentions fines ; ce sera une branche de l'arbre, pas un résultat à maquiller.
À revisiter si la phase 5 ne livre pas un coût par appel réutilisable hors de son
contexte.
