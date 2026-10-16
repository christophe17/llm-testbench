# PHASE 5B — Le pont : ML classique ou LLM, la réponse est un tableau (~1 semaine)

Ajoutée le 2026-08-31 (ADR 005). Le « B » signifie « insérée après coup entre 5 et 6 », pas
« sous-partie de la phase 5 ».

Objet : mesurer, avec le harness existant, l'arbitrage entre un modèle de ML classique, un LLM
et un hybride sur la **même tâche**. C'est l'unique livrable du projet où l'on entraîne un
modèle classique, et il n'existe que comme bras de comparaison : on ne construit pas un système
de prédiction, on chiffre un choix d'architecture. C'est l'exception bornée de `CLAUDE.md` §6.

**Jeux arbitrés (ADR 005)** : tabulaire `fake_job_postings2` (EMSCAD via le benchmark
multimodal AutoGluon, copie CC BY-NC-SA — **jamais redistribuée** ; site d'origine mort,
licence amont invérifiable) et texte **Banking77** (CC BY 4.0, chargement hors script HF).
Substituts documentés si l'un casse : `women_clothing_review`, MASSIVE fr-FR.

**5B.1 Tâche tabulaire à texte libre** (fake_job_postings2). Bras obligatoires, tous mesurés
par le même runner :

- baseline stupide (`DummyClassifier`, stratégies majoritaire et stratifiée) ;
- une règle simple (un seul attribut, un seul seuil — un arbre de profondeur 1) ;
- gradient boosting **texte ignoré** ;
- gradient boosting **texte en n-grams TF-IDF** — l'hybride classique, obligatoire : sans lui
  l'hybride LLM est comparé à un homme de paille (littérature sur fake_job_postings : 0,968
  contre 0,926 pour l'hybride à embeddings) ;
- LLM en zéro-coup sur lignes sérialisées (gabarit de sérialisation en fichier versionné dans
  `prompts/`, sortie structurée validée), puis few-shot en contexte à k fixé (exemples
  stratifiés, identiques pour toutes les lignes, graine fixée) ;
- hybride : embeddings des champs textuels par le provider de la phase 1, injectés comme
  features dans le gradient boosting.

Un seul modèle LLM par bras, choisi pour ce qu'on déploierait vraiment à ce volume ; le modèle
est un paramètre du notebook, pas une dimension du tableau.

**5B.2 Le cas inverse : classification de texte** (Banking77). Baseline stupide · TF-IDF +
modèle linéaire · embeddings + modèle linéaire (le « milieu » : sémantique sans génération) ·
LLM zéro-coup avec la liste des étiquettes dans le prompt · LLM few-shot. Attente déclarée avant
mesure : écart de qualité faible pour un écart de coût de plusieurs ordres de grandeur. Si la
mesure contredit l'attente, c'est le résultat, on le publie.

**5B.3 Axes de mesure, tous dans le tableau :**

- qualité : métrique du jeu (AUC / F1 macro), N runs, intervalle bootstrap — comparée au score
  publié ;
- latence p95 par prédiction et débit en lot ;
- coût pour mille prédictions : entraînement amorti + inférence pour le classique, tokens ×
  tarif via l'instrumentation de la phase 5 pour le LLM ; effet du cache de prompt (la liste
  d'étiquettes et les exemples few-shot sont un préfixe constant) ;
- déterminisme : taux d'accord prédiction à prédiction entre deux exécutions identiques (graine
  fixée pour le classique ; température 0 pour le LLM — le chiffre n'est pas 100 %, c'est le
  point) ;
- reproductibilité : ce qu'il faut épingler pour rejouer le chiffre dans six mois (versions,
  graines, identifiant exact du modèle — un modèle d'API peut changer sans préavis, voir le
  runbook de la phase 5), matérialisé par un **manifeste de run** que le runner écrit à côté
  des résultats — config hachée, graine, révision du jeu de données, versions, identifiant
  exact du modèle, métriques, coût ; **sans manifeste, un chiffre d'entraînement n'entre pas
  dans le tableau** ;
- auditabilité : existence d'une explication **par prédiction** recalculable par un tiers
  (SHAP / coefficients) contre un justificatif généré ; un seul proxy chiffré : stabilité du
  justificatif LLM sur la même entrée rejouée ;
- défendabilité devant un régulateur : grille discrète (0/1/2) à critères explicites, adossée
  aux obligations de transparence de l'AI Act et à l'art. 22 RGPD, déclarée qualitative, reliée
  à `docs/ai-act.md` de la phase 7.

**5B.4 Contamination.** Les jeux tabulaires publics sont anciens et omniprésents sur Kaggle : le
zéro-coup LLM est probablement flatté. Appliquer la mesure de signal de contamination de la
phase 2 et l'écrire à côté du chiffre. Référence de littérature imparfaite et documentée :
TabLLM fait du fine-tuning few-shot, pas du few-shot en contexte — seul son zéro-coup est
comparable à notre bras.

**5B.5 Livrable clé** : `docs/decision-tree-ml-vs-llm.md`, un arbre de décision d'architecture
où **chaque branche cite un chiffre du tableau** — quand une règle suffit, quand le ML classique,
quand l'hybride, quand le LLM (peu de données étiquetées, étiquettes mouvantes, texte long et
rare) — plus le seuil de volume où le coût bascule. L'arbre entre dans le README de la phase 8.

**Garde-fous** : un module `src/llm_testbench/classic/` (modèles classiques, sérialisation de
lignes, features hybrides), testé et typé, **jamais exposé par l'API ni appelé par l'agent** ;
les runners étendent `eval/`. Hyperparamètres par défaut ou recherche bornée et documentée — pas
de chasse au score. Pas de feature store, pas de dérive, pas de réentraînement, pas de matrice
de modèles, pas de seconde tâche.

**Notebook** : « choisir entre un XGBoost et un LLM, la réponse est un tableau » — les sorties
intermédiaires visibles sont la ligne sérialisée, le prompt final, la réponse brute et son
parsing, l'explication SHAP d'une prédiction, et le tableau.
