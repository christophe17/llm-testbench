# Guide 09 — Déploiement par GitHub Actions et OIDC : build arm64, ECR, Helm, sans clé

**Durée** : 20 minutes dont 5 d'attente de workflow. **Prérequis** : guides 00 (bootstrap
appliqué, avec `github.tf`), 03 (cluster allumé) et 05 (secrets posés). **Coût** : 0 € (les
minutes GitHub Actions sont gratuites sur un dépôt public ; le cluster, lui, coûte ce qu'il
coûte — guide 08). **Code** : `infra/terraform/bootstrap/github.tf`,
`infra/terraform/envs/dev/eks.tf` (`access_entries`), `.github/workflows/deploy.yml`, cibles
`make deploy` et `make deploy-trigger`.

---

## Le problème

`make deploy` fonctionne, mais il fonctionne *depuis votre poste* : avec vos identifiants, votre
Docker, votre `kubectl`. Un pipeline de déploiement doit faire la même chose depuis une machine
qui n'a rien, et qui ne doit surtout pas recevoir une clé AWS à durée de vie illimitée dans un
secret GitHub : c'est la fuite la plus classique de l'industrie (un `print(os.environ)` dans
un log de CI). La question n'est pas « comment déployer depuis la CI », c'est **comment la CI
prouve qui elle est** sans clé.

## Les options

| Option | Verdict |
|---|---|
| Clé d'accès AWS dans les secrets GitHub | Jamais : clé longue durée, visible de tout workflow du dépôt, sans trace de *quel* job l'a utilisée. |
| **OIDC : GitHub émet un jeton signé, AWS l'échange contre un rôle** | **Retenu** : identifiants temporaires (une heure), rôle limité au dépôt et à la branche, chaque assume-role dans CloudTrail avec le `sub` du jeton. Zéro secret stocké. |
| Déploiement en mode pull (GitOps : Argo CD, Flux) | La réponse de production quand l'endpoint du cluster est privé : rien n'entre, le cluster tire. Un opérateur de plus sur un cluster éphémère ; noté pour la phase 5 (canary, Argo Rollouts). |
| Runner auto-hébergé dans le VPC | Résout l'endpoint privé, ajoute une machine à opérer. Non. |

## Lecture guidée du code réel

**[`github.tf`](../../infra/terraform/bootstrap/github.tf)** — trois ressources, dans le
bootstrap parce qu'elles sont des identités de compte, stables, gratuites, et qu'elles doivent
survivre au `make infra-down` du soir :

- `aws_iam_openid_connect_provider.github` : AWS apprend à faire confiance aux jetons signés
  par `token.actions.githubusercontent.com`, pour l'audience `sts.amazonaws.com`. Un seul par
  compte (l'URL est la clé) : si un autre projet l'a déjà créé, importez-le au lieu de le
  recréer.
- `github_deploy_trust` : la politique de confiance du rôle. Deux conditions, et c'est tout le
  modèle de sécurité : l'audience, et le `sub` du jeton qui doit valoir
  `repo:christophe17/llm-testbench:ref:refs/heads/main`. **Ni un fork, ni une pull request, ni
  une autre branche** ne peut assumer ce rôle — le `sub` d'une PR est
  `repo:...:pull_request`, celui d'une branche `ref:refs/heads/<nom>`.
- `github_deploy` : la politique du rôle, au plus juste. `ecr:GetAuthorizationToken` sur `*`
  (l'API ne connaît pas plus fin), push sur **le** dépôt `llm-testbench-api` et rien d'autre,
  `eks:DescribeCluster` sur **le** cluster (c'est ce que fait `update-kubeconfig`), et
  `rds:DescribeDBInstances` sur **l'**instance, pour lire l'adresse de la base et l'ARN de son
  secret sans toucher à l'état Terraform. Pas de `terraform` dans le pipeline : il déploie une
  image, il ne gère pas l'infra.

**[`eks.tf`](../../infra/terraform/envs/dev/eks.tf)**, bloc `access_entries` — IAM dit *qui*
peut appeler l'API EKS, pas ce qu'on peut faire *dans* Kubernetes. L'access entry associe l'ARN
du rôle (reconstruit à partir de son nom, puisque le bootstrap et `envs/dev` n'ont pas d'état
commun) à la politique `AmazonEKSClusterAdminPolicy` sur tout le cluster. C'est trop pour un
`helm upgrade` dans un namespace, et c'est assumé pour un cluster de dev à un seul locataire ;
la réponse de moindre privilège est dans les pièges.

**[`deploy.yml`](../../.github/workflows/deploy.yml)** — ce que fait `make deploy`, étape par
étape, avec trois différences :

- `on: workflow_dispatch` seulement : le cluster est éphémère, un déploiement automatique à
  chaque push échouerait le soir. `concurrency: deploy-dev` : jamais deux déploiements
  entrelacés.
- `permissions: id-token: write` : c'est ce qui autorise le job à demander un jeton OIDC.
  Sans cette ligne, `configure-aws-credentials` échoue avec un message qui parle de tout sauf
  de ça. `vars.AWS_DEPLOY_ROLE_ARN` est une *variable* de dépôt, pas un secret : un ARN n'est
  pas confidentiel.
- `runs-on: ubuntu-24.04-arm` : un runner arm64, gratuit pour un dépôt public. L'image est
  construite nativement pour les nœuds Graviton, sans QEMU (dix fois plus lent, et des
  surprises sur les roues Python).
- Les paramètres de la base (`aws rds describe-db-instances`) sont passés au chart comme
  `make deploy` le fait depuis `terraform output` : deux chemins, les mêmes valeurs, et le
  mot de passe n'est lu par aucun des deux (guide 05).
- `rollout status` est en `continue-on-error` : la readiness refuse tant que l'index n'existe
  pas dans RDS (guide 04). Le workflow constate l'état des pods, il ne décide pas à votre
  place qu'un déploiement a échoué.

## Exécution

**1. Poser l'ARN du rôle dans le dépôt** (une fois, après le bootstrap) :

```bash
ROLE_ARN=$(cd infra/terraform/bootstrap && terraform output -raw github_deploy_role_arn)
gh variable set AWS_DEPLOY_ROLE_ARN --body "$ROLE_ARN"
gh variable list
```

**2. Vérifier que le cluster connaît le rôle** (environnement allumé) :

```bash
aws eks list-access-entries --cluster-name llm-testbench-dev --output table
```

Attendu : votre identité (créateur du cluster) et le rôle `llm-testbench-github-deploy`.

**3. Déclencher et suivre** :

```bash
make deploy-trigger                 # gh workflow run deploy.yml --ref main
gh run watch                        # ou : gh run list --workflow=deploy.yml
```

Attendu, dans le journal du job : `Assumed role: arn:aws:sts::<compte>:assumed-role/
llm-testbench-github-deploy/GitHubActions`, un push ECR avec le tag = 7 caractères du SHA,
`Release "api" has been upgraded`, puis les pods. Si l'index n'est pas encore dans RDS, le
rollout expire et le job reste vert avec l'avertissement : c'est voulu.

**4. Lire la trace côté AWS** — c'est l'intérêt de l'OIDC :

```bash
aws cloudtrail lookup-events --lookup-attribute AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
  --max-results 3 --query 'Events[].{time:EventTime,who:Username}' --output table
```

Attendu : une ligne par exécution du workflow, avec `GitHubActions` comme nom de session.
CloudTrail garde aussi le `sub` du jeton dans le détail de l'événement : on sait quel dépôt
et quelle branche ont déployé, ce qu'une clé partagée ne dira jamais.

**5. Déployer un rollback** : relancez le workflow sur un commit antérieur (`gh workflow run
deploy.yml --ref <sha>`)… et constatez qu'il est refusé : le `sub` d'un SHA n'est pas celui de
`main`. Le rollback se fait par un `git revert` poussé sur `main`, puis le workflow. C'est une
contrainte choisie : on ne déploie que ce qui est sur la branche.

## Les pièges

- **L'endpoint public du cluster reste ouvert** (`public_access_cidrs = ["0.0.0.0/0"]`) : les
  runners GitHub n'ont pas d'IP fixe, et EKS n'accepte qu'une poignée de CIDR. L'accès est
  authentifié par IAM et journalisé ; ce n'est pas une porte ouverte, c'est une porte avec un
  badge. La vraie fermeture passe par le mode pull (GitOps) ou un runner dans le VPC — et le
  jour où elle est faite, `make deploy` depuis votre poste doit passer par la même voie.
- **Le moindre privilège sur le cluster** : `AmazonEKSEditPolicy` limitée au namespace
  `llm-testbench` ne suffit pas, parce que le workflow crée le namespace (ressource de
  cluster) et des `ExternalSecret` (CRD, hors des rôles `edit` standard sauf agrégation).
  La réponse propre : namespace créé par Terraform ou `cluster-addons`, politique `Edit` sur le
  namespace, et un `ClusterRole` agrégé pour `external-secrets.io` — trois pièces pour un
  cluster à un seul utilisateur. Noté, pas fait.
- **`id-token: write` manquant** : l'erreur dit « Credentials could not be loaded » ou parle
  d'audience. Vérifiez d'abord le bloc `permissions`.
- **Le `sub` doit correspondre exactement** : un workflow déclenché sur une autre branche, ou
  avec un `environment:` GitHub, change le `sub` (`repo:...:environment:dev`). La politique de
  confiance est le seul endroit qui le dit.
- **Les empreintes du fournisseur OIDC** : AWS ne s'en sert plus pour GitHub (chaîne de
  confiance publique), mais la ressource Terraform les exige. Si GitHub change de certificat
  intermédiaire, rien ne casse ; si la liste est vide, l'apply échoue.
- **Un fournisseur OIDC par URL et par compte** : un second `terraform apply` depuis un autre
  projet échoue avec `EntityAlreadyExists`. On importe (`terraform import ... <arn>`), on ne
  duplique pas.
- **`rollout status` vert ne veut pas dire « ça marche »** : il dit que les pods sont prêts.
  `/readyz` et `/sources` (guide 04) disent si l'API répond vraiment.

## Questions d'entretien

<details><summary><b>1. Comment une CI s'authentifie-t-elle auprès d'un cloud sans clé stockée ?</b></summary>

Par fédération d'identité : la CI émet un jeton OIDC signé qui décrit le job (dépôt, branche,
déclencheur), le cloud a été configuré pour faire confiance à cet émetteur, et échange le jeton
contre des identifiants temporaires d'un rôle dont la politique de confiance filtre sur les
claims du jeton. Rien n'est stocké ; chaque échange est journalisé avec l'identité du job.
</details>

<details><summary><b>2. Que mettez-vous dans la politique de confiance, et pourquoi le `sub` ?</b></summary>

L'audience (`sts.amazonaws.com`) et le `sub`, qui encode dépôt + référence. Sans condition sur
le `sub`, n'importe quel dépôt GitHub au monde pourrait assumer le rôle : le fournisseur OIDC
est le même pour tous. C'est l'erreur de configuration la plus fréquente de ce mécanisme.
</details>

<details><summary><b>3. IAM contre RBAC Kubernetes : qui décide quoi ?</b></summary>

IAM décide qui peut *parler* à l'API EKS (`eks:DescribeCluster` pour obtenir le kubeconfig,
puis le jeton signé par IAM). Les access entries, ou l'ancien `aws-auth`, font le pont : elles
associent une identité IAM à des droits Kubernetes (politiques EKS prédéfinies ou groupes RBAC).
Ensuite, c'est RBAC Kubernetes qui décide de chaque verbe sur chaque ressource.
</details>

<details><summary><b>4. Push ou pull pour déployer sur un cluster ?</b></summary>

Push (ce workflow) : la CI pousse une release dans le cluster ; simple, mais la CI a besoin
d'un accès réseau et de droits sur le cluster. Pull (GitOps) : un opérateur dans le cluster
observe un dépôt ou un registre et réconcilie ; le cluster n'expose rien, l'état désiré est
dans git, et le drift se voit. À un seul service et un cluster éphémère, push ; dès qu'il y a
plusieurs environnements ou un endpoint privé, pull.
</details>

<details><summary><b>5. Pourquoi l'image est-elle construite sur un runner arm64 ?</b></summary>

Parce que les nœuds sont Graviton (arm64). Une image amd64 ne démarre pas (`exec format
error`) ; une construction croisée sous QEMU marche mais prend dix fois plus de temps et
tombe sur des roues Python sans variante arm64. Le runner natif supprime le problème, et c'est
aussi ce que vous avez sur un Mac Apple Silicon : une seule architecture de bout en bout.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas de GitOps (Argo CD, Flux)** : un opérateur de plus sur un cluster qu'on détruit tous
  les soirs ; revu en phase 5 avec le canary (Argo Rollouts), qui en a vraiment besoin.
- **Pas d'environnement GitHub avec approbation** : un seul humain ; la protection serait
  théâtrale. Le jour où un second contributeur arrive, `environment: dev` avec relecteur
  obligatoire, et le `sub` de la politique de confiance change avec (pièges).
- **Pas de signature d'image (cosign) ni de SBOM** : rien ne consomme la signature ; à
  faire quand une politique d'admission (Kyverno) la vérifiera. Le scan ECR à la poussée,
  lui, est actif (guide 03).
- **Pas de déploiement automatique sur push** : le cluster n'est pas toujours là. Quand il
  le sera (phase 5, trafic synthétique continu), ce workflow gagne un `on: push` et un
  `paths:` sur `src/`, `infra/helm/`, `Dockerfile`.
- **Pas de restriction de l'endpoint à une IP** : voir les pièges, et ADR 009.
