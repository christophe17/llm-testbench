# PHASE 4 — Agents multi-sources (semaines 9–11) ⭐ À ÉGALITÉ AVEC LE RAG

Dans mes missions passées, mes agents interrogeaient des bases SQL, des API métier, des données
structurées et des images. C'est mon terrain d'ingénierie et le segment qui se commoditise le
moins vite. Ce n'est pas un appendice du RAG. Chaque connecteur se branche sur l'interface
`Source` de la phase 1.

**4.1 Socle d'orchestration.** D'abord une **machine à états maison**, puis la même chose avec
LangGraph, et explique-moi honnêtement ce que le framework apporte et ce qu'il masque. Schémas
d'outils, validation Pydantic stricte, erreurs d'outil renvoyées de façon exploitable.
Garde-fous : budget d'étapes et de tokens, détection de boucle, timeout global, dégradation
gracieuse vers une réponse partielle honnête. Parallélisation des appels indépendants.

**Benchmark de frameworks d'agents** : le même agent de référence porté sur **smolagents,
OpenAI Agents SDK et CrewAI**, mesuré sur le même harness — exactitude sur les mêmes tâches,
tokens, latence, lignes de code. Raison d'être : le filtre ATS/mots-clés des offres, et un
comparatif chiffré que quasi personne ne publie. Garde-fou anti-empilement : ces ports sont des
**livrables de comparaison**, pas du code de production — `src/` garde une seule implémentation
(maison + LangGraph), les ports vivent dans le matériel de benchmark. Budget : environ une
journée par framework, ne pas creuser au-delà.

**4.2 SQL — le bloc le plus difficile, mesuré sur Spider et BIRD Mini-Dev.** Le schéma complet
ne tient pas dans le contexte : catalogue de schéma et **retrieval sur le schéma** (du RAG
appliqué aux métadonnées, pont avec la phase 3). Pipeline de sûreté avant exécution : parsing
de la requête générée (sqlglot), allowlist de tables et colonnes, interdiction DDL/DML, `LIMIT`
forcé, `EXPLAIN` préalable pour rejeter les requêtes trop coûteuses, timeout, rôle Postgres en
lecture seule, row-level security. Boucle de correction sur erreur SQL, avec budget. Pièges à
traiter explicitement : jointures plausibles mais fausses, résultat vide interprété comme « il
n'y en a pas », agrégations et `NULL`, dates et fuseaux. **Règle absolue : le modèle ne
recalcule jamais un chiffre, il restitue le résultat de la requête.** Métrique : exactitude
d'exécution, pas comparaison de texte.

**4.3 API métier.** Outils dérivés d'une spec OpenAPI plutôt qu'écrits à la main. Pagination,
rate limits, idempotence, retries. Séparation stricte lecture / écriture avec **confirmation
humaine obligatoire sur les effets de bord**. Propagation de l'identité utilisateur jusqu'à
l'API, démontrée sur des identités simulées (tau2-bench en fournit) : pas de clé partagée qui
donne tous les droits à tout le monde.

**4.4 Données structurées et séries temporelles.** Jamais un gros tableau en texte brut au
modèle : outils d'agrégation déterministes, ou exécution de code en bac à sable (sans réseau,
ressources et durée limitées). L'arithmétique est faite par du code, jamais par le modèle.

**4.5 Images et documents non textuels** — mesuré sur DocVQA et ChartQA (échantillonnés), et
CORD/FUNSD pour l'extraction. Extraction **structurée** avec schéma Pydantic imposé, jamais de
description libre. Exactitude champ par champ.

**4.6 Routage entre sources — la vraie décision d'architecture.** Documents, base, API, ou
plusieurs ? Compare un routeur explicite et un agent qui décide seul, et **mesure les deux**.
Traite les questions hybrides et le cas où deux sources se contredisent : politique de priorité
explicite ou signalement du conflit, jamais un choix silencieux.

**4.7 Sécurité des outils.** Injection indirecte via les **données renvoyées par un outil** —
champ texte empoisonné en base, réponse d'API hostile : c'est la vraie menace d'un agent.
Benchmark **AgentDojo**. Séparation stricte instructions / données, allowlist d'outils par
contexte, sandboxing, permissions utilisateur propagées de bout en bout, journal d'audit des
actions. Fabrique les attaques, montre qu'elles marchent, corrige, reteste, rechiffre.

**4.8 Serveur MCP et composition.** Expose nos outils via MCP, puis fais consommer **plusieurs
serveurs** : découverte dynamique, gouvernance des permissions, comportement quand un serveur
devient indisponible ou renvoie n'importe quoi. Beaucoup savent exposer un serveur MCP ; très
peu savent en orchestrer plusieurs proprement. Situe aussi le protocole **A2A** (agent-to-agent)
par rapport à MCP — en discussion argumentée dans le notebook, pas en implémentation.

**4.9 Évaluation étendue** — mesurée sur BFCL et tau2-bench. La vérité de référence n'est plus un
passage, ce qui change les métriques : trajectoires (outils appelés, ordre, arguments, nombre
d'étapes, coût par tâche réussie), exactitude d'exécution SQL, exactitude par champ en
extraction, matrice de confusion du routage, fidélité des chiffres cités. **Étends le harness de
la phase 2, ne crée pas un second harness.**

**4.10 Mémoire d'agent.** Mémoire conversationnelle intra-session et mémoire long-terme
inter-sessions — c'est du retrieval appliqué à l'historique des échanges, donc une réutilisation
directe de la phase 3, pas une brique exotique. Quoi retenir, où le stocker, quand l'injecter,
et **l'effet mesuré** : gain sur les tâches multi-tours (tau2-bench) contre coût en tokens de
chaque stratégie. Situer au passage le vocabulaire « context engineering » et le paysage (mem0,
checkpointing LangGraph) — en connaissance, notre implémentation reste la nôtre.

**Point de séniorité obligatoire** : implémente délibérément un cas où l'agent est **la mauvaise
réponse** — une requête déterministe fait mieux, plus vite, moins cher — mesure-le,
documente-le.

**Notebooks** : (1) un agent sans framework, la mécanique à nu — puis le même agent porté sur
LangGraph, smolagents, OpenAI Agents SDK et CrewAI, comparés au chiffre sur le même harness : ce
que chaque framework apporte, masque et coûte ; (2) text-to-SQL, du schéma à la requête sûre ;
(3) outils, API et effets de bord ; (4) données structurées et images — extraire sans
halluciner ; (5) le routage multi-sources et les sources contradictoires ; (6) évaluer un agent :
trajectoires, exécution, extraction ; (7) la mémoire d'agent : quoi retenir, où, à quel coût.
