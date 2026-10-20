# Ordre de lecture du banc

> Dans quel ordre lire ce dépôt pour l'étudier, de la phase 0 à la phase 10. Écrit le
> 2026-10-20, au moment de reprendre la phase 1 construite. C'est une carte de lecture, pas
> un état : ce qui est fait ou non est dans `STATE.md`.

## Principes

- **Un bloc, une séance.** Chaque bloc dit ce qu'il exige : rien, un Postgres local, des
  clés, un cluster AWS. Les blocs sans exigence passent en premier.
- **L'ordre à l'intérieur d'un bloc est toujours le même** : l'ADR qui justifie la structure
  → le notebook, exécuté en mode échantillon → les modules de `src/` au moment où le notebook
  les affiche (`inspect.getsource`) → le test du module quand un contrat reste flou → le guide
  d'infra quand une exécution l'exige.
- **Les phases non construites** listent les livrables que `docs/roadmap/phase-N.md` nomme,
  avec les numéros de notebook de la roadmap (`notebooks/phase-N/NN_slug.ipynb`). Les chemins
  exacts s'écrivent ici à la clôture de la phase (protocole `CLAUDE.md` §3, étape « Traces »).
  Rien de ⏳ n'est à chercher dans le dépôt avant.
- Légende : ✅ existe · ⏳ à venir, nom donné par la roadmap.

## Rituel de reprise, à chaque retour

Avant tout bloc, dans cet ordre : [STATE.md](../STATE.md) → dernières entrées de
[JOURNAL.md](../JOURNAL.md) → [decisions.md](decisions.md), les lignes depuis ta dernière
session → les ADR que ces lignes citent → `docs/roadmap/phase-N.md` de la phase en cours.
C'est le protocole de reprise du brief, appliqué à toi aussi.

---

## Bloc 0 — Ce qui a changé pendant l'arrêt (✅ · 30 min · rien à installer)

1. [decisions.md](decisions.md), lignes du 2026-10-19.
2. [ADR 009](adr/009-single-environment-oidc-aws-services.md) : un seul environnement,
   déploiement OIDC, règle d'entrée des services AWS.
3. [STATE.md](../STATE.md), section « Reste à faire ». La demande de quota GPU se lance dès
   ce bloc : elle prend des jours à des semaines et la phase 6 en dépend.

## Bloc 1 — Phase 0, le vocabulaire (✅ · une séance · rien à installer)

4. [ADR 001](adr/001-datasets.md) (les jeux retenus) et
   [ADR 004](adr/004-loader-interface.md) (l'interface des loaders), courts.
5. [Notebook 0](../notebooks/phase-0/00_guided_tour.ipynb) : corpus, queries, qrels,
   nDCG, SciFact, les quinze jeux. En partie 4, lire à côté
   [eval/types.py](../src/llm_testbench/eval/types.py),
   [eval/loaders/base.py](../src/llm_testbench/eval/loaders/base.py),
   [eval/loaders/beir.py](../src/llm_testbench/eval/loaders/beir.py) et
   [datasets-verification-2026-08-26.md](datasets-verification-2026-08-26.md).
6. [ADR 003](adr/003-code-conventions.md) : comment le code est écrit, typé et testé, à lire
   une fois avant d'ouvrir `src/`.

## Bloc 2 — Phase 1, la couche LLM (✅ · une à deux séances · rien à installer)

7. [ADR 006](adr/006-llm-layer-and-governance.md) d'abord : il justifie toute la structure.
8. [Notebook 1](../notebooks/phase-1/01_robust_llm_call.ipynb), en mode échantillon.
   Modules dans l'ordre de sa partie 3 :
   - 3.1 la requête neutre et gouvernée :
     [llm/types.py](../src/llm_testbench/llm/types.py),
     [llm/governance.py](../src/llm_testbench/llm/governance.py),
     [llm/registry.py](../src/llm_testbench/llm/registry.py), avec
     [config/llm_backends.toml](../config/llm_backends.toml) et
     [config/governance_policy.toml](../config/governance_policy.toml) ;
   - 3.2 la traduction vers le SDK et les erreurs typées :
     [llm/provider.py](../src/llm_testbench/llm/provider.py),
     [llm/providers/anthropic.py](../src/llm_testbench/llm/providers/anthropic.py),
     [llm/providers/openai_compatible.py](../src/llm_testbench/llm/providers/openai_compatible.py),
     [llm/errors.py](../src/llm_testbench/llm/errors.py) ;
   - 3.3 retry, circuit breaker, délai :
     [llm/resilience.py](../src/llm_testbench/llm/resilience.py) ;
   - 3.4 budget, cache, gouvernance :
     [llm/budget.py](../src/llm_testbench/llm/budget.py),
     [llm/cache.py](../src/llm_testbench/llm/cache.py),
     [llm/cost.py](../src/llm_testbench/llm/cost.py) avec
     [config/llm_pricing.toml](../config/llm_pricing.toml) ;
   - 3.5 la façade, où l'ordre des maillons est le contrat :
     [llm/client.py](../src/llm_testbench/llm/client.py) ;
   - 4.7 sortie structurée :
     [llm/structured.py](../src/llm_testbench/llm/structured.py),
     [llm/prompts.py](../src/llm_testbench/llm/prompts.py),
     [prompts/structured_output_instruction.md](../prompts/structured_output_instruction.md),
     [prompts/structured_output_repair.md](../prompts/structured_output_repair.md) ;
   - 4.1 et 4.8 la trace et le streaming :
     [obs/tracing.py](../src/llm_testbench/obs/tracing.py) ;
   - toute la partie 4, le simulateur qui fait tomber chaque maillon :
     [llm/testing.py](../src/llm_testbench/llm/testing.py).
9. Quand un comportement reste flou, le test du module est le contrat le plus court :
   [tests/llm/](../tests/llm/), par exemple
   [test_resilience.py](../tests/llm/test_resilience.py).

## Bloc 3 — Phase 1, l'ingestion et la première mesure (✅ · une séance · Postgres local)

10. [Guide 01](infra/01-local-dev-k3d.md), `make k3d-up` : le notebook 2 a besoin d'une
    base pgvector.
11. [ADR 007](adr/007-sources-ingestion-pgvector.md).
12. [Notebook 2](../notebooks/phase-1/02_document_to_index.ipynb), en mode échantillon.
    Modules dans l'ordre de sa partie 3 :
    - 3.1 parsing : [sources/types.py](../src/llm_testbench/sources/types.py),
      [ingest/parsing.py](../src/llm_testbench/ingest/parsing.py),
      [eval/loaders/qasper.py](../src/llm_testbench/eval/loaders/qasper.py) ;
    - 3.2 chunking : [ingest/chunking.py](../src/llm_testbench/ingest/chunking.py) ;
    - 3.3 embeddings : [llm/embeddings.py](../src/llm_testbench/llm/embeddings.py) ;
    - 3.4 stockage : [ingest/store.py](../src/llm_testbench/ingest/store.py) ;
    - 3.5 pipeline : [ingest/pipeline.py](../src/llm_testbench/ingest/pipeline.py),
      [ingest/cli.py](../src/llm_testbench/ingest/cli.py) ;
    - partie 4, du retrieval à la réponse citée :
      [sources/documents.py](../src/llm_testbench/sources/documents.py),
      [generation/answer.py](../src/llm_testbench/generation/answer.py),
      [prompts/chat_answer.md](../prompts/chat_answer.md), puis l'API :
      [app/schemas.py](../src/llm_testbench/app/schemas.py),
      [app/chat.py](../src/llm_testbench/app/chat.py),
      [app/sse.py](../src/llm_testbench/app/sse.py),
      [app/main.py](../src/llm_testbench/app/main.py) ;
    - partie 5, trois embeddings contre la littérature :
      [eval/embeddings_bench.py](../src/llm_testbench/eval/embeddings_bench.py) et le
      résultat archivé `data/results/embeddings_scifact.json`.
13. [Guide 07](infra/07-observability.md), `make langfuse-up` (VM Docker à 12 GB) : c'est là
    que vont les traces que les deux notebooks viennent d'émettre.
14. Tests de référence : [tests/ingest/](../tests/ingest/),
    [tests/generation/test_answer.py](../tests/generation/test_answer.py),
    [tests/app/test_api.py](../tests/app/test_api.py).

## Bloc 4 — Phase 1, exécutions complètes (✅ · clés nécessaires)

15. `.env` depuis `.env.example` (OpenAI, Anthropic, OpenRouter), puis dans l'ordre :

    ```bash
    make ingest-scifact
    make notebooks-full      # section « vrai provider » du 1, vrais embeddings et génération du 2
    make bench-embeddings    # ajoute text-embedding-3-small au tableau du notebook 2
    ```

16. Relire la partie 7 du notebook 1 (coût, prompt caching) et la partie 5 du notebook 2
    avec les vrais chiffres, et les comparer à `STATE.md` « Chiffres actuels ».

## Bloc 5 — Phase 1, l'infra cloud (✅ · AWS · ≈ 6 $/jour allumé)

Les guides se lisent dans l'ordre où ils s'exécutent ; l'[index](infra/README.md) donne le
coût de chacun. Ce bloc peut attendre la fin de la phase 2, qui est hors ligne ; il doit être
fait avant la phase 3 (Bedrock Knowledge Bases en bras de comparaison, matrice d'expériences
sur le cluster).

17. [Guide 00](infra/00-bootstrap.md) : bucket d'état, alerte de budget, rôle OIDC GitHub
    (`make bootstrap-apply`, huit ressources, 15 min).
18. [Guide 08](infra/08-costs.md) : ce que coûte chaque module, avant d'allumer quoi que ce
    soit.
19. [Guide 02](infra/02-network-vpc.md) → [03](infra/03-eks.md) →
    [04](infra/04-rds-pgvector.md) → [05](infra/05-secrets.md) : `make infra-up`,
    `make cluster-addons`, secrets.
20. [Guide 06](infra/06-helm-chart-api.md) : le chart, `make deploy`.
21. [Guide 09](infra/09-github-oidc-deployment.md) : la variable `AWS_DEPLOY_ROLE_ARN`
    (commande dans `STATE.md`), puis `make deploy-trigger`.
22. `make infra-down` le soir.

---

## Bloc 6 — Phase 2, l'évaluation (⏳ · phase centrale)

**Avant `GO PHASE 2`** : [roadmap/phase-2.md](roadmap/phase-2.md) en entier ;
[ADR 008](adr/008-work-on-main.md) pour la porte de régression (2.7) ; le plan d'une page
que je rends, avec ses décisions ouvertes.

**Pendant la phase, dans l'ordre** :

23. Les ADR du plan (harness et métriques, juge, corpus maison), puis le fichier de phase à
    nouveau s'il est amendé.
24. `notebooks/phase-2/01_*` — mesurer un RAG : pourquoi les métriques bout-en-bout cachent
    le vrai problème. Modules : `eval/` (runners BEIR, HotpotQA, SQuAD 2.0, QASPER ; métriques
    retrieval et génération séparées ; N runs et bootstrap). Premier contrôle : le harness
    reproduit les nDCG@10 du bloc 3.
25. `notebooks/phase-2/02_*` — LLM-as-judge : le calibrer ou ne pas s'en servir. Modules :
    `eval/` (juge, calibration, kappa), rubriques dans `prompts/`.
26. `notebooks/phase-2/03_*` — contamination : pourquoi tes bons scores mentent peut-être.
    Le corpus maison (2.5), son script de téléchargement, sa licence.
27. `notebooks/phase-2/04_*` — construire un golden set à partir de rien, en petit. La CLI de
    revue, le golden set versionné dans `data/` avec son CHANGELOG.
28. La porte d'évaluation (2.7) : `make eval`, `make eval-gate`, le hook `pre-push`, le job
    CI, et le passage du notebook qui la compare honnêtement à un merge bloqué en équipe.
29. Ragas, promptfoo, DeepEval : la comparaison dans le notebook, après le nôtre.

**Ce qui t'attend, toi** : choisir le corpus maison parmi trois candidats (2.5) ; annoter
50 exemples à la main pour calibrer le juge (2.3) ; relire intégralement les 50 à 80 questions
du golden set via la CLI (2.6).

**À la clôture** : l'entrée de clôture de `JOURNAL.md` (récit, incidents), la baseline
chiffrée du système de la phase 1 contre la littérature, `STATE.md`.

## Bloc 7 — Phase 3, RAG avancé et pipeline opéré (⏳)

**Avant `GO PHASE 3`** : [roadmap/phase-3.md](roadmap/phase-3.md) ; relire dans
[ADR 007](adr/007-sources-ingestion-pgvector.md) le choix « un index = une table » : c'est
le point de départ du lineage. Le bloc 5 doit être fait.

**Pendant la phase, dans l'ordre** :

30. L'ADR orchestrateur (Dagster contre Airflow contre Prefect) et les ADR des techniques
    retenues ou retirées.
31. `notebooks/phase-3/01_*` — pourquoi le hybrid search sauve les acronymes et le jargon.
    Modules : `retrieval/` (BM25, fusion RRF, re-ranking cross-encoder).
32. `notebooks/phase-3/02_*` — le duel des stratégies de chunking sur documents bruts
    (QASPER), et le parsing PDF reporté de la phase 1. Modules : `ingest/`.
33. `notebooks/phase-3/03_*` — transformation de requête : quand ça aide, quand ça coûte pour
    rien (HyDE, multi-query, décomposition, routage). Modules : `retrieval/`, `generation/`.
34. `notebooks/phase-3/04_*` — notre pipeline contre LlamaIndex et contre Bedrock Knowledge
    Bases sur le même jeu BEIR. Les deux ports vivent dans le matériel de benchmark, pas dans
    `src/` ; le service AWS est créé et détruit dans la journée.
35. `notebooks/phase-3/05_*` — la matrice d'expériences : régénérer cent index sans tout
    recalculer. Le pipeline orchestré, Pandera en entrée, le lineage ; le guide d'infra de
    l'orchestrateur sur le cluster.
36. GraphRAG, en dernier, et son retrait chiffré s'il n'apporte rien.

**Ce qui t'attend, toi** : le critère d'acceptation — régénérer n'importe quelle ligne du
tableau maître depuis zéro, avec une seule commande. À tester toi-même.

**À la clôture** : tableau « technique → gain avec intervalle de confiance → p95 → € »,
écart à la littérature, ligne « régénération d'une ligne depuis zéro ».

## Bloc 8 — Phase 4, agents multi-sources (⏳)

**Avant `GO PHASE 4`** : [roadmap/phase-4.md](roadmap/phase-4.md) ; relire
[sources/types.py](../src/llm_testbench/sources/types.py) : chaque connecteur s'y branche.

**Pendant la phase, dans l'ordre** :

37. Les ADR du plan (socle d'orchestration maison puis LangGraph, routage, AgentCore en
    option).
38. `notebooks/phase-4/01_*` — un agent sans framework, la mécanique à nu, puis le même agent
    sur LangGraph, smolagents, OpenAI Agents SDK et CrewAI, comparés au chiffre. Modules :
    `agents/` (machine à états, schémas d'outils, garde-fous) ; les ports dans le matériel de
    benchmark.
39. `notebooks/phase-4/02_*` — text-to-SQL, du schéma à la requête sûre (Spider, BIRD
    Mini-Dev). Modules : `sources/` (connecteur SQL, catalogue, pipeline de sûreté sqlglot,
    rôle en lecture seule).
40. `notebooks/phase-4/03_*` — outils, API et effets de bord (OpenAPI, confirmation humaine,
    identité propagée, tau2-bench).
41. `notebooks/phase-4/04_*` — données structurées et images : extraire sans halluciner
    (bac à sable, DocVQA, ChartQA, CORD, FUNSD) ; le générateur de séries temporelles.
42. `notebooks/phase-4/05_*` — le routage multi-sources et les sources contradictoires,
    routeur explicite contre agent qui décide seul, les deux mesurés.
43. `notebooks/phase-4/06_*` — évaluer un agent : trajectoires, exécution, extraction (BFCL,
    tau2-bench, AgentDojo). Le harness de la phase 2 étendu, pas un second.
44. `notebooks/phase-4/07_*` — la mémoire d'agent : quoi retenir, où, à quel coût.
45. Le serveur MCP et la composition de plusieurs serveurs (4.8), A2A en discussion ; le cas
    où l'agent est la mauvaise réponse, mesuré.

**Ce qui t'attend, toi** : tu es la confirmation humaine sur les effets de bord (4.3) ; les
attaques d'injection indirecte sont à rejouer toi-même (4.7).

**À la clôture** : exactitude d'exécution SQL, exactitude par champ, matrice de confusion du
routage, scores BFCL, tau2-bench, AgentDojo.

## Bloc 9 — Phase 5, LLMOps (⏳)

**Avant `GO PHASE 5`** : [roadmap/phase-5.md](roadmap/phase-5.md) ; relire dans
[ADR 009](adr/009-single-environment-oidc-aws-services.md) la règle d'entrée des services
AWS ; les guides [07](infra/07-observability.md) et [09](infra/09-github-oidc-deployment.md)
sont le socle.

**Pendant la phase, dans l'ordre** :

46. Le générateur de trafic synthétique en premier : son module, ses profils, et le paragraphe
    du README qui dit ce qu'il ne capture pas.
47. L'ADR de la file (SQS contre Postgres `SKIP LOCKED`, Redis Streams ou pas) et l'ADR du
    collecteur.
48. `notebooks/phase-5/01_*` — anatomie d'une trace et d'où viennent les millisecondes.
    Modules : `obs/` ; guide d'infra ADOT contre collecteur vanilla.
49. `notebooks/phase-5/02_*` — le modèle de coût, du token au prix par utilisateur. Budgets,
    kill switch, guide Cost Anomaly Detection, guide Karpenter.
50. `notebooks/phase-5/03_*` — détecter une régression de qualité en production sans labels.
    Juge asynchrone, file et worker, guide SQS, détection de drift.
51. Le registre de prompts, l'A/B derrière flag, canary et shadow dans le chart ; les
    dashboards JSON.
52. Les trois runbooks : provider indisponible · qualité dégradée sans changement de code ·
    coûts triplés dans la nuit.
53. L'UI de chat minimale, en fin de phase.

**Ce qui t'attend, toi** : jouer les trois runbooks en vrai sur le cluster, pas les lire ;
piloter les profils du générateur, y compris la dérive.

**À la clôture** : coût par profil extrapolé au mois, délais de détection (drift, coût) sur
dérive injectée, temps de montée Karpenter.

## Bloc 10 — Phase 5B, le pont (⏳)

**Avant `GO PHASE 5B`** : [ADR 005](adr/005-phase-5b-the-bridge.md) puis
[roadmap/phase-5b.md](roadmap/phase-5b.md) ; relire les trois verrous de `CLAUDE.md` §6.

54. `notebooks/phase-5b/01_*` — choisir entre un XGBoost et un LLM, la réponse est un
    tableau. Modules : `classic/` (jamais exposé par l'API), runners dans `eval/`, gabarit de
    sérialisation dans `prompts/`, le manifeste de run.
55. `docs/decision-tree-ml-vs-llm.md`, le livrable clé : chaque branche cite un chiffre.

**À la clôture** : le tableau des axes 5B.3, le signal de contamination à côté de chaque
chiffre.

## Bloc 11 — Phase 6, inférence et modèles ouverts (⏳ · GPU)

**Avant `GO PHASE 6`** : [roadmap/phase-6.md](roadmap/phase-6.md) ; l'état du quota GPU
dans `STATE.md` ; relire
[llm/providers/openai_compatible.py](../src/llm_testbench/llm/providers/openai_compatible.py)
et le backend `local` de [config/llm_backends.toml](../config/llm_backends.toml) : vLLM
s'y branche.

56. L'ADR de cible GPU (fournisseur spécialisé éphémère contre node group sur l'EKS existant)
    et le guide d'infra correspondant ; la destruction doit être évidente.
57. `notebooks/phase-6/01_*` — ce que vLLM fait vraiment sous le capot (continuous batching,
    PagedAttention, KV cache).
58. `notebooks/phase-6/02_*` — le vrai coût qualité de la quantization (AWQ, GPTQ, FP8),
    mesuré par le harness.
59. `notebooks/phase-6/03_*` — self-host contre API, le calcul complet (throughput, latence,
    sizing, seuil de bascule) ; embeddings et reranker self-hosted.
60. Le LoRA/QLoRA et son manifeste de run ; les cas où le fine-tuning n'était pas la bonne
    réponse ; la phase 5B rejouée sur un modèle self-hosted ; la ligne « coût de la
    gouvernance ».

**Ce qui t'attend, toi** : vérifier chaque soir que le GPU est détruit.

**À la clôture** : coût par million de tokens, cold start et temps de montée sur chaque cible.

## Bloc 12 — Phase 7, sécurité résiduelle et conformité (⏳)

**Avant `GO PHASE 7`** : [roadmap/phase-7.md](roadmap/phase-7.md) ; le corpus maison du
bloc 6 fournit les documents empoisonnés.

61. L'ADR du plan (Bedrock Guardrails en bras de comparaison, ou pas).
62. Le ou les notebooks décidés au plan : la roadmap n'en nomme pas. OWASP LLM Top 10 sur
    l'architecture complète, injection par document, exfiltration via les citations, filtrage
    de sortie, Presidio, red teaming (garak, promptfoo) dans la CI.
63. `docs/ai-act.md` : classification de risque, documentation, journalisation, minimisation
    RGPD, sur un déploiement hypothétique ; la grille de défendabilité de la phase 5B s'y
    rattache.

**Ce qui t'attend, toi** : savoir tenir la conversation AI Act en entretien, pas produire un
dossier.

## Bloc 13 — Phase 8, packaging (⏳ · commence dès la phase 2)

Ce bloc ne se lit pas en une fois : [roadmap/phase-8.md](roadmap/phase-8.md) d'abord, puis
au fil des phases.

64. À chaque clôture de phase, la rubrique « Incidents / surprises » de `JOURNAL.md` : les
    trois histoires d'incident d'entretien en sortent, jamais reconstituées après coup.
65. Le README à mesure que le tableau maître grossit (dès la phase 2), avec la ligne
    « régénération depuis zéro » (phase 3), l'arbre de décision (5B), la ligne « coût de la
    gouvernance » (phase 6), les limites du dispositif.
66. Les deux posts : le harness d'évaluation, et self-host contre API avec nos chiffres.
67. La préparation d'entretien : system design chronométré, build contre buy sur trois
    briques, trois histoires situation-action-résultat chiffré. Confronter à de vraies offres
    le raisonnement sur le mot « pipeline » (2026-10-15).

## Bloc 14 — Phase 9, voice (⏳ · extension)

**Avant `GO PHASE 9`** : [roadmap/phase-9.md](roadmap/phase-9.md) ; la vérification des
jeux (VoiceBench ou équivalent), même protocole que la phase 0, et son ADR.

68. `notebooks/phase-9/01_*` — d'où vient la latence d'un agent vocal, milliseconde par
    milliseconde (time-to-first-audio par étape).
69. `notebooks/phase-9/02_*` — évaluer un agent qu'on écoute. Le pipeline STT → agent → TTS
    derrière l'API existante, barge-in, dégradation vers le texte.

**À la clôture** : coût par minute contre coût par requête texte ; décision GO/NO-GO sur la
phase 10.

## Bloc 15 — Phase 10, browser et computer use (⏳ · si GO)

[roadmap/phase-10.md](roadmap/phase-10.md), puis `notebooks/phase-10/01_*` — un agent qui
clique : l'outil navigateur derrière l'interface existante, les garde-fous de la phase 4 et
l'injection indirecte démultipliée, mesuré sur WebArena ou équivalent. Si NO-GO, seul le
paragraphe « pas fait, et pourquoi » du README est à lire.

---

## Tenue de ce fichier

- À la clôture de chaque phase (protocole `CLAUDE.md` §3, étape « Traces »), les ⏳ du bloc
  deviennent des liens réels : slugs des notebooks, ADR numérotés, guides d'infra insérés à
  leur place d'exécution, modules de `src/` nommés dans l'ordre où les notebooks les
  affichent.
- Si une phase est amendée (`decisions.md`), le bloc correspondant est corrigé dans le même
  commit, comme le fichier de phase.
- Ce fichier ne porte pas de statut. « Fait / pas fait » et « reste à faire » sont dans
  `STATE.md`.
