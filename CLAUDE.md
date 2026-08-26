# BRIEF DE MISSION — lis tout avant d'écrire la moindre ligne

> Contrat de travail du projet. À chaque nouvelle session : relire ce fichier, `STATE.md`, `JOURNAL.md` et les 3 derniers ADR avant de répondre.

---

## 1. Qui je suis et ce que je veux

Développeur, 20 ans d'expérience. Web depuis 2006, puis DevOps, puis Machine Learning classique (XGBoost, SVM, PCA, régressions), puis Deep Learning (transformers, CNN, diffusion), puis MLOps. Tout appris sur le tas, en freelance.

Je vise un **CDI d'AI Engineer en startup / scale-up en France**, positionnement : *AI Engineer qui sait mettre en prod et qui mesure*. Mon avantage sur les autres candidats n'est pas le deep learning, c'est ma capacité à opérer, observer et chiffrer un système.

**Ce que je maîtrise déjà très bien** : Kubernetes, Terraform, CI/CD, Docker, observabilité classique, architecture de services, SQL, Python. Ne me fais pas perdre de temps là-dessus — génère l'infra directement au niveau production, je saurai la lire et la critiquer.

**Ce que je viens apprendre, et c'est l'objectif premier du projet** : la technique LLM en production. Vector stores, chunking, retrieval hybride, re-ranking, évaluation, agents multi-sources, text-to-SQL, MCP, observabilité LLM, quantization et inférence self-hosted, sécurité.

### Nature du livrable : un banc d'essai, pas une démo produit

**Décision structurante, ne la remets pas en cause.** Le repo public est un **banc d'essai technique chiffré** : chaque technique implémentée est mesurée sur des **jeux de données publics à vérité de référence déjà annotée**, et comparée aux scores publiés dans la littérature.

Raison principale, et elle est pédagogique : les scores de référence me donnent un repère objectif. Si mon BM25 sort très en dessous de la littérature, mon implémentation est fausse et je le sais le jour même. Sur un corpus maison, je n'ai aucun repère et je peux passer trois semaines à optimiser un système bancal sans m'en apercevoir.

Conséquence directe : **je n'ai à devenir expert d'aucun domaine métier.** L'annotation manuelle massive est remplacée par des jeux de données publics, plus un petit golden set maison de 50 à 80 questions dont le seul but est de démontrer que je maîtrise la méthode de construction d'une évaluation à partir de rien.

Le système reste **déployable et opéré** pour de vrai — API, cluster, observabilité, coûts. Ce n'est pas un notebook géant. Mais son argument de vente est la mesure, pas le cas d'usage.

---

## 2. Comment on travaille — LE POINT LE PLUS IMPORTANT

**J'apprends en lisant du code expliqué, pas en écrivant du code.** Tu écris 100 % du code. Mon travail est de lire, comprendre, questionner, arbitrer, et lancer des expériences en changeant des paramètres.

Pour chaque phase, deux livrables couplés.

### A. Le code de production, dans `src/`

Du vrai code, testé, typé, déployable.

### B. Un notebook pédagogique, dans `notebooks/`

**Contrat strict — respecte-le à la lettre :**

1. **Le notebook n'implémente RIEN.** Il `import` depuis `src/` et exécute le code réel du projet. Si tu réécris une version simplifiée dans le notebook, tu as échoué : je dois apprendre le code qui tourne, pas un jouet parallèle.
2. Pour montrer le code, utilise `inspect.getsource()` sur les fonctions et classes réelles, ou affiche des extraits de fichiers avec leur chemin, puis explique bloc par bloc.
3. Structure imposée :
   - **Le problème** : ce qu'on essaie de résoudre, pourquoi la solution naïve ne suffit pas.
   - **Les options** : 2 ou 3 approches possibles, pourquoi celle-là.
   - **Lecture guidée du code réel** de `src/`, commenté quand c'est subtil.
   - **Exécution** avec les **sorties intermédiaires visibles** : le chunk retourné, le prompt final envoyé, la requête SQL générée, la trace, la réponse brute. Je veux voir ce qui se passe, pas seulement le résultat.
   - **Les pièges** : ce qui casse en vrai, ce que les tutoriels ne disent pas.
   - **Expérimentations guidées** : 2 ou 3 cellules de configuration en haut que je peux modifier pour relancer et observer l'effet, sans écrire de code.
   - **Les chiffres** : impact mesuré sur la qualité, la latence, le coût — et **comparaison aux scores publiés** quand le jeu de données en a.
   - **Questions d'entretien** : 4 à 6 questions avec les réponses attendues en cellule repliée.
   - **Ce qu'on n'a pas fait, et pourquoi**.
4. **Le notebook doit s'exécuter de bout en bout.** `nbmake` dans la CI : un notebook cassé casse le build.
5. Prose en **français**, identifiants et code en anglais. Maximum ~40 cellules, sinon découpe.

### C. Règles de conversation

- **Explique avant de coder.** Pour toute décision non triviale : 2 options et ton arbitrage, en dix lignes, avant d'écrire.
- **Contredis-moi.** Si je demande une mauvaise idée, dis-le.
- Pas de flatterie, pas de récapitulatif de politesse.
- Si un choix m'engage (jeu de données, provider, coût), **pose la question et attends**.

---

## 3. Protocole de phase

Tu ne travailles **qu'une phase à la fois**, et seulement quand j'écris `GO PHASE N`.

1. **Plan** — ce que tu vas construire, les décisions ouvertes. Une page maximum, puis tu attends mon feu vert.
2. **Code** — tests d'abord quand c'est possible, puis implémentation, puis infra.
3. **Notebook** — selon le contrat ci-dessus.
4. **Mesure** — tu lances l'évaluation et tu produis les chiffres. À partir de la phase 3, **une phase sans chiffre n'est pas terminée**.
5. **Traces** — `JOURNAL.md`, ADR dans `docs/adr/`, `STATE.md`.
6. **Debrief** — en 10 lignes : ce qui est fait, ce que je dois lire en priorité, où je me ferai piéger en entretien, ce qui reste faible dans notre implémentation.

Une phase = une branche = une PR avec une description sérieuse.

### Reprise de session

`CLAUDE.md` (ce brief + décisions figées), `STATE.md` (phase en cours, chiffres actuels, questions ouvertes), `JOURNAL.md` (historique daté). **À chaque nouvelle session, relis les trois et les 3 derniers ADR avant de répondre.**

---

## 4. Stack, données et infra

### Décisions figées (stack)

- Python 3.12, `uv`, ruff, mypy strict, pytest, pre-commit.
- FastAPI + Pydantic v2, async, streaming SSE.
- PostgreSQL + pgvector comme base vectorielle.
- Abstraction multi-provider LLM dès le premier appel (OpenAI ↔ Anthropic ↔ Mistral ↔ modèle local).
- **Prompts en fichiers versionnés**, jamais en dur, dès la phase 1.
- Langfuse self-hosted, OpenTelemetry avec conventions sémantiques GenAI.

### Jeux de données du banc d'essai

À valider en phase 0 — disponibilité et licence vérifiées, substituts proposés si besoin, petits jeux privilégiés pour itérer vite.

| Usage | Candidats | Ce que le jeu fournit |
|---|---|---|
| Retrieval | **BEIR** (commencer par SciFact, NFCorpus, FiQA) | corpus + requêtes + jugements de pertinence |
| Modèles d'embeddings | **MTEB**, tâches francophones si disponibles | protocole de comparaison standardisé |
| Multi-hop | **HotpotQA**, **MuSiQue**, 2WikiMultihopQA | questions + passages de preuve |
| Questions sans réponse / refus | **SQuAD 2.0**, sous-ensembles non répondables de NQ | libellé explicite du « pas de réponse » |
| Chunking sur **documents bruts** | **QASPER** (articles complets, spans de preuve) | documents entiers, pas des passages pré-découpés |
| Text-to-SQL | **Spider**, **BIRD** | **les bases de données elles-mêmes** + requête de référence ; vérité = résultat d'exécution |
| API métier, agents multi-tours | **τ-bench** | environnement complet : outils API + base + documents de règles + utilisateur simulé |
| Appels d'outils, granularité fine | **BFCL** | exactitude des arguments, appels parallèles, cas « ne rien appeler » |
| Tableaux et raisonnement numérique | **HybridQA**, **TAT-QA**, WikiTableQuestions, FinQA | croisement texte + tableau, réponses annotées |
| Séries temporelles | **synthétique, généré par nos soins** | vérité calculée par pandas à la génération : zéro annotation, pièges contrôlés (valeurs manquantes, fuseaux, chevauchements, révisions de valeurs passées) |
| Images : QA sur documents et graphiques | **DocVQA**, **ChartQA** | questions annotées sur documents scannés et graphiques |
| Images : extraction structurée champ par champ | **CORD**, **FUNSD** | chaque champ étiqueté → exactitude par champ mesurable |
| Injection de prompt en contexte agentique | **AgentDojo** | environnements outillés + tâches d'injection |

**Notes de mise en œuvre.** Spider et BIRD sont en SQLite : prévois la conversion vers Postgres (sqlglot), c'est du vrai travail et un bon notebook. BIRD est volumineux et volontairement sale — commence par un sous-ensemble. DocVQA et ChartQA impliquent un modèle multimodal, donc un coût : échantillonne. Pour les séries temporelles, le générateur de jeu de test fait partie du livrable au même titre que le code applicatif : versionné, testé, avec graine fixée.

**La contamination est un sujet à traiter, pas à ignorer** : ces jeux sont probablement dans les données d'entraînement des modèles, donc les scores sont flattés. Construire une mesure de signal de contamination et un petit jeu « frais » de comparaison. Savoir en parler est un signal de séniorité en entretien.

### Infra : niveau production dès la phase 1

- **Dev local** : `k3d` + Tilt pour le hot-reload. Pas le Kubernetes de Docker Desktop. Machine **macOS Apple Silicon** — signaler toute image sans build `arm64` plutôt que de subir de l'émulation.
- **Cloud : AWS**, `eu-west-3`. EKS, ECR, RDS Postgres avec pgvector, S3, Bedrock comme provider parmi d'autres. Terraform, état distant chiffré, environnements `dev` et `prod`.
- **Coût** : le cluster ne tourne pas 24/7. `make infra-up` / `make infra-down`, pas de poste dormant (attention à NAT Gateway), coût mensuel estimé documenté par module.
- Helm, External Secrets + AWS Secrets Manager, HPA, probes, PDB, ressources dimensionnées.
- Observabilité par Helm : Prometheus, Grafana, collecteur OTel, Langfuse. Dashboards versionnés en JSON. En local, seulement le strict nécessaire.
- **GPU en phase 6 uniquement**, découplé du cloud principal (les quotas GPU sur compte AWS personnel sont lents et chers) : module dédié vers un fournisseur spécialisé, éphémère, destruction évidente. ADR sur ce découplage.
- **Portabilité** : le code applicatif reste agnostique du cloud, le spécifique AWS vit dans `infra/`.
- L'infra ne doit pas devenir le sujet. Générée vite et bien, relue, on avance.

### Structure du repo

```
.
├── CLAUDE.md · STATE.md · JOURNAL.md · Makefile
├── src/
│   ├── app/          # API, service
│   ├── llm/          # abstraction provider, retries, cache, structured output
│   ├── sources/      # interface Source générique + connecteurs (docs, SQL, API, images)
│   ├── ingest/       # parsing, chunking, embeddings, indexation
│   ├── retrieval/    # recherche, hybrid, reranking
│   ├── generation/   # chaînes, assemblage de contexte
│   ├── agents/       # orchestration, outils, garde-fous
│   ├── eval/         # harness, métriques, juges, runners de benchmarks
│   └── obs/          # instrumentation, coût, traces
├── prompts/          # prompts versionnés
├── data/             # jeux publics (cache) + golden set maison versionné
├── notebooks/        # un ou deux par phase
├── infra/            # terraform, helm, k8s
├── docs/adr/
└── tests/
```

---

## 5. La roadmap — 8 phases, 16 semaines

Calendrier : 0 (s1) · 1 (s2–3) · 2 (s4–6) · 3 (s7–8) · **4 (s9–11)** · 5 (s12–13) · 6 (s14–15) · 7+8 (s16).

Un seul système, qui grossit à chaque phase. Jamais un second projet.

### PHASE 0 — Fondations (semaine 1)

Repo, outillage, CI (lint, typecheck, tests, exécution des notebooks), infra Terraform + Helm, cluster local, Postgres/pgvector, Langfuse.

Avant de commencer : questions bloquantes (clés API disponibles, budget mensuel accepté, temps hebdomadaire réel). Puis vérification de la disponibilité, la taille et la licence de chaque jeu de données du tableau ci-dessus, proposition du sous-ensemble de démarrage le plus petit possible, et construction des loaders correspondants dans `src/eval/`.

**Notebook 0** : visite guidée de l'architecture cible et de ce que chaque module fera. Plus : à quoi ressemble chaque jeu de données, ce qu'il mesure, ce qu'il ne mesure pas.

### PHASE 1 — Squelette de production (semaines 2–3)

La qualité n'est pas encore le sujet : on construit la structure qu'on mesurera ensuite.

**Couche LLM** : abstraction provider, structured outputs avec validation et réparation, timeouts, retry/backoff, circuit breaker, budget de tokens, cache exact et sémantique, streaming SSE annulable.

**Abstraction des sources dès maintenant.** Le système interrogera à terme des documents, une base SQL, des API, des données structurées et des images (phase 4). Interface `Source` générique — capacités déclarées, métadonnées, provenance uniforme, citation homogène quelle que soit l'origine — et d'abord le connecteur documentaire. La phase 4 devient un branchement au lieu d'un refactor.

**Ingestion** : parsing soigné (le parsing fait la moitié de la qualité d'un RAG), chunking recursive volontairement naïf comme baseline à battre, métadonnées de traçabilité, comparaison chiffrée d'au moins 3 modèles d'embeddings via MTEB.

**API** : `/chat` avec citations obligatoires et refus explicite quand le contexte ne permet pas de répondre. Déployé sur le cluster, pas seulement en local.

**Notebooks** : (1) anatomie d'un appel LLM robuste — ce qui casse en prod et comment on l'encaisse ; (2) du document au chunk indexé, avec toutes les sorties intermédiaires visibles.

### PHASE 2 — L'ÉVALUATION (semaines 4–6) ⭐ PHASE CENTRALE

C'est la compétence qui rend embauchable et celle où la plupart des candidats sont creux. Trois semaines assumées — mais l'effort va dans la **construction du harness**, pas dans l'annotation manuelle.

**2.1 Le harness sur jeux publics.** Runners pour BEIR, HotpotQA, SQuAD 2.0, QASPER. Métriques **séparées retrieval et génération** — c'est le point technique clé et une question d'entretien fréquente. Retrieval : recall@k, precision@k, MRR, nDCG. Génération, à contexte supposé parfait : groundedness, pertinence, exactitude des citations, taux de refus correct sur les non-répondables, taux de refus abusif. Bout en bout : exactitude, latence, coût.

**2.2 Comparaison à la littérature.** Pour chaque jeu, affiche systématiquement notre score à côté des scores publiés. Un écart important est un bug, pas un résultat : traite-le comme tel.

**2.3 LLM-as-judge, fait correctement.** Rubriques explicites, notation discrète, justificatif avant la note, modèle juge différent du générateur. **Calibration obligatoire** : 50 exemples annotés à la main par moi, mesure de l'accord (Cohen's kappa). Un juge non calibré est un générateur de nombres rassurants. Neutraliser et documenter les biais : position, verbosité, self-preference, format.

**2.4 Non-déterminisme.** N runs, intervalles de confiance par bootstrap. Sans ça, la phase 3 célébrera des +2 % qui n'existent pas.

**2.5 Contamination.** Mesurer les signaux de contamination sur les jeux utilisés. Construire un petit jeu « frais » à partir de documents postérieurs aux cutoffs des modèles et comparer les écarts. Documenter honnêtement ce que ça implique sur nos chiffres.

**2.6 Le golden set maison — 50 à 80 questions, pas plus.** Son but n'est pas le volume, c'est de démontrer la méthode de construction d'une évaluation à partir de rien : taxonomie étiquetée (factuelle, multi-hop, **sans réponse**, ambiguë, piège, temporelle), génération assistée puis revue humaine intégrale via une CLI, versionnement avec CHANGELOG. Corpus support : quelques centaines de documents bruts, choisis pour leurs difficultés de format plutôt que pour leur thème. Socle réutilisable pour des données client.

**2.7 Industrialisation.** `make eval` → rapport HTML comparatif, historique des runs en base, GitHub Action qui **bloque la PR** sur régression au-delà d'un seuil.

Regarder ce que font Ragas, promptfoo et DeepEval — mais **construire le nôtre d'abord**, puis comparer dans le notebook.

**Notebooks** : (1) mesurer un RAG — pourquoi les métriques bout-en-bout cachent le vrai problème ; (2) LLM-as-judge : le calibrer ou ne pas s'en servir ; (3) contamination — pourquoi tes bons scores mentent peut-être ; (4) construire un golden set à partir de rien, en petit.

**Livrable clé** : la **baseline chiffrée** du système de la phase 1, comparée à la littérature.

### PHASE 3 — RAG avancé (semaines 7–8)

**Chaque technique est derrière un flag et mesurée sur les jeux publics.** Gain non significatif → on retire et on documente pourquoi. Une technique retirée avec preuve chiffrée vaut mieux que dix techniques empilées.

Ordre de rentabilité constatée : recherche hybride BM25 + dense avec fusion RRF · re-ranking cross-encoder · comparaison de 4 stratégies de chunking (recursive, sémantique, parent-document, late chunking) sur **documents bruts** avec QASPER · contextual retrieval · transformation de requête (HyDE, multi-query, décomposition multi-hop, routage) · filtrage par métadonnées.

**Le pipeline d'ingestion devient un vrai pipeline opéré** : orchestration avec **Dagster** (ou Airflow — ADR), jobs idempotents, réindexation incrémentale sur détection de changement, suppression et versions de documents, reprise après échec, **validation des données en entrée avec Pandera**. C'est ce qui sépare « j'ai fait un RAG » de « j'ai opéré un RAG », directement relié à l'expérience DevOps : aller vite dessus.

**Livrable clé** : tableau « technique → gain qualité avec intervalle de confiance → coût latence p95 → coût € », plus l'écart à la littérature.

**Notebooks** : (1) pourquoi le hybrid search sauve les acronymes et le jargon ; (2) le duel des stratégies de chunking sur documents bruts ; (3) transformation de requête : quand ça aide, quand ça coûte pour rien.

### PHASE 4 — Agents multi-sources (semaines 9–11) ⭐ À ÉGALITÉ AVEC LE RAG

Terrain d'ingénierie principal, segment qui se commoditise le moins vite. Ce n'est pas un appendice du RAG.

**4.1 Socle d'orchestration.** D'abord une **machine à états maison**, puis la même chose avec LangGraph, avec un bilan honnête de ce que le framework apporte et masque. Schémas d'outils, validation Pydantic stricte, erreurs d'outil renvoyées de façon exploitable. Garde-fous : budget d'étapes et de tokens, détection de boucle, timeout global, dégradation gracieuse vers une réponse partielle honnête. Parallélisation des appels indépendants.

**4.2 SQL — le bloc le plus difficile, mesuré sur Spider et BIRD.** Catalogue de schéma et **retrieval sur le schéma**. Pipeline de sûreté avant exécution : parsing (sqlglot), allowlist de tables et colonnes, interdiction DDL/DML, `LIMIT` forcé, `EXPLAIN` préalable, timeout, rôle Postgres en lecture seule, row-level security. Boucle de correction sur erreur SQL, avec budget. Pièges : jointures plausibles mais fausses, résultat vide interprété comme « il n'y en a pas », agrégations et `NULL`, dates et fuseaux. **Règle absolue : le modèle ne recalcule jamais un chiffre, il restitue le résultat de la requête.** Métrique : exactitude d'exécution.

**4.3 API métier.** Outils dérivés d'une spec OpenAPI. Pagination, rate limits, idempotence, retries. Séparation stricte lecture / écriture avec **confirmation humaine obligatoire sur les effets de bord**. Propagation de l'identité utilisateur jusqu'à l'API.

**4.4 Données structurées et séries temporelles.** Jamais un gros tableau en texte brut : outils d'agrégation déterministes, ou exécution de code en bac à sable. L'arithmétique est faite par du code, jamais par le modèle.

**4.5 Images et documents non textuels** — mesuré sur DocVQA et ChartQA. Extraction **structurée** avec schéma Pydantic imposé. Exactitude champ par champ.

**4.6 Routage entre sources.** Comparer un routeur explicite et un agent qui décide seul, et **mesurer les deux**. Questions hybrides et sources contradictoires : politique de priorité explicite ou signalement du conflit, jamais un choix silencieux.

**4.7 Sécurité des outils.** Injection indirecte via les **données renvoyées par un outil**. Benchmark **AgentDojo**. Séparation instructions / données, allowlist d'outils par contexte, sandboxing, permissions propagées, journal d'audit. Fabriquer les attaques, montrer qu'elles marchent, corriger, retester, rechiffrer.

**4.8 Serveur MCP et composition.** Exposer nos outils via MCP, puis consommer **plusieurs serveurs** : découverte dynamique, gouvernance des permissions, comportement en cas de serveur indisponible ou hostile.

**4.9 Évaluation étendue** — mesurée sur BFCL et τ-bench. Trajectoires (outils appelés, ordre, arguments, étapes, coût par tâche réussie), exactitude d'exécution SQL, exactitude par champ, matrice de confusion du routage, fidélité des chiffres cités. **Étendre le harness de la phase 2, pas un second harness.**

**Point de séniorité obligatoire** : implémenter délibérément un cas où l'agent est **la mauvaise réponse** — une requête déterministe fait mieux, plus vite, moins cher — le mesurer, le documenter.

**Notebooks** : (1) un agent sans framework, la mécanique à nu ; (2) text-to-SQL, du schéma à la requête sûre ; (3) outils, API et effets de bord ; (4) données structurées et images — extraire sans halluciner ; (5) le routage multi-sources et les sources contradictoires ; (6) évaluer un agent : trajectoires, exécution, extraction.

### PHASE 5 — LLMOps : observabilité, coût, exploitation (semaines 12–13) ⭐ ARME PRINCIPALE

Traçabilité OTel/GenAI + Langfuse : trace complète requête → routage → retrieval → reranking → outils → génération, avec durée, tokens et coût par span. Coût par requête, par utilisateur, par fonctionnalité. TTFT et p50/p95/p99 par étape. Budgets, alertes, kill switch sur dérive de coût. Registre de versions de prompts avec rollback à chaud. A/B testing de prompts derrière feature flag avec analyse statistique. Qualité en production : échantillonnage vers un juge asynchrone, boucle de feedback, détection de drift. Déploiement canary et shadow pour un changement de prompt ou de modèle.

**Runbooks obligatoires** : le provider est indisponible · la qualité s'est dégradée sans changement de code · les coûts ont triplé dans la nuit.

**Notebooks** : (1) anatomie d'une trace et d'où viennent les millisecondes ; (2) le modèle de coût, du token au prix par utilisateur ; (3) détecter une régression de qualité en production sans labels.

### PHASE 6 — Inférence et modèles ouverts (semaines 14–15)

vLLM : continuous batching, PagedAttention, KV cache — comprendre **pourquoi** c'est rapide. Quantization AWQ / GPTQ / FP8 avec **impact qualité mesuré par notre harness**. Modèle économique : throughput vs latence, sizing GPU, coût par million de tokens self-host vs API, **seuil de bascule en volume**. Déploiement GPU sur Kubernetes, autoscaling, cold start. Embeddings et reranker self-hosted. LoRA/QLoRA sur un cas justifié, évalué contre la baseline prompt-only — **et documenter les cas où le fine-tuning n'était pas la bonne réponse, chiffres à l'appui**.

Module Terraform GPU éphémère, destruction évidente.

**Note stratégique** : cible Suisse à moyen terme (banque, pharma, assurance) → résidence des données et on-premise. Cette phase a une valeur supérieure à la moyenne — ne pas la sacrifier en cas de retard. Au moins un modèle ouvert européen en plus des classiques.

**Notebooks** : (1) ce que vLLM fait vraiment sous le capot ; (2) le vrai coût qualité de la quantization ; (3) self-host vs API, le calcul complet.

### PHASE 7 — Sécurité résiduelle et conformité (semaine 16, partagée avec la phase 8)

OWASP LLM Top 10 sur l'archi complète, injection indirecte par **document** empoisonné, exfiltration via les citations, filtrage de sortie, PII (Presidio), red teaming automatisé (garak, promptfoo redteam) dans la CI. Puis `docs/ai-act.md` : classification de risque EU AI Act, obligations de documentation et de journalisation, minimisation RGPD.

### PHASE 8 — Packaging (semaine 16, commencé dès la semaine 4)

**README du banc d'essai** : ce que le projet mesure → l'architecture (un schéma) → **le tableau maître des résultats** avec écart à la littérature, coût et latence → les décisions et arbitrages → ce qui a cassé → ce que je ferais différemment à l'échelle 100×.

Deux posts techniques tirés du JOURNAL. Une contribution open source ciblée. CV en trois blocs. Préparation d'entretien : system design IA chronométré, trois histoires d'incident situation-action-résultat chiffré, argumentaire build vs buy sur trois briques.

---

## 6. Règles de qualité et anti-patterns

**Toujours :** tests avant implémentation quand c'est possible, avec appels réseau mockés pour que la suite tourne hors ligne · un ADR par décision structurante (contexte, options, décision, conséquences) · chiffres avant/après à partir de la phase 3 · prompts en fichiers versionnés · une technique sans gain est retirée et documentée.

**Jamais :** pas de version simplifiée du code dans les notebooks · pas de certification · pas de réimplémentation d'un transformer from scratch · pas de fine-tuning avant la phase 6 · pas de second projet · pas d'empilement de frameworks pour faire joli.

**Et spécifiquement pour ce projet :** ne jamais proposer d'élargir le périmètre vers de la prédiction, du scoring ou de la modélisation métier. Le sujet est le retrieval, les agents, la mesure et l'exploitation.

---

## Décisions figées (au fil de l'eau)

> Une ligne par décision arbitrée en conversation. Le détail va dans un ADR quand la décision est structurante.

| Date | Décision | ADR |
|---|---|---|
| 2026-08-26 | Providers initiaux : OpenAI + Anthropic. Mistral et Bedrock plus tard ; compte AWS à créer. | — |
| 2026-08-26 | Budget : le minimum nécessaire → défauts économiques partout (petits modèles par défaut, cluster éteint par défaut, dépense AWS différée tant que non indispensable). | — |
| 2026-08-26 | Pas de calendrier imposé : les « semaines » du brief deviennent des jalons ordonnés, pas des dates. | — |
| 2026-08-26 | Repo GitHub public dès le jour 1. | — |
| 2026-08-26 | Machine locale : Apple Silicon M1, 32 Go RAM. | — |
| 2026-08-26 | FUNSD retiré (licence non commerciale, redistribution interdite). DocVQA conservé pour l'éval : données hors git, source citée. | ADR à écrire en phase 0 |
| 2026-08-26 | Aucune donnée publique versionnée dans le repo (licences CC BY-SA) : `data/` en `.gitignore`, les loaders téléchargent et cachent. | idem |
