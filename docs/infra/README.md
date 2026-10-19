# Guides d'infrastructure

Les guides de ce dossier expliquent l'infra du banc d'essai avec le même contrat pédagogique
que les notebooks : le problème, les options, lecture guidée du **vrai code** (HCL, YAML,
Makefile), exécution pas à pas avec les sorties attendues et les contrôles à faire, les
pièges, les questions d'entretien, et ce qu'on n'a pas fait. Ils s'exécutent en CLI, à la
main : ils ont besoin d'identifiants et d'un cluster, ce qu'une CI hors ligne n'a pas.

Calibrage : le vocabulaire Kubernetes et Terraform est supposé acquis ; chaque choix AWS,
chaque arbitrage et chaque piège sont explicités. La règle d'entrée d'un service AWS dans le
banc est dans `CLAUDE.md` §4 (ADR 009).

| # | Guide | Ce qu'on construit | Coût allumé |
|---|---|---|---|
| 00 | [Bootstrap](00-bootstrap.md) | bucket d'état Terraform, alerte de budget, rôle OIDC GitHub | ~0 €/mois |
| 01 | [Dev local k3d](01-dev-local-k3d.md) | cluster local, Postgres/pgvector, Tilt | 0 € |
| 02 | [Réseau VPC](02-reseau-vpc.md) | sous-réseaux, routage, NAT ou endpoints | ~0,05 $/h + trafic |
| 03 | [EKS](03-eks.md) | plan de contrôle, nœuds Graviton, accès, identités de pods | ~0,18 $/h |
| 04 | [RDS pgvector](04-rds-pgvector.md) | base managée, extension, accès depuis le cluster | ~0,02 $/h |
| 05 | [Secrets](05-secrets.md) | Secrets Manager, External Secrets, URL de base composée dans le cluster | ~1,60 $/mois |
| 06 | [Chart Helm de l'API](06-chart-helm-api.md) | probes, HPA, PDB, ressources | 0 € |
| 07 | [Observabilité](07-observabilite.md) | Langfuse, collecteur OTel | 0 € en local |
| 08 | [Coûts](08-couts.md) | coût par module, `make infra-up` / `make infra-down` | — |
| 09 | [Déploiement par GitHub Actions](09-deploiement-github-oidc.md) | rôle OIDC, build arm64, ECR, Helm, sans clé | 0 € |

Total de l'environnement `dev` allumé : ~0,25 $/h, ~6 $/jour ; éteint : ~0 $ (guide 08).
