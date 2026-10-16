# Roadmap — vue d'ensemble

Un seul système, qui grossit à chaque phase. Jamais un second projet. Chaque phase a son
fichier ; il se lit au démarrage de la phase (protocole : `CLAUDE.md` §3). Les « semaines »
sont des unités d'effort relatif, pas des échéances.

| Phase | Fichier | Effort | Objet |
|---|---|---|---|
| 0 | [phase-0.md](phase-0.md) | s1 | Fondations : outillage, CI, cluster local, un loader de référence |
| 1 | [phase-1.md](phase-1.md) | s2–3 | Squelette de production : couche LLM, sources, ingestion, API `/chat` |
| 2 ⭐ | [phase-2.md](phase-2.md) | s4–6 | L'évaluation : harness, juge calibré, contamination, golden set |
| 3 | [phase-3.md](phase-3.md) | s7–8 | RAG avancé, chaque technique mesurée ; matrice d'expériences orchestrée |
| 4 ⭐ | [phase-4.md](phase-4.md) | s9–11 | Agents multi-sources : SQL, API, structuré, images, MCP, mémoire |
| 5 ⭐ | [phase-5.md](phase-5.md) | s12–13 | LLMOps : trafic synthétique, traces, coût, qualité en continu |
| 5B | [phase-5b.md](phase-5b.md) | ~1 sem. | Le pont : ML classique, LLM ou hybride, la réponse est un tableau |
| 6 | [phase-6.md](phase-6.md) | s14–15 | Inférence et modèles ouverts : vLLM, quantization, self-host vs API |
| 7 | [phase-7.md](phase-7.md) | s16 | Sécurité résiduelle et conformité (AI Act, RGPD) |
| 8 | [phase-8.md](phase-8.md) | s16 (dès s4) | Packaging : README, tableau maître, posts, entretiens |
| 9 | [phase-9.md](phase-9.md) | extension | Voice : STT → agent → TTS, time-to-first-audio |
| 10 | [phase-10.md](phase-10.md) | extension optionnelle | Browser / computer use (GO/NO-GO fin de phase 9) |

Phases 5B, 9 et 10 : extensions décidées après coup (5B le 2026-08-31, 9 et 10 le
2026-08-27), hors calendrier initial. Le « B » de 5B signifie « insérée entre 5 et 6 », pas
« sous-partie de la phase 5 ».

## Jeux de données du banc d'essai

Vérifiés le 2026-08-26 (`docs/datasets-verification-2026-08-26.md`, ADR 001) : NQ retiré,
τ-bench remplacé par **tau2-bench**, BIRD via **Mini-Dev**. Chaque loader arrive avec la phase
qui en a besoin.

| Usage | Jeux | Ce que le jeu fournit | Phase |
|---|---|---|---|
| Retrieval | **BEIR** (SciFact, NFCorpus, FiQA) | corpus + requêtes + jugements de pertinence | 0 (SciFact), 2, 3 |
| Modèles d'embeddings | **MTEB** | protocole de comparaison standardisé | 1 |
| Multi-hop | **HotpotQA**, **MuSiQue**, 2WikiMultihopQA | questions + passages de preuve | 2, 3 |
| Questions sans réponse / refus | **SQuAD 2.0** | libellé explicite du « pas de réponse » | 2 |
| Chunking sur **documents bruts** | **QASPER** | documents entiers, pas des passages pré-découpés | 1, 3 |
| Text-to-SQL | **Spider**, **BIRD Mini-Dev** | les bases elles-mêmes + requête de référence ; vérité = résultat d'exécution | 4 |
| API métier, agents multi-tours | **tau2-bench** | outils API + base + règles + utilisateur simulé | 4 |
| Appels d'outils, granularité fine | **BFCL** | exactitude des arguments, appels parallèles, cas « ne rien appeler » | 4 |
| Tableaux et raisonnement numérique | **HybridQA**, **TAT-QA**, WikiTableQuestions, FinQA | croisement texte + tableau, réponses annotées | 4 |
| Séries temporelles | **synthétique, généré par nos soins** | vérité calculée par pandas : zéro annotation, pièges contrôlés (valeurs manquantes, fuseaux, chevauchements, révisions de valeurs passées) | 4 |
| Images : QA sur documents et graphiques | **DocVQA**, **ChartQA** | questions annotées sur documents scannés et graphiques | 4 |
| Images : extraction champ par champ | **CORD**, **FUNSD** | chaque champ étiqueté → exactitude par champ | 4 |
| Injection de prompt agentique | **AgentDojo** | environnements outillés + tâches d'injection | 4 |
| Tabulaire à texte libre | **fake_job_postings2** (EMSCAD) | classification, score publié | 5B |
| Classification de texte | **Banking77** | 77 intentions, scores publiés | 5B |
| Voice / browser | VoiceBench, WebArena ou équivalents | à vérifier au démarrage, même protocole | 9, 10 |

**Notes de mise en œuvre.** Spider et BIRD sont en SQLite : conversion vers Postgres (sqlglot),
c'est du vrai travail et un bon notebook. BIRD est volumineux et volontairement sale —
commencer par un sous-ensemble. DocVQA et ChartQA impliquent un modèle multimodal, donc un
coût : échantillonner. Pour les séries temporelles, le générateur fait partie du livrable au
même titre que le code applicatif : versionné, testé, graine fixée.

**La contamination est un sujet à traiter, pas à ignorer** : ces jeux sont probablement dans
les données d'entraînement des modèles, donc les scores sont flattés. Mesure de signal de
contamination et petit jeu « frais » de comparaison (phase 2.5), réappliqués en 5B.

## Fil rouge : les histoires d'incident

Les trois histoires d'entretien de la phase 8 viennent de la construction elle-même
(régression détectée par la CI d'évaluation, dérive de coût, juge mal calibré, quantization qui
dégrade en silence, pipeline qui reconstruit tout). Elles se consignent **au fil de l'eau**
dans `JOURNAL.md`, rubrique « Incidents / surprises » — jamais reconstituées après coup.
