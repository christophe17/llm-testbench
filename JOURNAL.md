# JOURNAL

> Historique daté du projet, au fil de l'eau. Une entrée par session de travail significative.
>
> Format d'entrée :
>
> ```
> ## AAAA-MM-JJ — titre court
> **Contexte** : où on en était.
> **Fait** : ce qui a été construit, mesuré ou décidé (avec chiffres quand il y en a).
> **Incidents / surprises** : ce qui a cassé, ce qui a contredit une hypothèse — matière première
> des histoires d'entretien de la phase 8, à consigner sur le moment.
> **Suite** : la prochaine étape concrète.
> ```

## 2026-08-26 — Démarrage : brief, pilotage, vérification des datasets

**Contexte** : reprise du projet à zéro sur la branche `phase-0` (un premier jet de phase 0 existait dans l'historique git ; l'arbre de travail a été volontairement vidé pour repartir du brief).

**Fait** : brief de mission consolidé dans `CLAUDE.md` ; `STATE.md` et `JOURNAL.md` créés ; vérification web (nom exact, version, licence, taille, mode de récupération) de chaque jeu de données du tableau de la section 4 du brief ; réponses aux questions bloquantes obtenues (clés OpenAI/Anthropic/OpenRouter, budget au besoin réel, pas de calendrier).

**Incidents / surprises** : —

**Suite** : validation du sous-ensemble de démarrage et `GO PHASE 0`.

## 2026-08-26 — Phase 0 construite : outillage, loader SciFact, CI, k3d, bootstrap

**Contexte** : `GO PHASE 0` reçu ; arbitrages validés — package `llm_testbench`,
Langfuse + modules cloud reportés en phase 1, bootstrap AWS seul avec budget ~50 €.

**Fait** : outillage complet (uv/ruff/mypy strict/pytest/pre-commit) ; interface de
chargement avec validation d'intégrité référentielle et flag `sampled` porté par les
données ; loader BEIR/SciFact (jointure de 3 dépôts HF Parquet), 13 tests hors ligne +
smoke test réseau ; CI hors ligne (notebook en mode échantillon via nbmake) ; k3d +
Postgres/pgvector vérifié de bout en bout (extension `vector` 0.8.6 active) ; Terraform
bootstrap écrit et validé, non appliqué (compte AWS à créer) ; notebook 0 exécuté dans
les deux modes, contrôle automatique des volumes contre le papier BEIR (5 183 docs,
300 requêtes test — conforme).

**Incidents / surprises** :
- Le kernelspec Jupyter utilisateur `python3` pointait vers un Python 3.10 Homebrew et
  masquait le venv du projet : le notebook passait en `uv run` mais échouait sous
  nbmake (`ModuleNotFoundError`). Correctif : kernel dédié `llm-testbench` enregistré
  par `make setup` et par la CI. Leçon : un notebook « qui marche chez moi » peut
  s'exécuter dans un autre interpréteur que celui qu'on croit.
- k3d local en 5.4.6 (2022, k3s 1.24) refusait l'apiVersion `v1alpha5` ; un cluster
  `llm-testbench` hérité du premier jet traînait encore et `kubectl apply` l'a visé
  sans prévenir. Nettoyage, mise à jour k3d 5.9.0, recréation propre. Leçon : toujours
  vérifier `kubectl config current-context` avant d'appliquer.
- Les ids qrels de SciFact arrivent typés `int` côté HF alors que les ids corpus sont
  des `str` : sans cast systématique, la jointure échoue en silence. C'est exactement
  le genre de bug que la validation d'intégrité à la construction attrape.

**Suite** : relecture de la PR phase 0 ; `make bootstrap-apply` quand le compte AWS
existe ; `GO PHASE 1`.

## 2026-08-26 — Notebook 0 réécrit après retour : « je suis totalement largué »

**Contexte** : première version du notebook 0 rejetée à la relecture — elle exposait le
code de `src/` en supposant acquis tout le vocabulaire IR/LLM (retrieval, qrels, splits,
BM25, nDCG), alors que ce vocabulaire est précisément ce que le projet doit enseigner.

**Fait** : réécriture complète en 38 cellules, progression imposée : problématique
concrète → notions sur un exemple jouet de cinq lignes → données réelles explorées →
seulement ensuite le code de `src/` lu bloc par bloc → tour du banc → expérimentations →
lexique de 22 termes. Chaque terme est défini à sa première apparition. Règle gravée
dans `CLAUDE.md` §8 pour tous les notebooks à venir.

**Incidents / surprises** : le contrat du brief (« lecture guidée du code réel ») était
respecté à la lettre mais raté sur le fond : montrer le vrai code ne dispense pas de
construire les concepts avant. Le bon ordre s'est révélé être : voir les données
d'abord, lire le code ensuite — l'inverse de la v1.

**Suite** : relecture de la nouvelle version du notebook.

## 2026-08-27 — Audit marché et extension de la roadmap (8 → 10 phases)

**Contexte** : question posée — la roadmap est-elle calibrée pour un poste AI Engineer en
France en remote ? Vérification web contre les offres et analyses de recrutement 2026.

**Fait** : cœur de la roadmap confirmé (éval, agents, MCP, observabilité, coût, vLLM —
la « littératie en évaluation » est citée comme premier signal d'embauche). Quatre trous
identifiés et intégrés : GraphRAG (phase 3, derrière flag, candidat assumé au retrait
chiffré), mémoire d'agent (4.10 + notebook 7), voice agents (nouvelle phase 9), browser/
computer use (nouvelle phase 10, optionnelle, GO/NO-GO fin de phase 9). Paysage des
frameworks (LangChain, LlamaIndex, CrewAI, smolagents, OpenAI Agents SDK) et A2A traités
en connaissance dans les notebooks, jamais en implémentation. UI de chat minimale ajoutée
en fin de phase 5. Décisions actées : repo public confirmé ; 2 clients intéressés → les
déploiements clients seront des repos séparés (portfolio « vraie prod »), le banc d'essai
reste le laboratoire — la règle « jamais un second projet » tient, les extensions se
branchent sur le système unique pour réutiliser harness, infra et observabilité.

**Incidents / surprises** : point de vigilance marché — le full remote est minoritaire
sur ce métier en France (même Mistral attend de la présence à Paris) ; viser le remote
réduit l'entonnoir et renforce le poids du différenciateur mesure/portfolio.

**Suite** : inchangée — relecture de la PR phase 0, puis `GO PHASE 1`.

## 2026-08-27 — Révision : les frameworks passent en comparaison chiffrée

**Contexte** : objection soulevée sur la décision du matin (« frameworks en connaissance
seulement ») — une offre qui exige LangGraph/CrewAI passe par un filtre ATS avant
d'atteindre un humain ; un mot-clé absent du CV peut être éliminatoire au tri, même si
l'entretien se gagnerait sur les concepts.

**Fait** : décision révisée. Phase 4.1 : le même agent de référence porté sur smolagents,
OpenAI Agents SDK et CrewAI, mesuré sur le même harness (exactitude, tokens, latence,
lignes de code, ~1 jour par framework) — les ports sont des livrables de benchmark,
`src/` garde une seule implémentation de production (maison + LangGraph). Phase 3 :
notre pipeline comparé à LlamaIndex out-of-the-box sur le même jeu BEIR (pattern
« le nôtre d'abord, puis la comparaison », déjà acté pour Ragas/promptfoo en phase 2).
A2A reste en discussion. Bénéfice attendu : mots-clés CV honnêtement gagnés + un
comparatif chiffré de frameworks que quasi personne ne publie.

**Incidents / surprises** : —

**Suite** : inchangée — relecture de la PR phase 0, puis `GO PHASE 1`.

## 2026-08-31 — Amendement : phase 5B « Le pont », ML classique contre LLM

**Contexte** : demande d'une phase courte après la phase 5 pour mesurer, avec le harness
existant, l'arbitrage ML classique / LLM / hybride — le livrable que personne n'apporte en
entretien. Conflit apparent avec la règle §6 « pas de prédiction ».

**Fait** : phase 5B rédigée et insérée entre 5 et 6 dans `CLAUDE.md` (numérotation
conservée, « B » = insérée après coup) ; règle §6 reformulée : exception nommée, unique,
trois verrous (aucune autre tâche de prédiction, pas de chasse au score, module `classic/`
jamais exposé par l'API). ADR 005 avec vérification web des jeux candidats. Trois
corrections apportées à l'énoncé initial : (1) le bras « GBM de référence » se dédouble en
texte-ignoré et texte-en-n-grams — la littérature (Shi et al. 2021) montre que l'hybride
classique (AUC 0,968) bat l'hybride à embeddings LLM (0,926), donc sans ce bras le tableau
flatterait le LLM ; (2) TabLLM n'est comparable que pour son zéro-coup, son few-shot est du
fine-tuning ; (3) l'attente « écart qualité faible » sur le texte ne tiendra probablement
pas sur 77 intentions fines — déclarée avant mesure, publiée telle quelle.

**Incidents / surprises** : le site d'origine d'EMSCAD (Université de l'Égée) est mort — il
répond une page d'hébergement générique ; la licence d'origine du jeu tabulaire recommandé
n'est donc plus vérifiable à la source, seule la copie du benchmark (CC BY-NC-SA) l'est.
`PolyAI/banking77` sur HF est encore à script (cassé avec `datasets` ≥ 3), PR Parquet
ouverte depuis août 2025 sans réponse des mainteneurs : prévoir un miroir ou le CSV GitHub.

**Suite** : arbitrage des deux jeux de la phase 5B (non bloquant avant cette phase) ;
inchangé par ailleurs — relecture de la PR phase 0, puis `GO PHASE 1`.

## 2026-08-31 — Jeux de la phase 5B arbitrés

**Contexte** : recommandation de l'ADR 005 soumise.

**Fait** : retenus `fake_job_postings2` (tabulaire à texte libre, EMSCAD via le benchmark
multimodal AutoGluon) et Banking77 (classification de texte, 77 intentions). Substituts
conservés dans l'ADR : `women_clothing_review`, MASSIVE fr-FR. ADR 005 accepté sans réserve.

**Incidents / surprises** : —

**Suite** : inchangée — relecture de la PR phase 0, puis `GO PHASE 1`.

## 2026-09-01 — Question : le pipeline de données est-il l'extension naturelle ?

**Contexte** : question posée en relisant le brief — une phase « data pipeline » serait-elle
la suite logique de la roadmap ?

**Fait** : réponse négative, consignée, pas de modification de la roadmap. Arguments :
(1) la phase 3 est déjà un pipeline de données opéré (Dagster, partitions, idempotence,
lineage, Pandera, réindexation incrémentale) avec une justification propre au banc — la
matrice d'expériences, pas la fraîcheur ; (2) un pipeline au sens data engineering
(Kafka, Spark, dbt, CDC) existe pour des données qui bougent — le banc n'a ni source vivante
ni trafic, ce serait réintroduire la logique « corpus vivant » supprimée par le pivot, cas
typique du « bloc qui flotte » de l'audit de cohérence §6 ; (3) hors positionnement — le
data engineering est un métier voisin, l'audit marché du 27/08 ne l'a pas retenu ;
(4) les vrais pipelines de données auront leur place dans les repos clients séparés.
Deux extensions « données » jugées légitimes : la boucle de données LLMOps (traces →
juge → curation → golden set / jeu LoRA, reliant les phases 2, 5 et 6, sur traces
synthétiques à déclarer comme telles), notée en candidat post-phase 10 dans `STATE.md` ;
et le parsing de documents à l'échelle (Docling / unstructured / marker sur le corpus
maison difficile à parser, impact mesuré sur le retrieval), qui relève du notebook 2 de la
phase 3 plutôt que d'une phase nouvelle. Le mot « pipeline de données » est déjà légitime
dans le README et le CV grâce à la phase 3 : à formuler ainsi en phase 8.

**Incidents / surprises** : —

**Suite** : inchangée — relecture de la PR phase 0, puis `GO PHASE 1`.

## 2026-09-03 — Clôture de la phase 0 : notebook relu, environnement local réparé

**Contexte** : notebook 0 relu en entier (version pédagogique réécrite le 26/08) ; PR #1
mergée sur `main` depuis le 27/08 ; amendements docs (phase 5B, journal du 01/09) encore
non commités.

**Fait** : vérification locale complète avant clôture — ruff, mypy strict, 13 tests hors
ligne, notebook 0 exécuté en mode échantillon par nbmake — tout vert après réparation de
l'environnement (ci-dessous). Phase 0 déclarée terminée, debrief livré. Le protocole
s'arrête là jusqu'à `GO PHASE 1`.

**Incidents / surprises** : le dépôt a été déplacé de `~/Sites/` vers `~/Roadmaps/`. Les
scripts console du venv (`.venv/bin/pytest`, `mypy`), le kernel Jupyter `llm-testbench` et le
hook pre-commit portaient encore l'ancien chemin absolu (shebang / `kernel.json` /
`INSTALL_PYTHON`). Symptômes trompeurs : `uv sync --frozen` répondait « Audited 141
packages » (rien à faire), ruff et mypy passaient, mais `uv run pytest` échouait sur
`ModuleNotFoundError: llm_testbench` et `--nbmake` inconnu — parce que le `pytest` qui
s'exécutait était celui de conda base (8.4.1, sur PATH), pas celui du venv (9.1.1).
Diagnostic décisif : `head -1 .venv/bin/pytest`. Correctif : `uv sync --reinstall`,
réenregistrement du kernel (`make setup`), `pre-commit install`. Leçon, même famille que
l'incident kernelspec du 26/08 : un outil qui « passe » ne prouve pas qu'il tourne dans
l'interpréteur qu'on croit, et `uv sync` ne vérifie pas les shebangs. Durcissement :
le Makefile invoque désormais `python -m pytest` (passe par le lien `python` du venv,
insensible au déplacement) au lieu du script console `pytest`. Reste un chemin périmé
purement cosmétique dans une sortie versionnée du notebook 0 (racine affichée) — sera
rafraîchi à la prochaine exécution complète.

**Suite** : PR docs pour les amendements non commités ; `GO PHASE 1`.
