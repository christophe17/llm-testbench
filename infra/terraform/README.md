# Infra Terraform

## État en phase 0

Seul le module `bootstrap/` existe : bucket S3 d'état (chiffré, versionné, verrouillage
natif S3) et alerte de budget mensuelle. Les modules d'environnement (`envs/dev`,
`envs/prod` : réseau, EKS, ECR, RDS pgvector, S3) arrivent en phase 1, quand il y a
quelque chose à déployer — décision et coûts détaillés dans `docs/adr/002`.

## Lancer le bootstrap (une fois)

Prérequis : compte AWS créé, identifiants configurés (`aws configure` ou SSO), Terraform ≥ 1.10.

```bash
cd infra/terraform/bootstrap
terraform init
terraform apply -var "alert_email=vous@example.com"
```

L'état du bootstrap reste **local** (`terraform.tfstate` dans ce dossier, ignoré par git) :
c'est le module qui crée le bucket d'état, il ne peut pas y stocker le sien. Ses ressources
sont stables et peu nombreuses ; si le fichier d'état local est perdu, `terraform import`
les récupère en quelques minutes.

## Coût mensuel estimé du bootstrap

| Ressource | Coût |
|---|---|
| Bucket S3 d'état (quelques ko) | ~0 € |
| AWS Budgets (2 premiers budgets) | 0 € |
| **Total** | **~0 €/mois** |
