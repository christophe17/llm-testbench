# Terraform — AWS `eu-west-3`

**Statut phase 0 : écrit, relu, PAS appliqué** (compte AWS en cours de création).
Premier `apply` en phase 1.

## Organisation

```
bootstrap/   # bucket S3 d'état (chiffré, versionné, lock natif S3) — appliqué une fois, état local
envs/dev/    # l'environnement de dev complet, à plat
envs/prod/   # (phase 5+) — les ressources partagées seront extraites en modules à ce moment-là
```

Choix assumé : `envs/dev` utilise les modules communautaires `terraform-aws-modules`
(vpc, eks) plutôt que des modules maison — moins de code à maintenir, qualité
production, et l'infra ne doit pas devenir le sujet. L'extraction en modules maison
n'arrivera qu'avec le besoin réel (création de `prod`).

## Workflow

```bash
cd infra/terraform/bootstrap && terraform init && terraform apply   # une seule fois
cd ../envs/dev
terraform init -backend-config="bucket=<bucket-état>"               # après bootstrap
terraform apply                                                     # = make infra-up (phase 1)
terraform destroy                                                   # = make infra-down
```

## Coûts estimés (`eu-west-3`, si allumé 24/7 — d'où le up/down)

| Ressource | Coût 24/7 | Note |
|---|---|---|
| EKS control plane | ~73 $/mois | 0,10 $/h — LA raison du `infra-down` |
| NAT Gateway (×1) | ~35 $/mois + data | un seul NAT assumé en dev ; poste dormant classique |
| Nœuds (2× t4g.medium spot) | ~20–30 $/mois | arm64 (Graviton), spot en dev |
| RDS db.t4g.micro | ~13 $/mois | arrêtable (`aws rds stop-db-instance`, max 7 j) |
| S3 + ECR | < 2 $/mois | négligeable au volume du projet |
| **Total si on laisse tourner** | **~145 $/mois** | **objectif réel : < 30 $/mois avec up/down** |

Rythme de travail réel : dev quotidien sur k3d, `infra-up` ponctuel pour valider
les déploiements, `infra-down` systématique ensuite.
