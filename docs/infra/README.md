# Guides d'infrastructure

Les guides de ce dossier expliquent l'infra du banc d'essai avec le même contrat pédagogique
que les notebooks : le problème, les options, lecture guidée du **vrai code** (HCL, YAML,
Makefile), exécution pas à pas avec les sorties attendues et les contrôles à faire, les
pièges, les questions d'entretien, et ce qu'on n'a pas fait. Ils s'exécutent en CLI, à la
main : ils ont besoin d'identifiants et d'un cluster, ce qu'une CI hors ligne n'a pas.

Calibrage : le vocabulaire Kubernetes et Terraform est supposé acquis ; chaque choix AWS,
chaque arbitrage et chaque piège sont explicités. Les priorités suivent
`docs/aws-competences.md`.

| # | Guide | Ce qu'on construit | Coût |
|---|---|---|---|
| 00 | [Bootstrap](00-bootstrap.md) | bucket d'état Terraform, alerte de budget | ~0 €/mois |
| 01 | Dev local k3d | cluster local, Postgres/pgvector, Tilt | 0 € |
| 02 | Réseau VPC | sous-réseaux, routage, NAT ou endpoints | à chiffrer |
| 03 | EKS | plan de contrôle, nœuds, accès, identités de pods | à chiffrer |
| 04 | RDS pgvector | base managée, extension, accès depuis le cluster | à chiffrer |
| 05 | Secrets | Secrets Manager, External Secrets | à chiffrer |
| 06 | Chart Helm de l'API | probes, HPA, PDB, ressources | 0 € |
| 07 | Observabilité | Langfuse, collecteur OTel | à chiffrer |
| 08 | Coûts | coût par module, `make infra-up` / `make infra-down` | — |

Les guides 01 à 08 arrivent au fil de la phase 1, dans l'ordre de construction.
