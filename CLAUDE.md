# BRIEF DE MISSION — llm-testbench

Ce fichier est le contrat de travail, chargé à chaque session. Il ne contient que ce qui sert
à chaque tour : qui je suis, comment on travaille, le protocole, la stack, les règles.
Le reste est ailleurs et se lit **au moment où il sert** :

| Fichier | Contenu | Quand le lire |
|---|---|---|
| `docs/roadmap/README.md` | vue d'ensemble des phases, calendrier, tableau des jeux de données | au début de chaque phase |
| `docs/roadmap/phase-N.md` | l'énoncé de la phase N, amendements intégrés | au début de la phase N, et à chaque reprise en cours de phase |
| `docs/decisions.md` | registre daté des décisions prises en cours de route, avec renvoi aux ADR | à chaque reprise de session |
| `STATE.md` · `JOURNAL.md` · `docs/adr/` | état courant, historique daté, décisions structurantes | à chaque reprise de session |

Quand une décision modifie le brief, **on corrige le texte concerné** (ici ou dans le fichier
de phase) **et** on ajoute une ligne datée à `docs/decisions.md`. Jamais un amendement qui
contredit un texte resté en place.

---

## 1. Qui je suis et ce que je veux

Développeur, 20 ans d'expérience. Web depuis 2006, puis DevOps, puis Machine Learning classique
(XGBoost, SVM, PCA, régressions), puis Deep Learning (transformers, CNN, diffusion), puis MLOps.
Tout appris sur le tas, en freelance.

**Cible.** La stratégie de carrière est tenue hors de ce dépôt, dans
`~/Roadmaps/program/docs/01-career-strategy.md` (décision PD-8) ; la Suisse (banque, pharma,
assurance) y est une contrainte. Ce banc sert un positionnement : *AI Engineer qui sait mettre
en prod et qui mesure*. Le CDI d'AI Engineer en startup / scale-up en France est un repli du
programme, pas sa cible. Mon avantage n'est pas le deep learning, c'est ma capacité à opérer,
observer et chiffrer un système. La preuve de production du programme est
`~/Project/sherpapier` (PD-11) ; ce dépôt est le laboratoire et la référence pédagogique.
Aucune certification (PD-9).

**Ce que je maîtrise déjà très bien** : Kubernetes, Terraform, CI/CD, Docker, observabilité
classique, architecture de services, SQL, Python. Génère l'infra directement au niveau
production — mais **explique-la** (voir §2.D) : je sais la lire, je veux quand même reboucler
sur chaque choix AWS.

**Ce que je viens apprendre, et c'est l'objectif premier du projet** : la technique LLM en
production. Vector stores, chunking, retrieval hybride, re-ranking, évaluation, agents
multi-sources, text-to-SQL, MCP, observabilité LLM, quantization et inférence self-hosted,
sécurité.

### Nature du livrable : un banc d'essai, pas une démo produit

**Décision structurante, ne la remets pas en cause.** Le repo public est un **banc d'essai
technique chiffré** : chaque technique implémentée est mesurée sur des **jeux de données
publics à vérité de référence déjà annotée**, et comparée aux scores publiés dans la
littérature.

Raison principale, et elle est pédagogique : les scores de référence me donnent un repère
objectif. Si mon BM25 sort très en dessous de la littérature, mon implémentation est fausse et
je le sais le jour même. Sur un corpus maison, je n'ai aucun repère et je peux passer trois
semaines à optimiser un système bancal sans m'en apercevoir.

Conséquence directe : **je n'ai à devenir expert d'aucun domaine métier.** L'annotation
manuelle massive est remplacée par des jeux de données publics, plus un petit golden set maison
de 50 à 80 questions dont le seul but est de démontrer que je maîtrise la méthode de
construction d'une évaluation à partir de rien.

Le système reste **déployable et opéré** pour de vrai — API, cluster, observabilité, coûts. Ce
n'est pas un notebook géant. Mais son argument de vente est la mesure, pas le cas d'usage.

**Conséquence à assumer : il n'y a ni utilisateurs ni trafic réel.** Tout ce qui suppose de la
production — A/B testing en ligne, canary, drift, feedback — sera démontré sur un **générateur
de trafic synthétique** rejouant les requêtes des jeux publics selon des profils de charge
configurables. C'est une limite réelle du dispositif : elle doit être écrite noir sur blanc
dans le README, jamais maquillée.

**Repo public, sans contenu client.** Des déploiements clients éventuels vivent dans des repos
séparés ; rien d'un client n'entre ici.

---

## 2. Comment on travaille — LE POINT LE PLUS IMPORTANT

**J'apprends en lisant du code expliqué, pas en écrivant du code.** Tu écris 100 % du code. Mon
travail est de lire, comprendre, questionner, arbitrer, et lancer des expériences en changeant
des paramètres.

Pour chaque phase, deux livrables couplés.

### A. Le code de production, dans `src/`

Du vrai code, testé, typé, déployable.

### B. Un notebook pédagogique, dans `notebooks/`

**Contrat strict — respecte-le à la lettre :**

1. **Le notebook n'implémente RIEN.** Il `import` depuis `src/` et exécute le code réel du
   projet. Si tu réécris une version simplifiée dans le notebook, tu as échoué : je dois
   apprendre le code qui tourne, pas un jouet parallèle.
2. Pour montrer le code, utilise `inspect.getsource()` sur les fonctions et classes réelles, ou
   affiche des extraits de fichiers avec leur chemin, puis explique bloc par bloc.
3. Structure imposée :
   - **Le problème** : ce qu'on essaie de résoudre, pourquoi la solution naïve ne suffit pas.
   - **Les options** : 2 ou 3 approches possibles, pourquoi celle-là.
   - **Lecture guidée du code réel** de `src/`, commenté quand c'est subtil.
   - **Exécution** avec les **sorties intermédiaires visibles** : le chunk retourné, le prompt
     final envoyé, la requête SQL générée, la trace, la réponse brute. Je veux voir ce qui se
     passe, pas seulement le résultat.
   - **Les pièges** : ce qui casse en vrai, ce que les tutoriels ne disent pas.
   - **Expérimentations guidées** : 2 ou 3 cellules de configuration en haut que je peux
     modifier pour relancer et observer l'effet, sans écrire de code.
   - **Les chiffres** : impact mesuré sur la qualité, la latence, le coût — et **comparaison
     aux scores publiés** quand le jeu de données en a.
   - **Questions d'entretien** : 4 à 6 questions avec les réponses attendues en cellule
     repliée.
   - **Ce qu'on n'a pas fait, et pourquoi**.
4. **Le notebook doit s'exécuter de bout en bout.** `nbmake` dans la CI : un notebook cassé
   casse le build. Un benchmark complet à chaque commit coûte trop cher : mode échantillon
   piloté par `LLM_TESTBENCH_SAMPLE=1` — la CI, hors ligne et sans secret, vérifie que tout
   s'exécute sur un extrait minuscule ; les chiffres publiés viennent d'exécutions complètes
   lancées à la main et archivées (ADR 003).
5. Prose en **français**, identifiants et code en anglais. Maximum ~40 cellules, sinon découpe.
6. **Niveau débutant sur les notions LLM/IR.** Problématique d'abord, chaque terme défini à sa
   première apparition, exemple jouet avant toute abstraction, progression pas à pas, lexique
   final. Ne jamais supposer le vocabulaire retrieval/évaluation acquis (le DevOps/K8s/SQL, si).

### C. Règles de conversation

- **Explique avant de coder.** Pour toute décision non triviale : 2 options et ton arbitrage,
  en dix lignes, avant d'écrire.
- **Contredis-moi.** Si je demande une mauvaise idée, dis-le.
- Pas de flatterie, pas de récapitulatif de politesse.
- Si un choix m'engage (jeu de données, provider, coût), **pose la question et attends**.

### D. L'infra est expliquée aussi

Guides markdown dans `docs/infra/`, même structure que les notebooks (problème, options,
lecture guidée du vrai code, exécution avec sorties attendues, pièges, questions d'entretien,
non-fait), exécutés par moi en CLI. Vocabulaire K8s/Terraform acquis ; chaque choix AWS et
chaque piège explicités. Pas de notebook infra (identifiants et cluster requis, incompatible
avec la CI hors ligne).

---

## 3. Protocole de phase

Tu ne travailles **qu'une phase à la fois**, et seulement quand j'écris `GO PHASE N`.

1. **Plan** — relis `docs/roadmap/phase-N.md`, fais l'audit de cohérence (§6), puis : ce que tu
   vas construire, les décisions ouvertes. Une page maximum, puis tu attends mon feu vert.
2. **Code** — tests d'abord quand c'est possible, puis implémentation, puis infra.
3. **Notebook** — selon le contrat ci-dessus.
4. **Mesure** — tu lances l'évaluation et tu produis les chiffres. À partir de la phase 3,
   **une phase sans chiffre n'est pas terminée**.
5. **Traces** — `JOURNAL.md`, ADR dans `docs/adr/`, `STATE.md`, `docs/decisions.md`.
6. **Debrief** — en 10 lignes : ce qui est fait, ce que je dois lire en priorité, où je me
   ferai piéger en entretien, ce qui reste faible dans notre implémentation.

**Tout se fait sur `main`** (ADR 008) : pas de branche de phase, pas de PR. Des commits petits
et bien décrits, poussés quand la CI locale passe ; la CI GitHub tourne sur chaque push. Le
récit d'une phase, qui allait dans la description de PR, va dans son entrée de clôture de
`JOURNAL.md`.

### Reprise de session

À chaque nouvelle session, avant de répondre : `STATE.md`, les dernières entrées de
`JOURNAL.md`, `docs/decisions.md`, les 3 derniers ADR, et `docs/roadmap/phase-N.md` pour la
phase en cours.

---

## 4. Stack et infra — décisions figées

- Python 3.12, `uv`, ruff, mypy strict, pytest, pre-commit. Package : `llm_testbench`.
- FastAPI + Pydantic v2, async, streaming SSE.
- PostgreSQL + pgvector comme base vectorielle (psycopg 3 en SQL brut, index HNSW).
- Abstraction multi-provider LLM dès le premier appel, deux implémentations : Anthropic natif
  (sert aussi Bedrock) et compatible OpenAI (OpenAI, OpenRouter, Mistral, puis vLLM/Ollama).
  Modèle = chaîne `backend/modèle`. **OpenRouter est un backend de largeur, jamais le chemin
  unique** (ADR 006).
- **Gouvernance des données, propriété de la couche LLM** : classe de données sur chaque
  requête, registre de backends avec métadonnées de gouvernance, politique qui refuse par
  défaut, décision tracée ; s'applique aussi aux embeddings et au juge (ADR 006).
- **Prompts en fichiers versionnés**, jamais en dur.
- Langfuse self-hosted, OpenTelemetry avec conventions sémantiques GenAI.

### Infra : niveau production

- **Dev local** : `k3d` + Tilt. Pas le Kubernetes de Docker Desktop. Machine **macOS Apple
  Silicon** — signale toute image sans build `arm64` plutôt que de me faire subir de
  l'émulation.
- **Cloud : AWS**, `eu-west-3`. EKS, ECR, RDS Postgres avec pgvector, S3, Bedrock comme
  provider parmi d'autres. Terraform, état distant chiffré, environnements `dev` et `prod`.
- **Coût** : le cluster ne tourne pas 24/7. `make infra-up` / `make infra-down`, pas de poste
  dormant (attention à NAT Gateway), coût mensuel estimé documenté par module. Pas de plafond
  de budget a priori, mais chaque poste est estimé avant engagement.
- Helm, External Secrets + AWS Secrets Manager, HPA, probes, PDB, ressources dimensionnées.
- Observabilité par Helm : Prometheus, Grafana, collecteur OTel, Langfuse. Dashboards versionnés
  en JSON. En local, seulement le strict nécessaire.
- **GPU en phase 6 uniquement**, découplé du cloud principal (module dédié vers un fournisseur
  spécialisé, éphémère, destruction évidente).
- **Portabilité** : le code applicatif reste agnostique du cloud, le spécifique AWS vit dans
  `infra/`.
- L'infra ne doit pas devenir le sujet. Tu la génères vite et bien, je la relis, on avance.

### Structure du repo

```
.
├── CLAUDE.md · STATE.md · JOURNAL.md · Makefile
├── src/llm_testbench/
│   ├── app/          # API, service
│   ├── llm/          # abstraction provider, retries, cache, structured output, gouvernance
│   ├── sources/      # interface Source générique + connecteurs (docs, SQL, API, images)
│   ├── ingest/       # parsing, chunking, embeddings, indexation
│   ├── retrieval/    # recherche, hybrid, reranking
│   ├── generation/   # chaînes, assemblage de contexte
│   ├── agents/       # orchestration, outils, garde-fous
│   ├── eval/         # harness, métriques, juges, runners de benchmarks
│   ├── classic/      # phase 5B uniquement : modèles classiques comme bras de comparaison
│   └── obs/          # instrumentation, coût, traces
├── prompts/          # prompts versionnés
├── data/             # jeux publics (cache) + golden set maison versionné
├── notebooks/        # un ou plusieurs par phase
├── infra/            # terraform, helm, k8s
├── docs/             # roadmap/, adr/, infra/, decisions.md
└── tests/
```

---

## 5. La roadmap

Dans `docs/roadmap/` : un `README.md` de vue d'ensemble et un fichier par phase (0 à 10, plus
5B). **Un seul système, qui grossit à chaque phase. Jamais un second projet.** Les « semaines »
sont des unités d'effort relatif, pas des échéances.

---

## 6. Règles de qualité et anti-patterns

**Toujours :** tests avant implémentation quand c'est possible, avec appels réseau mockés pour
que la suite tourne hors ligne · un ADR par décision structurante (contexte, options, décision,
conséquences) · chiffres avant/après à partir de la phase 3 · prompts en fichiers versionnés ·
une technique sans gain est retirée et documentée · un manifeste de run par entraînement
(phases 5B et 6).

**Audit de cohérence, à chaque début de phase.** Ce projet a pivoté en cours de conception :
d'un produit bâti sur un corpus métier vers un banc d'essai sur jeux publics. Certaines parties
de la roadmap peuvent encore porter des justifications héritées de l'ancienne logique — corpus
vivant, fraîcheur des données, expertise de domaine, démonstration produit, utilisateurs réels.
**Avant de commencer une phase, relis-en l'énoncé et demande-toi si chaque bloc a encore une
raison d'être dans la logique actuelle.** Si un bloc flotte, signale-le et propose soit de le
supprimer, soit de le reformuler sur une justification valide — ne le code pas mécaniquement
parce qu'il est écrit. Signale-moi aussi toute contradiction entre deux sections du brief.

**Jamais :** pas de version simplifiée du code dans les notebooks · pas de certification · pas
de reimplémentation d'un transformer from scratch · pas de fine-tuning avant la phase 6 · pas de
second projet · pas d'empilement de frameworks pour faire joli. Les frameworks tiers
(LlamaIndex, smolagents, OpenAI Agents SDK, CrewAI) n'entrent que comme **ports de
comparaison chiffrée** dans le matériel de benchmark ; `src/` garde une seule implémentation.

**Et spécifiquement pour ce projet :** le sujet est le retrieval, les agents, la mesure et
l'exploitation. Ne me propose jamais d'élargir le périmètre vers de la prédiction, du scoring
ou de la modélisation métier **comme livrable** : aucun modèle prédictif n'est construit pour
sa valeur métier, aucune tâche de prédiction n'est ajoutée pour elle-même. **Unique exception,
nommée et bornée — la phase 5B** : des modèles classiques y sont entraînés uniquement comme
bras de comparaison d'un arbitrage d'architecture, sur un jeu public à référence publiée,
mesurés par le harness commun. Trois verrous : (1) aucune autre tâche de prédiction, dans
aucune autre phase, sans amendement explicite du brief ; (2) hyperparamètres par défaut ou
recherche bornée et documentée — un bras de comparaison honnête, pas un modèle optimisé ;
(3) le code classique vit dans `src/` testé et typé, mais n'est jamais exposé par l'API ni
appelé par l'agent. Toute proposition qui réutilise ce module hors 5B est à traiter comme une
violation de cette règle, pas comme une extension naturelle.
