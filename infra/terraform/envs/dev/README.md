# Environnement `dev` — EKS, RDS pgvector, ECR, S3, Secrets Manager

Un environnement **éphémère** : `make infra-up` le crée en ~20 minutes, `make infra-down`
le détruit entièrement (base incluse, sans snapshot). Rien ne doit rester allumé sans
raison. Guides pas à pas : `docs/infra/02` à `06`.

## Coût estimé (eu-west-3, tarifs publics relevés le 2026-09-03, à vérifier sur Cost Explorer)

| Module | Ressource | Allumé | Éteint |
|---|---|---|---|
| eks | plan de contrôle | ~0,10 $/h | 0 |
| eks | 2 × t4g.medium à la demande | ~0,08 $/h | 0 |
| network | NAT Gateway (`nat_gateway = "single"`) | ~0,05 $/h + 0,05 $/Go | 0 |
| rds | db.t4g.micro + 20 Go gp3 | ~0,02 $/h + ~2,3 $/mois | 0 |
| ecr | images (≤ 10 conservées) | ~0,10 $/Go/mois | idem tant que non détruit |
| secrets | 4 secrets Secrets Manager | ~1,60 $/mois | 0 après `infra-down` |
| s3 | bucket de travail | ~0,02 $/Go/mois | 0 après `infra-down` |
| **Total** | | **~0,25 $/h ≈ 6 $/jour** | **~0 $** |

Une journée de test = ~6 $. Un mois oublié = ~180 $ : c'est pour ça que l'alerte de
budget (guide 00) existe avant cet environnement.
