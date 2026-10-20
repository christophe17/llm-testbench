# Guide 02 — Le réseau : VPC, sous-réseaux, NAT ou pas NAT

**Durée** : 20 minutes. **Prérequis** : guide 00 appliqué (bucket d'état). **Coût** : le
plan ne crée rien ; la NAT Gateway, si on la garde, coûtera ~0,05 $/h une fois appliquée
(guide 03). **Code** : `infra/terraform/envs/dev/network.tf`, `locals.tf`, `variables.tf`.

---

## Le problème

Un cluster a besoin de trois choses que le réseau doit séparer : des adresses **publiques**
pour ce qui reçoit du trafic d'Internet (équilibreurs de charge), des adresses **privées**
pour ce qui ne doit jamais être joignable de l'extérieur (nœuds, pods), et un coin encore
plus fermé pour la base. Et les nœuds privés ont quand même besoin de **sortir** :
tirer des images, appeler les API des providers LLM, joindre le plan de contrôle.

C'est ce dernier point qui coûte : la sortie d'un sous-réseau privé passe par une NAT
Gateway, facturée à l'heure et au gigaoctet, **qu'elle serve ou non**. C'est le poste
dormant numéro un des comptes AWS personnels.

## Les options

| Option | Coût | Verdict |
|---|---|---|
| Une NAT Gateway par AZ | ~0,10 $/h | La réponse production (pas de dépendance inter-AZ). Trop cher pour un dev éphémère. |
| **Une seule NAT Gateway** (`nat_gateway = "single"`) | ~0,05 $/h + 0,05 $/Go | **Défaut** : topologie de production (nœuds privés), coût acceptable pour quelques heures. |
| **Pas de NAT, nœuds en sous-réseaux publics** (`nat_gateway = "none"`) | 0 | Nœuds avec IP publique mais groupe de sécurité fermé en entrée. Topologie « dev », zéro coût dormant. |
| VPC endpoints (S3, ECR, Secrets Manager…) | ~0,01 $/h chacun | Réduit le trafic NAT, ne le supprime pas (les API LLM sont sur Internet). Reporté. |

Le choix est une variable : vous pouvez faire les deux et comparer sur Cost Explorer.

## Lecture guidée du code réel

**[`locals.tf`](../../infra/terraform/envs/dev/locals.tf)** — deux zones de disponibilité
(le minimum pour EKS, qui refuse une seule AZ), et trois familles de sous-réseaux
calculées avec `cidrsubnet` à partir du `/16` : publics en `10.42.0-1.0/24`, privés en
`10.42.10-11.0/24`, base en `10.42.20-21.0/24`. Calculer plutôt qu'écrire en dur : changer
le CIDR ne demande de toucher qu'une variable.

**[`network.tf`](../../infra/terraform/envs/dev/network.tf)** — le module
`terraform-aws-modules/vpc` (le plus utilisé de l'écosystème, ~240 variables ; on en
utilise douze) :

- `create_database_subnet_group = true` : le groupe de sous-réseaux qu'RDS exigera au
  guide 04, créé ici parce qu'il appartient au réseau.
- `enable_dns_hostnames` : sans lui, les endpoints privés (RDS, plan de contrôle) n'ont
  pas de nom résolvable dans le VPC.
- `enable_nat_gateway = (var.nat_gateway == "single")` et `single_nat_gateway = true` :
  une seule passerelle partagée par les deux AZ (le module en ferait une par AZ par
  défaut).
- `map_public_ip_on_launch` : en mode sans NAT, les nœuds reçoivent une IP publique au
  démarrage, sinon ils ne sortiraient jamais.
- **Les tags `kubernetes.io/role/elb` et `internal-elb`** : c'est ainsi que les
  contrôleurs Kubernetes (Service de type LoadBalancer, AWS Load Balancer Controller)
  savent dans quels sous-réseaux placer un équilibreur. Sans ces tags, un `Service
  type: LoadBalancer` reste en `<pending>` sans expliquer pourquoi.

**[`eks.tf`](../../infra/terraform/envs/dev/eks.tf)**, deux lignes seulement pour ce
guide : `subnet_ids` choisit les sous-réseaux publics ou privés pour les nœuds selon la
variable, et `control_plane_subnet_ids` place les interfaces du plan de contrôle en
privé dans tous les cas.

## Exécution

**1. Initialiser avec le backend du bootstrap.**

```bash
make infra-init
```

Le Makefile passe `-backend-config="bucket=llm-testbench-tfstate-<compte>"` : le nom du
bucket dépend du compte, il n'est jamais écrit dans le code. Attendu : téléchargement des
modules (vpc, eks, rds) et des providers, puis `Terraform has been successfully
initialized!`. Le fichier `.terraform.lock.hcl` est versionné avec les empreintes de
trois plateformes (Mac arm64, Linux amd64 et arm64) : une CI Linux résoudrait les mêmes
versions de providers que vous.

**2. Planifier l'environnement entier**, mais ne lire que le réseau pour l'instant :

```bash
make infra-plan 2>&1 | tee /tmp/plan.txt
grep -E "^  # module.vpc" /tmp/plan.txt
```

Attendu : un VPC, 6 sous-réseaux, une passerelle Internet, des tables de routage, une
Elastic IP et une NAT Gateway (en mode `single`), un groupe de sous-réseaux de base.
Comptez : environ 25 ressources pour le seul réseau, sur ~70 pour l'environnement.

**3. Essayer l'autre mode** sans rien créer :

```bash
cd infra/terraform/envs/dev && terraform plan -var nat_gateway=none | grep -E "nat_gateway|eip" ; cd -
```

Plus de NAT ni d'EIP dans le plan. Choisissez, puis notez votre choix dans
`terraform.tfvars` (ignoré par git) si vous vous écartez du défaut.

## Les pièges

- **La NAT Gateway se facture même sans trafic** : ~35 $/mois oubliée. C'est la raison de
  `make infra-down` et de l'alerte du guide 00.
- **Les nœuds publics ne sont pas « ouverts »** : une IP publique et un groupe de
  sécurité qui n'autorise rien en entrée, c'est joignable par personne. La différence
  avec le privé est la surface d'erreur (une règle de plus et c'est ouvert), pas
  l'exposition par défaut.
- **`0.0.0.0/0` sur l'endpoint public du plan de contrôle** (`public_access_cidrs`) : le
  défaut du projet pour simplifier ; en pratique, mettez votre IP en `/32`. L'API
  Kubernetes reste authentifiée, mais exposer le port d'authentification au monde entier
  n'est jamais gratuit.
- **Le `/16` est généreux à dessein** : les pods EKS consomment une IP du VPC chacun
  (CNI VPC). Un `/24` par sous-réseau privé, c'est ~250 pods par AZ : assez ici, court
  en production.
- **Les tags de sous-réseaux sont invisibles jusqu'au jour où ils manquent** : un
  LoadBalancer `<pending>` ou une erreur obscure du contrôleur. Ils sont dans le code,
  pas dans votre mémoire.

## Questions d'entretien

<details><summary><b>1. Public, privé, base : pourquoi trois familles ?</b></summary>

Trois politiques de routage : les publics ont une route vers la passerelle Internet
(ils reçoivent), les privés une route vers la NAT (ils sortent sans recevoir), la base
aucune route vers l'extérieur (elle ne fait ni l'un ni l'autre). Le groupe de sécurité
protège l'instance ; le sous-réseau protège de l'erreur de groupe de sécurité.
</details>

<details><summary><b>2. Comment réduire le coût de sortie d'un cluster privé ?</b></summary>

VPC endpoints pour les services AWS (S3 en gateway, gratuit ; ECR, Secrets Manager,
CloudWatch en interface, ~0,01 $/h chacun) pour que ce trafic ne passe plus par la NAT ;
une seule NAT en dev ; et surveiller le trafic NAT par gigaoctet, souvent dominé par les
pulls d'images (d'où l'endpoint ECR en premier).
</details>

<details><summary><b>3. Pourquoi EKS exige-t-il deux AZ ?</b></summary>

Le plan de contrôle managé est déployé en haute disponibilité par AWS sur plusieurs AZ ;
il a besoin de sous-réseaux dans au moins deux. Vos nœuds, eux, peuvent rester dans une
seule AZ si vous acceptez le risque.
</details>

<details><summary><b>4. Un pod sort par quelle adresse ?</b></summary>

En privé : par l'IP de la NAT Gateway (une seule adresse pour tout le cluster, pratique
pour une allowlist chez un fournisseur). En public sans NAT : par l'IP publique de son
nœud, qui change à chaque remplacement de nœud — impossible à mettre en allowlist.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas de VPC endpoints** : gain réel seulement avec du trafic AWS soutenu ; à mesurer
  en phase 5 avec le générateur de trafic.
- **Pas de flow logs** : utiles pour l'audit réseau, hors sujet en dev éphémère.
- **Pas d'IPv6** : aucun besoin, et le CNI VPC en double pile ajoute des cas à gérer.
- **Pas de NAT par AZ** : la haute disponibilité de la sortie n'a pas de sens pour un
  environnement qu'on détruit le soir.
