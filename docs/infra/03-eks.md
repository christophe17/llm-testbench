# Guide 03 — EKS : plan de contrôle, nœuds Graviton, accès, identités de pods, déploiement

**Durée** : 45 minutes dont ~20 d'attente Terraform. **Prérequis** : guides 00 à 02.
**Coût** : ~0,25 $/h allumé (README de l'environnement) ; **`make infra-down` en fin de
session**. **Code** : `infra/terraform/envs/dev/eks.tf`, `iam.tf`, `outputs.tf`, cibles
`make infra-up`, `kubeconfig`, `cluster-addons`, `deploy`.

---

## Le problème

Faire tourner Kubernetes soi-même, vous savez faire. La question sur AWS est *ce qu'on
délègue* : le plan de contrôle (EKS le gère, 0,10 $/h), les nœuds (groupes managés,
Fargate, ou Auto Mode), les add-ons (CNI, DNS, proxy, métriques), et surtout **comment
un pod obtient des droits AWS** sans clé partagée — le point qui bloque tout le monde et
la première question d'entretien sur EKS.

## Les options

**Les nœuds.**

| Option | Verdict |
|---|---|
| **Groupe de nœuds managé** (Graviton `t4g.medium`) | **Retenu** : AWS gère l'AMI et les mises à jour, on garde le contrôle du dimensionnement. Graviton : ~20 % moins cher qu'x86 et **même architecture que l'image construite sur Mac M1** — pas de build croisé. |
| Fargate | Pas de nœud à gérer, mais démarrage lent, pas de volumes, pas de DaemonSet : mal adapté à une API à probes et à Langfuse. |
| EKS Auto Mode | Karpenter et les add-ons gérés par AWS, facturé en plus par nœud. Séduisant, mais il cache précisément ce qu'on veut apprendre ici. |

**Les identités de pods.**

| Option | Verdict |
|---|---|
| Clé AWS dans un Secret | Jamais : une clé partagée, sans expiration, dans le cluster. |
| IRSA (rôle par ServiceAccount via OIDC) | L'ancien standard, encore requis par certains charts ; annotation sur le ServiceAccount, fournisseur OIDC par cluster. |
| **EKS Pod Identity** | **Retenu** : une association (cluster, namespace, ServiceAccount) → rôle, créée par Terraform ; aucune annotation, aucun OIDC à gérer. L'agent est un add-on. |

**L'accès humain au cluster.**

| Option | Verdict |
|---|---|
| ConfigMap `aws-auth` | En voie de disparition ; les cours l'enseignent encore. |
| **Access entries** (`authentication_mode = "API"`) | **Retenu** : les droits d'accès sont des ressources AWS, pas un YAML dans le cluster. |

## Lecture guidée du code réel

**[`eks.tf`](../../infra/terraform/envs/dev/eks.tf)** :

- `kubernetes_version = "1.33"` : chaque version a ~14 mois de support standard, puis le
  **support étendu est facturé** six fois plus cher. Une variable, pour monter de version
  délibérément.
- `endpoint_public_access` + `endpoint_private_access` : l'API Kubernetes est joignable
  de votre Mac (public, filtré par `public_access_cidrs`) et des nœuds (privé).
- `authentication_mode = "API"` et `enable_cluster_creator_admin_permissions = true` :
  l'identité qui lance `terraform apply` devient administrateur du cluster par une access
  entry — c'est ce qui rend `kubectl` possible dès la fin de l'apply.
- `enable_irsa = true` : le fournisseur OIDC existe quand même, pour les charts qui ne
  parlent pas encore Pod Identity.
- `create_kms_key = true` : chiffrement des secrets Kubernetes au repos avec une clé KMS
  dédiée (~1 $/mois).
- `enabled_log_types` : journaux du plan de contrôle (API, audit, authentification) dans
  CloudWatch, gardés 7 jours.
- `addons` : les cinq add-ons managés. `before_compute = true` pour le CNI et l'agent
  Pod Identity : ils doivent exister avant les nœuds, sinon les premiers pods démarrent
  sans réseau ou sans identité. **`metrics-server` en add-on managé** : c'est lui que
  l'HPA du chart (guide 06) interroge.
- `eks_managed_node_groups.default` : AMI Amazon Linux 2023 **arm64**, `t4g.medium`
  (2 vCPU, 4 Go), 1 à 3 nœuds, 2 au démarrage, disque de 30 Go.

**[`iam.tf`](../../infra/terraform/envs/dev/iam.tf)** — la partie à lire lentement :

- `pod_identity_trust` : la politique de confiance que tout rôle Pod Identity porte —
  le service `pods.eks.amazonaws.com` peut assumer le rôle et étiqueter la session.
- Rôle `api` : `bedrock:InvokeModel` et `InvokeModelWithResponseStream` sur les modèles
  de fondation de la région et sur les profils d'inférence `eu.*` (les modèles Claude en
  Europe sont souvent servis par un profil inter-régions UE). Rien d'autre.
- Rôle `external_secrets` : lire les secrets sous le préfixe `llm-testbench/dev/*`,
  et seulement ceux-là.
- Deux `aws_eks_pod_identity_association` : (namespace `llm-testbench`, ServiceAccount
  `api`) → rôle API ; (namespace `external-secrets`, ServiceAccount `external-secrets`)
  → rôle ESO. Le nom du ServiceAccount de l'API est le nom de la release Helm (`api`),
  d'où `var.api_service_account`.

**[`outputs.tf`](../../infra/terraform/envs/dev/outputs.tf)** — ce que les cibles `make`
consomment : l'URL ECR, la commande `update-kubeconfig`, les noms des secrets à remplir.

## Exécution

**1. Créer l'environnement** (~20 minutes ; le plan de contrôle EKS est la partie longue).

```bash
make infra-up
```

Répondez `yes`. À la fin, le Makefile enchaîne `make kubeconfig`. Vérifiez :

```bash
kubectl config current-context           # arn:aws:eks:eu-west-3:<compte>:cluster/llm-testbench-dev
kubectl get nodes -o wide                 # 2 nœuds Ready, ARCH arm64
kubectl get pods -A                       # coredns, kube-proxy, aws-node, eks-pod-identity-agent, metrics-server
kubectl top nodes                         # metrics-server répond
```

**2. Les add-ons hors Terraform** : External Secrets Operator (Helm) et le magasin de
secrets.

```bash
make cluster-addons
kubectl -n external-secrets get pods
kubectl get clustersecretstore aws-secrets-manager     # READY True
```

`READY True` prouve la chaîne complète : le pod ESO a obtenu, par Pod Identity, des
identifiants temporaires lui permettant de lister nos secrets. Aucune clé n'a été
créée nulle part.

**3. Renseigner les secrets** (guide 05, à faire maintenant si vous voulez un `/chat`
fonctionnel) puis **déployer l'API** :

```bash
make deploy
kubectl -n llm-testbench get pods -w
```

`make deploy` : connexion à ECR, build de l'image (arm64, comme les nœuds), push au SHA
git, `helm upgrade` avec `values-dev.yaml`. Comme en local, le pod restera `0/1` tant
que l'index n'existe pas dans RDS : c'est le guide 04.

**4. Vérifier l'identité de pod de l'API**, sans clé :

```bash
kubectl -n llm-testbench exec deploy/api -- env | grep AWS_CONTAINER_CREDENTIAL_FULL_URI
```

Cette variable, injectée par l'agent Pod Identity, est l'endroit où le SDK AWS ira
chercher des identifiants temporaires pour le rôle `api`. Le provider Bedrock de la
couche LLM (backend `bedrock`, `config/llm_backends.toml`) s'en sert tel quel.

**5. En fin de session :**

```bash
make infra-down
```

Vérifiez sur Cost Explorer le lendemain : rien ne doit apparaître hormis les secrets
(centimes) et, éventuellement, des logs CloudWatch résiduels.

## Les pièges

- **Le support étendu EKS** : une version qui passe en support étendu coûte 0,60 $/h au
  lieu de 0,10 $/h, sans prévenir autrement que par un e-mail. Mettez la version à jour
  avant l'échéance (la variable existe pour ça).
- **`before_compute`** : oublié, les premiers nœuds démarrent avant le CNI, les pods
  système échouent, puis tout finit par converger — après vingt minutes de confusion.
- **L'access entry du créateur** : si `terraform apply` est lancé par une autre identité
  que celle de votre `kubectl` (un rôle assumé, par exemple), vous n'aurez pas accès au
  cluster. Ajoutez des `access_entries` pour les autres identités.
- **Pod Identity ne marche que pour les pods lancés après l'association**. Un pod
  déjà en marche ne reçoit pas l'identité : redémarrez-le.
- **Une image amd64 sur des nœuds Graviton** ne démarre pas (`exec format error`).
  L'image du Mac est arm64 ; si vous passez à des nœuds x86, `docker buildx build
  --platform linux/amd64`.
- **`make infra-down` peut échouer sur des ressources créées par Kubernetes** (un
  LoadBalancer, des volumes EBS) que Terraform ne connaît pas. Supprimez d'abord les
  Services de type LoadBalancer et les PVC, puis relancez.
- **Les logs CloudWatch du plan de contrôle** persistent après la destruction (groupe de
  logs à rétention 7 jours) : quelques centimes, mais visibles sur la facture.

## Questions d'entretien

<details><summary><b>1. Comment un pod obtient-il des droits AWS, et pourquoi pas une clé ?</b></summary>

Par une identité de pod : le ServiceAccount du pod est associé à un rôle IAM, l'agent
sur le nœud fournit des identifiants temporaires que le SDK récupère automatiquement.
Une clé statique ne expire pas, se partage entre tous les pods qui la lisent, et fuit
avec n'importe quel `kubectl get secret`. Deux mécanismes : IRSA (OIDC, annotation sur
le ServiceAccount) et Pod Identity (association AWS, sans annotation), le second
remplaçant progressivement le premier.
</details>

<details><summary><b>2. Access entries contre aws-auth ?</b></summary>

`aws-auth` est un ConfigMap dans le cluster qui mappe des identités IAM à des groupes
Kubernetes : modifiable par quiconque édite le ConfigMap, invisible d'IAM, facile à
casser (une erreur de YAML et plus personne n'entre). Les access entries sont des
ressources AWS gérées par API, avec des politiques prédéfinies (admin, view…), auditées
par CloudTrail.
</details>

<details><summary><b>3. Quand choisir Fargate, un groupe managé, ou Karpenter ?</b></summary>

Fargate pour des charges isolées, sans DaemonSet ni volume, où l'on ne veut aucun nœud
à gérer. Groupe managé pour un cluster stable à la taille prévisible. Karpenter quand la
charge varie et que le choix d'instance (famille, Spot) doit se faire à la demande :
c'est le mot-clé des offres, et le sujet de la phase 5 quand il y aura du trafic à
absorber.
</details>

<details><summary><b>4. Que contient le prix d'EKS ?</b></summary>

0,10 $/h pour le plan de contrôle quelle que soit la taille, puis les nœuds au tarif EC2,
le stockage EBS, la NAT, les équilibreurs, et 0,60 $/h en support étendu. Le plan de
contrôle seul est ~73 $/mois : c'est pour ça qu'un cluster de dev doit s'éteindre.
</details>

<details><summary><b>5. Comment expose-t-on un service sur EKS ?</b></summary>

Un `Service type: LoadBalancer` crée un équilibreur (classique par défaut, NLB/ALB avec
l'AWS Load Balancer Controller) dans les sous-réseaux tagués `kubernetes.io/role/elb`.
Un Ingress demande le contrôleur. Chaque équilibreur coûte ~0,02 $/h : en dev, le
port-forward suffit.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas de Karpenter** : un groupe de nœuds fixe suffit tant qu'il n'y a pas de charge
  variable (phase 5).
- **Pas d'AWS Load Balancer Controller ni d'Ingress** : port-forward en dev ; l'exposition
  publique arrivera avec l'UI de chat (phase 5).
- **Pas de Spot** : les nœuds Spot coûtent ~70 % de moins mais peuvent disparaître ;
  pertinent pour le générateur de trafic ou les jobs d'évaluation, pas pour l'API en
  phase 1.
- **Pas d'IAM Identity Center** : un seul humain sur un compte personnel ; la réponse de
  production reste notée (guide 00).
- **Pas de pipeline de déploiement** : `make deploy` depuis le poste ; le rôle OIDC pour
  GitHub Actions viendra si un jour la CI déploie (ADR 003 : elle reste hors ligne).
