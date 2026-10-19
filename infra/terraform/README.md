# Infra Terraform

Deux modules, deux cycles de vie.

| Module | Contenu | État | Cycle de vie |
|---|---|---|---|
| `bootstrap/` | bucket S3 d'état (chiffré, versionné, verrou natif), alerte de budget, fournisseur OIDC GitHub et rôle de déploiement | **local** (il crée le bucket d'état, il ne peut pas y ranger le sien) | appliqué une fois par compte (guides 00 et 09) |
| `envs/dev` | VPC, EKS (Pod Identity, access entries), RDS pgvector, ECR, S3, Secrets Manager, rôles | S3, bucket du bootstrap | **éphémère** : `make infra-up` le matin, `make infra-down` le soir (guides 02 à 06, coûts au guide 08) |

Il n'y a pas d'environnement `prod` : le banc n'a pas d'utilisateurs, un second environnement
serait un poste dormant (ADR 009).

## Lancer le bootstrap (une fois)

Prérequis : compte AWS créé, identifiants configurés (`aws configure` ou SSO), Terraform ≥ 1.10.

```bash
export TF_VAR_alert_email="vous@exemple.fr"
make bootstrap-plan     # Plan: 8 to add
make bootstrap-apply
```

Si l'état local du bootstrap est perdu, `terraform import` récupère ses huit ressources en
quelques minutes (identifiants : nom du bucket, `<compte>:llm-testbench-monthly`, ARN du
fournisseur OIDC, nom du rôle).

## L'environnement dev

```bash
make infra-init         # backend S3 du bootstrap
make infra-plan
make infra-up           # ~20 minutes, puis kubeconfig
make cluster-addons     # External Secrets + ClusterSecretStore
make deploy             # ou : make deploy-trigger (GitHub Actions, guide 09)
make infra-down         # le soir
```

## Coût mensuel estimé du bootstrap

| Ressource | Coût |
|---|---|
| Bucket S3 d'état (quelques ko) | ~0 € |
| AWS Budgets (2 premiers budgets) | 0 € |
| Fournisseur OIDC et rôle IAM | 0 € |
| **Total** | **~0 €/mois** |

L'environnement dev : `envs/dev/README.md` (~0,25 $/h allumé, ~0 $ éteint).
