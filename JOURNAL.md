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
