# PHASE 5 — LLMOps : observabilité, coût, exploitation (semaines 12–13) ⭐ MON ARME

C'est ici que mes années de DevOps deviennent un avantage. Peu d'AI Engineers savent faire cette phase —
à soigner autant que la phase 2.

**Prérequis : le générateur de trafic synthétique.** Il n'y a pas d'utilisateurs. D'abord un
générateur qui rejoue les requêtes des jeux publics selon des profils configurables — débit,
rafales, mélange de types de questions, part de requêtes hors périmètre, et **possibilité de
faire dériver la distribution dans le temps**. Tout le reste de la phase se mesure dessus. Écrire
explicitement dans le README ce que cette simulation ne capture pas.

**Traçabilité** OTel/GenAI + Langfuse : trace complète requête → routage → retrieval →
reranking → outils → génération, avec durée, tokens et coût par span. Collecteur : **ADOT** (la
distribution AWS d'OpenTelemetry) sur EKS, le collecteur OTel vanilla en local — même pipeline
OTLP, deux distributions, la différence expliquée et chiffrée (ce qu'ADOT ajoute vraiment).

**Coût et latence.** Coût par requête et **par profil de trafic**, extrapolé en coût mensuel
pour des volumes cibles que tu proposeras. TTFT et p50/p95/p99 décomposés par étape sous
charge. Budgets, alertes, kill switch sur dérive de coût ; **Cost Anomaly Detection** (AWS) en
complément du kill switch maison, les deux délais de détection mesurés sur la même dérive
injectée. **Karpenter** pour absorber le générateur de trafic : nœuds à la demande, Spot pour le
générateur et les jobs d'évaluation, temps de montée et coût chiffrés.

**Prompts.** Registre de versions de prompts avec rollback à chaud sans redéploiement. A/B
testing de prompts derrière feature flag, avec analyse statistique sur trafic simulé.
Déploiement canary et shadow pour un changement de prompt ou de modèle.

**Qualité en continu.** Échantillonnage des requêtes vers un juge asynchrone, détection de drift
sur la distribution entrante — mesurée en injectant une dérive contrôlée depuis le générateur,
ce qui donne un vrai chiffre : au bout de combien de requêtes la détection se déclenche-t-elle ?
Boucle de feedback : l'endpoint et le stockage, alimentés par le juge à défaut d'utilisateurs —
et on le dit.

**File et worker.** L'échantillonnage vers le juge et la boucle de feedback passent par une
vraie file et un worker, jamais par un appel en ligne dans la requête : livraison au moins une
fois, idempotence par clé, retries, file de lettres mortes surveillée. Abstraction à deux
implémentations, comme la couche LLM (ADR 006) : Postgres `SKIP LOCKED` en local sur k3d,
**SQS** sur AWS (file standard, file de lettres mortes gérée, visibilité, at-least-once natif) ;
l'ADR du plan de phase arbitre le reste (Redis Streams, ou pas), sous la contrainte que le code
applicatif ne voie jamais la différence (`CLAUDE.md` §4, règle d'entrée des services AWS).

**Runbooks obligatoires** : le provider est indisponible · la qualité s'est dégradée sans
changement de code (le fournisseur a silencieusement mis à jour son modèle) · les coûts ont
triplé dans la nuit.

**UI de chat minimale**, en fin de phase : une page qui consomme le streaming SSE, affiche les
citations et alimente l'endpoint de feedback — trois choses déjà construites à ce stade. Son
but est de rendre le banc démontrable en 30 secondes en entretien ou devant un client, pas de
faire du produit : pas de framework front lourd, pas de design system, une page.

**Notebooks** : (1) anatomie d'une trace et d'où viennent les millisecondes ; (2) le modèle de
coût, du token au prix par utilisateur ; (3) détecter une régression de qualité en production
sans labels.
