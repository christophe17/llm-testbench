# ADR 009 — Un seul environnement éphémère, déploiement par OIDC, règle d'entrée des services AWS

- **Date** : 2026-10-19
- **Statut** : accepté

## Contexte

Reprise du projet après un mois d'arrêt, audit du brief et de l'infra à la lumière du
programme (`~/Roadmaps/program`, PD-18 : ce banc est la preuve pour les missions freelance, et
Christophe veut monter en compétence sur AWS sans prendre une mauvaise décision d'infra pour
des raisons pédagogiques). Trois constats :

1. le brief (§4) prévoyait des environnements `dev` et `prod`, héritage de l'époque où le
   projet était un produit ; un banc sans utilisateurs n'a rien à mettre en production, et un
   second environnement est un poste dormant et du Terraform sans charge ;
2. le déploiement était manuel (`make deploy` depuis le poste, décision du 2026-09-03), alors
   que le mot-clé CI/CD sur AWS est au cœur du positionnement et que la phase 5 (canary,
   rollback) a besoin d'un mécanisme de déploiement reproductible ;
3. la demande « utiliser le plus de services AWS possible pour apprendre » n'avait pas de
   règle : sans règle, on empile (le brief §6 l'interdit), ou on refuse tout.

S'y ajoute un compromis documenté depuis la phase 1 : le mot de passe RDS traversait l'état
Terraform pour composer l'URL de la base.

## Options considérées

**Environnements.** (1) `dev` + `prod` comme écrit — fidèle au brief, mais `prod` n'aurait ni
trafic ni raison d'être, et doublerait le coût allumé. (2) **Un seul `dev` éphémère** — le
canary et le shadow de la phase 5 se démontrent dans un cluster (deux releases Helm, un
routage), pas entre deux environnements ; si un jour une mission exige un vrai `prod`, il se
crée alors, avec sa raison.

**Déploiement.** (1) Manuel depuis le poste — simple, non reproductible, pas de trace. (2)
Clé AWS dans les secrets GitHub — jamais. (3) **GitHub Actions avec rôle OIDC**, déclenché à
la main (cluster éphémère), runner arm64, build + push ECR + `helm upgrade` — identique à
`make deploy`, sans secret stocké, tracé dans CloudTrail. (4) GitOps (Argo CD / Flux) — la
réponse de production quand l'endpoint est privé ; un opérateur de plus sur un cluster détruit
chaque soir, reporté en phase 5 avec Argo Rollouts.

**Services AWS.** (1) Minimum (EKS, RDS, ECR, S3, Secrets Manager) et rien d'autre — sûr, mais
laisse l'apprentissage AWS hors du banc. (2) Maximum « pour apprendre » (Lambda, Step
Functions, Kendra, OpenSearch Serverless, SageMaker…) — c'est l'empilement que le brief
interdit, et les services managés de RAG cachent exactement ce que le banc mesure. (3) **Une
règle d'entrée** : un service AWS entre quand il est la réponse naturelle d'un bloc déjà prévu
par la roadmap, ou comme bras de comparaison mesuré ; jamais comme chemin unique ; chaque
service a une implémentation locale équivalente derrière la même abstraction.

## Décision

Option 2, option 3, option 3.

- **Un seul environnement `dev`, éphémère.** `CLAUDE.md` §4 corrigé ; `infra/terraform/README.md`
  ne mentionne plus `envs/prod`.
- **Déploiement par GitHub Actions et OIDC** : fournisseur OIDC et rôle `llm-testbench-github-deploy`
  dans le bootstrap (identité de compte, stable, gratuite) ; access entry `AmazonEKSClusterAdminPolicy`
  dans `envs/dev` ; workflow `deploy.yml` en `workflow_dispatch`, runner `ubuntu-24.04-arm`,
  qui lit l'adresse de la base et l'ARN de son secret par l'API RDS, jamais par l'état
  Terraform. La CI de tests reste hors ligne et sans secret (ADR 003). Guide 09.
- **Conséquence assumée : l'endpoint public du cluster reste ouvert** (`public_access_cidrs`
  à `0.0.0.0/0`). Les runners GitHub n'ont pas d'IP fixe ; l'accès est authentifié par IAM et
  journalisé. La restriction à une IP et le pipeline sont exclusifs sans runner dans le VPC ou
  mode pull ; on choisit le pipeline, et la variable reste pour qui ne déploie que depuis son
  poste.
- **L'URL de la base est composée dans le cluster** par un template External Secrets (moteur
  v2, `urlquery`), à partir du secret géré par RDS ; Terraform ne lit plus le mot de passe.
  Le secret `database-url` disparaît.
- **Règle d'entrée des services AWS**, inscrite dans `CLAUDE.md` §4, avec ses premières
  applications dans les fichiers de phase : Bedrock Knowledge Bases comme bras de comparaison
  du notebook 4 de la phase 3 ; SQS (abstraction à deux implémentations, Postgres `SKIP
  LOCKED` en local), ADOT, Karpenter et Cost Anomaly Detection en phase 5 ; un node group GPU
  sur l'EKS existant comme seconde cible mesurée de la phase 6, si le quota G est accordé
  (demande à faire dès maintenant) ; Bedrock Guardrails en phase 7 et AgentCore en phase 4,
  optionnels, décidés au plan de phase. Refusés même pour apprendre : multi-compte et Control
  Tower, Transit Gateway, Kinesis, Glue, EMR, SageMaker comme plateforme — aucune charge du
  banc ne les justifie.

## Conséquences

- Le bootstrap passe de cinq à huit ressources et doit être appliqué avant `envs/dev` (il
  l'était déjà pour le bucket d'état). Une variable de dépôt GitHub (`AWS_DEPLOY_ROLE_ARN`)
  à poser une fois.
- `make deploy` et le workflow font la même chose par deux chemins (`terraform output` /
  API RDS) ; les deux doivent évoluer ensemble. Un test de rendu du chart avec les valeurs
  `database.*` est dans `make helm-lint`.
- La phase 5 hérite de deux obligations : passer `deploy.yml` en `on: push` quand le cluster
  tournera en continu, et revoir push contre pull (Argo Rollouts pour le canary).
- La phase 6 hérite d'une colonne de plus dans son tableau (cible AWS contre fournisseur
  spécialisé) et d'un ADR de choix de cible chiffré à la place de l'ADR de découplage.
- À revisiter si un contributeur ou un client entre dans le dépôt : environnement GitHub avec
  approbation, moindre privilège sur le cluster (guide 09, pièges), retour aux PR (ADR 008).
