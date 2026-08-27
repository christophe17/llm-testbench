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
