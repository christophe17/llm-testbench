# PHASE 2 — L'ÉVALUATION (semaines 4–6) ⭐ PHASE CENTRALE

C'est la compétence qui me rend embauchable et celle où la plupart des candidats sont creux.
Trois semaines assumées — mais l'effort va dans la **construction du harness**, pas dans
l'annotation manuelle.

**2.1 Le harness sur jeux publics.** Runners pour BEIR, HotpotQA, SQuAD 2.0, QASPER. Métriques
**séparées retrieval et génération** — c'est le point technique clé et une question d'entretien
fréquente. Retrieval : recall@k, precision@k, MRR, nDCG. Génération, à contexte supposé
parfait : groundedness, pertinence, exactitude des citations, taux de refus correct sur les
non-répondables, taux de refus abusif. Bout en bout : exactitude, latence, coût.

**2.2 Comparaison à la littérature.** Pour chaque jeu, notre score à côté des scores publiés.
Un écart important est un bug, pas un résultat : à traiter comme tel. Premier repère acquis en
phase 1 : le harness doit reproduire les nDCG@10 mesurés via `mteb` sur SciFact
(bge-base-en-v1.5 0,740 ; all-MiniLM-L6-v2 0,645 ; BM25 publié 0,665).

**2.3 LLM-as-judge, fait correctement.** Rubriques explicites, notation discrète, justificatif
avant la note, modèle juge différent du générateur (OpenAI, le générateur étant Anthropic —
ADR 006). **Calibration obligatoire** : j'annote 50 exemples à la main, tu mesures l'accord
(Cohen's kappa). Un juge non calibré est un générateur de nombres rassurants. Neutralise et
documente les biais : position, verbosité, self-preference, format.

**2.4 Non-déterminisme.** N runs, intervalles de confiance par bootstrap. Sans ça, la phase 3
célébrera des +2 % qui n'existent pas.

**2.5 Le corpus maison — un seul corpus, trois usages.** Quelques centaines de documents bruts,
sélectionnés sur **deux critères et deux seulement** : publiés après les cutoffs des modèles
utilisés, et difficiles à parser (colonnes, tableaux, scans, notes de bas de page, structures
irrégulières). **Le thème est indifférent — ne me propose pas un domaine à comprendre,
propose-moi des formats à casser.** Ce corpus sert simultanément à : mesurer la contamination
par comparaison avec les jeux publics, supporter le golden set maison, et fournir les documents
empoisonnés de la phase 7. Propose-moi 3 candidats avec leurs difficultés de format et leur
licence (le repo est public : la licence doit permettre la redistribution, ou le corpus est
téléchargé par script sans être versionné).

**2.6 Le golden set maison — 50 à 80 questions, pas plus.** Son but n'est pas le volume, c'est
de démontrer que je sais construire une évaluation à partir de rien : taxonomie étiquetée
(factuelle, multi-hop, **sans réponse**, ambiguë, piège, temporelle), génération assistée puis
revue humaine intégrale via une CLI que tu me construis, versionnement avec CHANGELOG. C'est
aussi le socle réutilisable si je le branche un jour sur les données d'un client (dans un repo
séparé).

**2.7 Industrialisation.** `make eval` → rapport HTML comparatif, historique des runs en base.
**Garde-fou de régression** : on travaille sur `main` sans PR (ADR 008), donc pas de PR à
bloquer. Deux niveaux à la place : (1) un hook `pre-push` qui lance `make eval-gate` en mode
échantillon et **refuse le push** au-delà du seuil de régression — c'est le seul vrai blocage ;
(2) la même porte dans la CI GitHub, qui passe au rouge sur `main` si le hook a été contourné.
Le notebook doit dire honnêtement la différence avec un merge bloqué en équipe.

Regarde ce que font Ragas, promptfoo et DeepEval — mais **construis le nôtre d'abord**, puis
compare dans le notebook.

**Notebooks** : (1) mesurer un RAG — pourquoi les métriques bout-en-bout cachent le vrai
problème ; (2) LLM-as-judge : le calibrer ou ne pas s'en servir ; (3) contamination — pourquoi
tes bons scores mentent peut-être ; (4) construire un golden set à partir de rien, en petit.

**Livrable clé** : la **baseline chiffrée** du système de la phase 1, comparée à la
littérature.
