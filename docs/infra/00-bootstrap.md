# Guide 00 — Bootstrap AWS : l'état distant et l'alerte de budget avant le premier euro

**Durée** : 15 minutes. **Prérequis** : compte AWS, AWS CLI configurée, Terraform ≥ 1.10.
**Coût** : ~0 €/mois. **Code** : `infra/terraform/bootstrap/` (trois fichiers, ~100 lignes).

Ce guide s'exécute une seule fois par compte. Tout ce qui suit dans la phase 1 (réseau, EKS,
RDS) stocke son état dans le bucket créé ici et vit sous l'alerte de budget créée ici.

---

## Le problème

Deux problèmes d'œuf et de poule, à régler avant toute autre ressource cloud.

**1. L'état Terraform a besoin d'un endroit où vivre.** Terraform garde la correspondance
entre le code et les ressources réelles dans un fichier d'état. En local, ce fichier est un
point de défaillance unique : un disque perdu et Terraform ne sait plus ce qu'il a créé ; deux
`apply` concurrents et l'état est corrompu. Il faut donc un stockage distant, chiffré,
versionné et verrouillable. Mais ce stockage est lui-même une ressource cloud, que quelque
chose doit créer.

**2. L'alerte de budget doit exister avant la première ressource facturée.** Le brief interdit
les postes dormants. Or les postes dormants sont silencieux par nature : une NAT Gateway
oubliée coûte ~35 €/mois sans jamais se signaler, un plan de contrôle EKS ~70 €/mois. Sans
alerte, on découvre la dérive sur la facture du mois suivant.

## Les options

**Pour l'état.**

| Option | Verdict |
|---|---|
| Fichier local | Refusé : point de défaillance unique, pas de verrou, pas d'historique. Accepté *uniquement* pour ce module-ci (voir plus bas). |
| S3 + table DynamoDB pour le verrou | La réponse classique jusqu'en 2024. Deux services à gérer pour un verrou. Encore dans la plupart des tutoriels. |
| **S3 avec verrou natif** (`use_lockfile`, Terraform ≥ 1.10) | **Retenu.** Le verrou est un objet `.tflock` écrit conditionnellement dans le bucket lui-même. Un seul service. |
| HCP Terraform (ex-Terraform Cloud) | Refusé : dépendance à un SaaS pour un projet qui veut montrer qu'il sait opérer. |

**Pour l'alerte.**

| Option | Verdict |
|---|---|
| **AWS Budgets** | **Retenu.** Gratuit pour les deux premiers budgets, seuils au réel et au prévisionnel, e-mail sans infrastructure. |
| Alarme CloudWatch sur la métrique de facturation | Métrique uniquement en `us-east-1`, à activer à la main dans la console, pas de prévisionnel. |
| Cost Anomaly Detection | Complémentaire (détection statistique, gratuite), pas un plafond. Candidat pour la phase 5. |

## Lecture guidée du code réel

Ouvrez [`infra/terraform/bootstrap/main.tf`](../../infra/terraform/bootstrap/main.tf).

**Le bloc `terraform`** fixe `required_version = ">= 1.10"`. Ce n'est pas une coquetterie : le
verrou natif S3 n'existe pas avant. Le provider AWS est épinglé en `~> 5.60` (toute 5.x à
partir de 5.60, jamais 6.x) : une montée de version majeure du provider se décide, elle ne
s'attrape pas.

**Le bloc `provider`** porte des `default_tags`. Chaque ressource créée par ce module hérite
de `Project`, `ManagedBy`, `Module`. C'est ce qui rendra possible, plus tard, un coût *par
module* dans Cost Explorer : sans tags, la facture est un total indifférencié.

**`data "aws_caller_identity"`** lit l'identifiant du compte courant. Il sert au nom du
bucket : les noms de buckets S3 sont uniques *au monde*, pas par compte. Suffixer par
l'identifiant de compte évite la collision avec le `llm-testbench-tfstate` de quelqu'un
d'autre.

**Le bucket** a un `lifecycle { prevent_destroy = true }`. Terraform refusera de le détruire,
même sur un `terraform destroy` explicite. C'est voulu : ce bucket contiendra l'état de tout
le reste, sa destruction accidentelle serait le pire incident possible du projet.

**Trois ressources annexes** configurent le bucket. Depuis le provider 4.x, ces réglages sont
des ressources séparées, plus des arguments du bucket :

- `aws_s3_bucket_versioning` : chaque écriture d'état garde la version précédente. Un
  `apply` raté se répare en restaurant la version d'avant.
- `aws_s3_bucket_server_side_encryption_configuration` : chiffrement `aws:kms` avec la clé
  gérée par AWS (`aws/s3`). Chiffré au repos sans créer de clé, donc sans le coût mensuel
  d'une clé personnalisée. `bucket_key_enabled = true` réduit le nombre d'appels KMS
  facturés. L'état Terraform mérite ce soin : il contiendra un jour le mot de passe RDS en
  clair.
- `aws_s3_bucket_public_access_block` : les quatre verrous anti-exposition publique. Un
  bucket d'état public est une fuite de secrets.

**Le budget** est en USD : AWS Budgets ne connaît pas l'euro (55 USD ≈ 50 €). Le bloc
`dynamic "notification"` déroule trois alertes à partir d'une liste : 80 % et 100 % du
**réel**, 100 % du **prévisionnel**. Le prévisionnel est le plus utile : AWS extrapole la
consommation du mois et prévient des jours avant que le réel ne crève le plafond.

**[`variables.tf`](../../infra/terraform/bootstrap/variables.tf)** : région, plafond, et
l'adresse e-mail d'alerte, seule variable sans défaut. **[`outputs.tf`](../../infra/terraform/bootstrap/outputs.tf)** :
le nom du bucket et un bloc `backend "s3"` prêt à coller dans les modules d'environnement,
avec `use_lockfile = true`.

## Exécution

**1. Vérifier l'identité et l'outillage.**

```bash
aws sts get-caller-identity
terraform version
```

Attendu : votre identifiant de compte et l'ARN de votre utilisateur ; Terraform ≥ 1.10.
Si `get-caller-identity` échoue, rien d'autre ne marchera : réglez `aws configure` d'abord.

**2. Fournir l'adresse d'alerte sans l'écrire dans un fichier.**

```bash
export TF_VAR_alert_email="vous@exemple.fr"
```

Terraform lit toute variable `TF_VAR_<nom>` de l'environnement. On évite ainsi un fichier
`terraform.tfvars` contenant une adresse personnelle dans un dépôt public (`*.tfvars` est
désormais ignoré par git, ceinture et bretelles). Sans cet export, `terraform apply` vous
demandera la valeur interactivement : ça marche aussi.

**3. Initialiser et planifier.**

```bash
make bootstrap-plan
```

`terraform init` télécharge le provider AWS et affiche `Terraform has been successfully
initialized!`. Le plan doit se terminer par :

```
Plan: 5 to add, 0 to change, 0 to destroy.
```

Cinq ressources : le bucket, son versioning, son chiffrement, son blocage d'accès public, le
budget. Si le chiffre diffère, arrêtez-vous et lisez le plan.

**4. Appliquer.**

```bash
make bootstrap-apply
```

Répondez `yes`. En fin d'exécution, deux sorties : `tfstate_bucket` et `backend_example`.
Notez le nom du bucket : `llm-testbench-tfstate-<identifiant de compte>`.

**5. Contrôler ce qui a été créé.** Ne croyez pas Terraform sur parole, interrogez AWS.

```bash
cd infra/terraform/bootstrap
BUCKET=$(terraform output -raw tfstate_bucket)
aws s3api get-bucket-versioning --bucket "$BUCKET"
aws s3api get-bucket-encryption --bucket "$BUCKET"
aws s3api get-public-access-block --bucket "$BUCKET"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws budgets describe-budgets --account-id "$ACCOUNT" \
  --query 'Budgets[].[BudgetName,BudgetLimit.Amount,BudgetLimit.Unit]' --output table
aws budgets describe-notifications-for-budget --account-id "$ACCOUNT" \
  --budget-name llm-testbench-monthly --output table
```

Attendu, dans l'ordre : `"Status": "Enabled"` ; `SSEAlgorithm: aws:kms` et
`BucketKeyEnabled: true` ; quatre `true` ; un budget `llm-testbench-monthly` à `55 USD` ;
trois notifications (`ACTUAL 80`, `ACTUAL 100`, `FORECASTED 100`).

**6. Regarder où est l'état de ce module.**

```bash
ls infra/terraform/bootstrap/terraform.tfstate
git check-ignore infra/terraform/bootstrap/terraform.tfstate
```

Il est **local**, et git l'ignore. C'est l'exception assumée : ce module crée le bucket
d'état, il ne peut pas y ranger le sien. Il ne contient que cinq ressources stables. S'il
est perdu, `terraform import` les récupère en quelques minutes (les identifiants sont le
nom du bucket et, pour le budget, `<compte>:llm-testbench-monthly`).

**7. Me dire que c'est fait**, avec le nom du bucket. Les modules `envs/dev` en ont besoin
pour leur bloc `backend`.

## Les pièges

- **L'alerte prévisionnelle est muette au début.** AWS a besoin d'environ cinq semaines
  d'historique de consommation pour produire une prévision. Sur un compte neuf, seules les
  alertes au réel fonctionnent le premier mois.
- **Un budget n'est pas un disjoncteur.** AWS Budgets rafraîchit ses données jusqu'à trois
  fois par jour : entre la dérive et l'e-mail, il peut s'écouler huit heures. Le vrai kill
  switch sur dérive de coût est un livrable de la phase 5, pas de ce guide.
- **`prevent_destroy` bloque aussi le ménage volontaire.** Pour supprimer réellement le
  bucket un jour : retirer le bloc `lifecycle`, vider le bucket *y compris toutes les
  versions* (un bucket versionné non vidé refuse la suppression), puis `destroy`.
- **La clé `aws/s3` n'est pas une clé à vous.** Chiffré, oui ; mais pas de rotation
  pilotée, pas de politique de clé, pas de partage inter-comptes. Suffisant pour un état
  Terraform personnel ; en entreprise, on passe à une clé gérée par le client.
- **Vos identifiants sont ceux d'un utilisateur IAM à clés longues.** Acceptable sur un
  compte personnel. La réponse de production est IAM Identity Center (SSO, identifiants
  temporaires) pour les humains et OIDC pour la CI. On y revient au guide 03.
- **Le fichier `.terraform.lock.hcl` est ignoré par git** depuis la phase 0. Pour ce module,
  c'est sans conséquence ; pour les modules d'environnement, on le versionnera avec les
  empreintes des deux plateformes (`darwin_arm64` pour vous, `linux_amd64` pour une CI
  future), sinon deux machines peuvent résoudre deux versions de provider différentes.
- **Le bucket est en `eu-west-3`, le budget est global.** AWS Budgets n'a pas de région :
  ne cherchez pas le budget dans la console Paris, il est dans « Billing and Cost
  Management ».
- **Un autre bucket d'état existe sur ce compte**, créé par un autre projet. Ce module n'y
  touche pas et crée le sien : un état par projet, jamais de partage.

## Questions d'entretien

<details><summary><b>1. Pourquoi un état distant, et que se passe-t-il sans verrou ?</b></summary>

L'état est la seule mémoire de Terraform : perdu, Terraform recréera tout en doublon.
Sans verrou, deux `apply` simultanés lisent le même état, écrivent chacun le leur, et le
second écrase les ressources créées par le premier dans l'état sans les détruire dans le
cloud : ressources orphelines, facturées, invisibles de Terraform.
</details>

<details><summary><b>2. S3 + DynamoDB ou verrou natif S3 : quelle différence ?</b></summary>

Même garantie (exclusion mutuelle des opérations), mécanisme différent : DynamoDB utilise
une table avec écriture conditionnelle ; le verrou natif utilise l'écriture conditionnelle
de S3 (`If-None-Match`) sur un objet `.tflock`. Le natif exige Terraform ≥ 1.10 et supprime
un service à gérer. Les deux peuvent coexister pendant une migration.
</details>

<details><summary><b>3. Le versioning du bucket d'état sert à quoi concrètement ?</b></summary>

À revenir en arrière après un `apply` qui a corrompu l'état, et à retrouver l'état d'avant
une manipulation `terraform state rm` malheureuse. C'est aussi une piste d'audit : qui a
changé quoi, quand.
</details>

<details><summary><b>4. Pourquoi chiffrer l'état, et SSE-S3 ou SSE-KMS ?</b></summary>

L'état contient des valeurs sensibles en clair : mots de passe de base de données, jetons,
adresses privées. SSE-S3 (AES-256 géré par S3) suffit à la conformité de base ; SSE-KMS
ajoute la traçabilité CloudTrail des accès à la clé et, avec une clé personnalisée, le
contrôle de sa politique. On a pris SSE-KMS avec la clé AWS : la trace sans le coût.
</details>

<details><summary><b>5. Comment gère-t-on le problème de l'œuf et de la poule du bootstrap ?</b></summary>

Trois réponses connues : état local assumé pour le seul module bootstrap (notre choix, avec
`import` comme plan de reprise) ; création manuelle du bucket puis import ; ou un premier
`apply` en local suivi d'une migration de l'état vers le bucket qu'il vient de créer
(`terraform init -migrate-state`). La troisième est élégante mais crée une dépendance
circulaire à expliquer à chaque reprise.
</details>

<details><summary><b>6. Une alerte de budget suffit-elle à maîtriser les coûts ?</b></summary>

Non : elle détecte, elle n'empêche pas, et avec un retard de plusieurs heures. La maîtrise
vient de l'architecture (rien de dormant : `make infra-down`), des tags pour attribuer, de
la détection d'anomalies pour les surprises, et d'un mécanisme d'arrêt automatique pour
les dérives rapides. Le budget est le filet, pas la ceinture.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas de DynamoDB** : le verrou natif suffit et c'est un service de moins.
- **Pas d'OIDC pour la CI** : la CI reste hors ligne et sans secret (ADR 003) ; le
  déploiement est manuel en phase 1. On créera le rôle OIDC le jour où un pipeline déploie.
- **Pas de clé KMS personnalisée** : pas de besoin de contrôle de politique de clé sur un
  compte personnel.
- **Pas de Cost Anomaly Detection** : complémentaire, à ajouter en phase 5 avec le reste
  de la maîtrise des coûts.
- **Pas d'IAM Identity Center** : compte personnel, un seul humain ; noté comme réponse de
  production au guide 03.

## Coût

| Ressource | Coût mensuel |
|---|---|
| Bucket S3 d'état (quelques ko, versionné) | ~0 € |
| Appels KMS sur la clé `aws/s3` | ~0 € (centimes au pire) |
| AWS Budgets (deux premiers budgets) | 0 € |
| **Total** | **~0 €** |
