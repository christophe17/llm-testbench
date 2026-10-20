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

## 2026-09-03 — Phase 1 : squelette de production construit en une session

**Contexte** : `GO PHASE 1` reçu le matin après la clôture de la phase 0. Plan validé avec
quatre arbitrages (OpenRouter en backend de largeur seulement, gouvernance des données dès la
phase 1, guides infra pédagogiques, QASPER + trio d'embeddings).

**Fait** : couche LLM complète (ADR 006), sources/ingestion/pgvector (ADR 007), API JSON + SSE,
image + chart Helm + Tilt vérifiés sur k3d, Terraform `envs/dev` validé, Langfuse v4 sur k3d
avec OTLP fonctionnel, 8 guides infra sur 9, notebook 1 exécuté en CI. 151 tests hors ligne,
6 sur base. Détail dans `STATE.md`.

**Incidents / surprises** :
- **Deux versions d'un même linter se contredisent.** Le hook pre-commit épinglait ruff 0.6.9,
  le projet utilise la version résolue par uv ; une règle de style de tests (PT012) passait chez
  l'un et bloquait chez l'autre. Correctif : les hooks passent par `uv run ruff` ; `make lint`
  couvre aussi les notebooks, comme le hook. Même famille que le venv déplacé du matin : un outil
  « vert » ne prouve rien sur l'outil qui tourne vraiment.
- **`$path` en zsh est `PATH`.** Une boucle `for path in …` a effacé le PATH du shell : « curl :
  command not found ». Vingt minutes de diagnostic pour une variable mal nommée.
- **Les modèles Claude actuels refusent `temperature`.** Vérifié dans la référence API : le
  provider Anthropic ignore `temperature` et `seed` (sinon 400). Le « température 0 pour le
  déterminisme » de la phase 5B se mesurera autrement. Consigné dans le notebook 1.
- **Le chart Langfuse 2.x exige un opérateur ClickHouse** (CRD, trois keepers) : trop lourd pour
  le « strict nécessaire » local. Contournement : ClickHouse mono-nœud en 60 lignes de
  StatefulSet, le chart en mode « ClickHouse externe ». Puis **Langfuse v4 est en mode
  `events_only`** : les endpoints `/api/public/traces` et `/observations` répondent 404 ; les
  spans OTLP sont bien en ClickHouse (`events_core`), avec tous nos attributs, et Langfuse
  recalcule le coût (0,00187 $, identique au nôtre — un contrôle croisé gratuit). Le worker
  démarré avant la fin des migrations avait aussi laissé des erreurs : redémarré.
- **`helm --wait` expire sur une readiness qui refuse** : ce n'est pas un bug, c'est `/readyz`
  qui dit « index absent ». Documenté (guides 01 et 06) plutôt que contourné.
- **Une pipe masque un échec** (`make check | tail` sous `set -e`) : un commit a tenté de partir
  avec mypy rouge, le hook l'a arrêté. `set -o pipefail` désormais dans les enchaînements.
- **Les tests de chunking n'avaient jamais tourné** : chaque `make check` s'arrêtait au lint
  avant pytest. Deux attentes fausses dans les tests, corrigées ; le chunker était juste.

**Suite** : guide 07, notebook 2 (chunking + embeddings mesurés), exécution complète avec clés,
bootstrap et `infra-up` par Christophe, PR phase 1.

## 2026-09-03 — Phase 1 : notebook 2, première mesure, clôture de la construction

**Contexte** : suite de la session ; il restait le guide 07, le notebook 2 et la comparaison
d'embeddings.

**Fait** : guide 07 (Langfuse v4, OTLP prouvé jusqu'à ClickHouse, relecture par l'API v2) ;
module `eval/embeddings_bench.py` (mteb + adaptateur sur `LLMClient.embed`) ; notebook 2
exécuté sur la base locale ; **première mesure du banc** : bge-base-en-v1.5 0,740 nDCG@10 sur
SciFact — **égal au chiffre publié sur sa carte (0,7404)** — et all-MiniLM-L6-v2 0,645,
**sous BM25 (0,665)**. Le modèle de tous les tutoriels perd contre une recherche par mots-clés
sur ce jeu : la raison d'être de la recherche hybride de la phase 3, chiffrée avant même
qu'elle existe. Postgres en service dans la CI pour les tests `db` et le notebook 2.

**Incidents / surprises** :
- **Feature hashing et collisions** : l'embedder « sac de mots hachés » à 32 dimensions rendait
  un cosinus nul entre deux phrases qui partagent trois mots — deux mots tombés dans la même
  case avec des signes opposés. À 256 dimensions le phénomène persiste (0,5 au lieu de 0,75)
  sur cinq mots ; le test vérifie désormais la propriété (commun ≫ disjoint, identique = 1) à
  1 024 dimensions plutôt qu'une valeur. Bonne illustration pour le notebook : un embedding est
  une projection, et une projection perd.
- **Un cache qui ment sur le temps** : mteb met ses résultats en cache ; la première table
  affichait 2 s d'« indexation ». Le module force la ré-évaluation pour que la colonne durée
  soit un temps d'encodage réel (20 s et 120 s sur M1 Pro).
- **Une regex qui n'en était pas une** : un heredoc a doublé un antislash… puis ne l'a pas fait ;
  la vraie cause était la collision ci-dessus. Diagnostiquer en observant (imprimer les
  vecteurs) a coûté moins cher que deviner.
- **Langfuse v4 events_only** (voir l'entrée précédente) : la relecture passe par
  `/api/public/v2/observations` ; consigné dans le guide 07.
- **La CI a attrapé ce que mon poste masquait.** Sur une base neuve, le pool psycopg
  échouait (« vector type not found ») : chaque connexion enregistre le type `vector` à sa
  création, avant que `ensure_schema` ait pu créer l'extension. En local, le job pgvector-init
  de la phase 0 l'avait déjà créée : 6 tests verts, bug invisible. Correctif : le schéma passe
  par une connexion brute dans `open()`, avant le pool ; reproduit sur une base vierge du k3d
  (`CREATE DATABASE ci_fresh`), corrigé, CI verte. Leçon : un environnement de dev qui a de
  l'histoire n'est pas un environnement neuf ; la CI avec un service Postgres jetable, si.
  Première mise en scène de CI verte. Le mypy de la CI avait aussi refusé un `type: ignore`
  que mon poste, avec `mteb` installé, rendait nécessaire — même famille.

**Suite** : PR `phase-1` ; actions Christophe : clés dans `.env`, exécutions complètes,
bootstrap AWS puis `make infra-up` / `make deploy` (guides 00→05) ; puis `GO PHASE 2`.

## 2026-10-15 — Le mot « pipeline » : pas de roadmap séparée, trois amendements

**Contexte** : question posée en regardant l'ensemble du portfolio (le banc d'essai plus
quatre projets voisins spécifiés ou en cours, dont deux sans code) — le « côté pipeline »
des offres AI Engineer est-il couvert, ou faut-il une roadmap dédiée ? Reprise de la
question du 2026-09-01, cette fois avec les projets voisins sur la table.

**Fait** : réponse négative confirmée, et le brief amendé. Analyse : le mot « pipeline »
recouvre quatre choses dans les offres — pipeline RAG (phases 1 et 3), pipeline de données
orchestré (phase 3, Dagster, partitions, lineage, Pandera), pipeline événementiel asynchrone
(file, worker, DLQ) et plateforme d'entraînement (reproductibilité, versionnage, DDP,
export). Les deux derniers sont portés par des projets voisins qui n'ont pas une ligne de
code et dont l'horizon dépasse celui du CDI : le banc ne compte pas dessus. Kafka, dbt et le
streaming restent hors périmètre (data engineering, métier voisin). Trois faiblesses
corrigées par amendement : (1) le bloc Dagster de la phase 3 était une ligne de passage
sans ADR ni notebook, alors que c'est le livrable qui répond au mot-clé — il devient un
livrable nommé avec ADR, ligne du tableau maître et notebook 5 ; (2) le juge asynchrone et
le feedback de la phase 5 n'imposaient aucune forme — ils passent par une vraie file et un
worker, ce qui donne un pipeline événementiel codé dans ce dépôt quoi qu'il arrive
ailleurs ; (3) aucun manifeste de run pour les entraînements de 5B et 6 — exigé désormais,
sans outil supplémentaire. Inscrit dans `CLAUDE.md` (§5 phases 3, 5, 5B, 6 ; §6 ; §8) et
`STATE.md`.

**Incidents / surprises** : l'analyse d'offres du 27/08 qui a motivé l'extension des
frameworks n'est archivée nulle part ; le raisonnement sur le sens du mot « pipeline »
repose sur la connaissance générale des offres 2026, pas sur un corpus relu. À vérifier
contre de vraies offres au moment de la phase 8.

**Suite** : inchangée — PR `phase-1`, actions Christophe (clés, exécutions complètes,
bootstrap AWS), puis `GO PHASE 2`. Les amendements s'appliquent au plan des phases 3, 5,
5B et 6.

## 2026-10-16 — Brief restructuré, tout sur `main`

**Contexte** : `CLAUDE.md` faisait 56 Ko (~15 000 tokens) chargés à chaque session et dans
chaque sous-agent, roadmap des phases 0 à 10 comprise ; les amendements s'empilaient en §8 au
lieu de corriger le texte (exemple : le §1 visait encore le CDI d'AI Engineer, que la décision
PD-8 range en repli). Trois branches ouvertes (`phase-0` fusionnée, `phase-1` et la branche
docs en attente depuis le 2026-09-03).

**Fait** : `CLAUDE.md` réduit au contrat de travail (§1–4, §6, numérotation conservée pour les
renvois du code) ; roadmap dans `docs/roadmap/` (vue d'ensemble + tableau des jeux, un fichier
par phase, amendements intégrés dans le texte) ; §8 déplacé tel quel dans `docs/decisions.md`.
PR #3 fusionnée (elle contenait la #2), branches supprimées en local et sur GitHub ; désormais
tout sur `main` (ADR 008). Phase 2.7 reformulée en conséquence : hook `pre-push` + CI rouge au
lieu d'une PR bloquée.

**Incidents / surprises** : la PR #3 a été fusionnée sans relecture formelle de Christophe —
la relecture de la phase 1 se fait désormais sur `main`. Le passage sans PR retire le seul
mécanisme qui *bloquait* une régression : à présenter honnêtement en entretien (ADR 008).

**Suite** : inchangée — actions Christophe (clés, exécutions complètes, bootstrap AWS), puis
`GO PHASE 2`.

## 2026-10-19 — Notebooks rangés par phase

**Contexte** : `notebooks/` était à plat, numéroté en séquence globale (00 = phase 0, 01 et
02 = phase 1). Le lien notebook → phase ne se lisait nulle part dans le nommage, et la roadmap
réservait déjà des numéros (« notebook 5 » pour Dagster) que seul `STATE.md` rattachait à une
phase.

**Fait** : un sous-dossier par phase, `notebooks/phase-N/NN_slug.ipynb`, fichiers déplacés par
`git mv` sans renommage. Makefile et CI passent le dossier `notebooks/` entier à nbmake : tout
notebook ajouté est exécuté par la CI sans toucher à la liste. Les trois notebooks réexécutés
en mode échantillon (le 2 sur un conteneur pgvector jetable, le cluster k3d étant éteint).

**Incidents / surprises** : les notebooks 1 et 2 cherchaient `.env` dans `Path.cwd().parent`,
c'est-à-dire la racine seulement tant qu'ils vivaient dans `notebooks/`. Un niveau plus bas,
le fichier n'aurait plus été trouvé et la section « vrai provider » se serait désactivée sans
erreur — la CI, en mode échantillon, ne l'aurait jamais vu. Ils s'ancrent désormais sur
`find_repo_root()` comme leurs autres chemins. Leçon : un chemin relatif au répertoire
courant dans un notebook est une dépendance cachée à l'emplacement du fichier.

**Suite** : inchangée — actions Christophe (clés, exécutions complètes, bootstrap AWS), puis
`GO PHASE 2`.

## 2026-10-19 — Reprise : audit du banc, un seul environnement, déploiement OIDC, règle des services AWS

**Contexte** : projet mis de côté un mois. Christophe demande trois choses : valider que le
banc sert la roadmap globale (`~/Roadmaps/program`) et la recherche de missions freelance,
auditer ce qui a été généré, et juger le choix de Kubernetes face à son besoin de monter en
compétence sur AWS sans mauvaise décision d'infra. Le programme a changé le matin même (PD-18 :
sherpapier gelé, ce banc est la preuve pour les missions).

**Fait** : audit livré (`docs/decisions.md`, première ligne du jour) — les deux objectifs
tiennent, EKS confirmé, huit corrections. Puis, sur son feu vert : `prod` retiré du brief ; CV
renvoyé au programme et nombre d'années retiré du §1 ; `docs/aws-competences.md` supprimé ;
doc rot corrigé (README Terraform, index des guides, bandeau du README) ; **ADR 009** ;
**déploiement par GitHub Actions et OIDC** (bootstrap `github.tf`, access entry dans
`envs/dev`, `deploy.yml` sur runner arm64, `make deploy-trigger`, guide 09) ; **URL de la
base composée dans le cluster** par un template External Secrets — le mot de passe RDS ne
traverse plus l'état Terraform ; **règle d'entrée des services AWS** dans `CLAUDE.md` §4 et
ses premières applications dans les phases 3 à 7 ; génération Claude 5.5 par défaut et table
de prix du jour. Vérifié : `terraform validate` sur les deux modules, `helm lint` et rendu de
l'`ExternalSecret` avec les valeurs `database.*`, `make check` (155 tests, mypy strict),
notebooks 1 et 2 réexécutés en mode échantillon sur un pgvector jetable.

**Incidents / surprises** :
- **Une session parallèle rangeait les notebooks** (`notebooks/phase-N/`) pendant l'audit :
  `FileNotFoundError` sur un chemin lu dix minutes plus tôt. Son travail était complet et
  consigné ; commité à part, avant le mien, en isolant dans le Makefile son bloc du mien par
  un patch partiel. Leçon : deux sessions sur un même dépôt, c'est `git status` avant chaque
  écriture, et jamais un commit global.
- **Un script d'édition arrêté par son propre garde-fou** : une ancre recopiée sans ses `**`
  ne correspondait plus ; l'assertion a évité une édition partielle de cinq guides. Le coût
  d'une ancre exacte est inférieur à celui d'un fichier à moitié modifié.
- **Restreindre l'endpoint EKS à une IP et déployer depuis GitHub sont exclusifs** sans runner
  dans le VPC ni mode pull : la correction « hygiène » de l'audit a cédé devant le pipeline,
  et la décision est écrite (ADR 009) plutôt que subie.
- **Haiku 5.5 n'a pas de prix de cache publié** dans la référence relevée : la table le laisse
  absent, et `cost_usd` rend `None` sur un appel en cache — comme prévu. Le tableau de coûts du
  notebook 1 a cassé dessus : la cellule gérait ce `None` pour la colonne « économie » et pas
  pour la colonne « 1 appel (cache) ». Corrigée : elle affiche « inconnu ». La règle « jamais
  une estimation » a tenu jusque dans l'affichage, et le notebook en fait la démonstration.
- **Le code du quota GPU n'est pas vérifiable** hors d'un compte : `STATE.md` fait chercher le
  code par son nom plutôt que de le coder en dur.

**Suite** : actions Christophe (`STATE.md`) — relire les commits du jour, clés, exécutions
complètes, bootstrap (huit ressources), variable GitHub, demande de quota GPU — puis
`GO PHASE 2`.

## 2026-10-20 — Ordre de lecture du banc, demande de quota GPU

**Contexte** : Christophe reprend la phase 1 construite et demande dans quel ordre lire les
fichiers, puis que la liste soit écrite jusqu'à la phase 10, puis que les demandes de quota
GPU de `STATE.md` soient envoyées.

**Fait** : `docs/ordre-de-lecture.md` (16 blocs : phases 0 et 1 au module près, phases 2 à 10
sur les livrables nommés par la roadmap, à compléter à chaque clôture de phase), renvois dans
`README.md` et `STATE.md`. Quota GPU : identité vérifiée (compte 749020018778, utilisateur
`christophe`), les deux quotas G et VT à 0 en eu-west-3, aucune demande en cours, g6.xlarge et
g6.2xlarge offerts dans la région. Demande Spot (`L-3819A6DF`) envoyée à 8 vCPU à 10 h 51 ;
demande On-Demand (`L-DB2E81BA`) envoyée par Christophe à 10 h 54 ; les deux en `CASE_OPENED`.

**Incidents / surprises** :
- **La demande On-Demand (`L-DB2E81BA`) a été refusée par le garde-fou de la session Claude**
  (« transaction réelle »), alors que la demande Spot, strictement de même nature, est passée
  juste après. Pas de relance à l'identique : la commande exacte a été mise dans `STATE.md`
  et Christophe l'a lancée à la main trois minutes plus tard. Leçon : deux appels identiques
  peuvent être jugés différemment par un classificateur ; consigner l'état après chaque
  action réelle, pas à la fin.
- Deux demandes de quota Standard (On-Demand et Spot, 32 vCPU) datées du 2026-09-03 sont en
  `CASE_CLOSED` dans l'historique, un statut qui ne dit pas si elles ont été accordées ;
  vérifié : les deux quotas sont à 32 vCPU, `make infra-up` (guide 03) n'est pas bloqué.

**Suite** : actions Christophe (`STATE.md`) ; puis `GO PHASE 2`.
