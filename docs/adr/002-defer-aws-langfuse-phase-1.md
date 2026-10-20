# ADR 002 — Cloud AWS et Langfuse reportés en phase 1, bootstrap seul en phase 0

- **Date** : 2026-08-26
- **Statut** : accepté

## Contexte

Le brief place « infra Terraform + Helm » et Langfuse en phase 0. Or rien ne se déploie
avant la phase 1 (aucune API), et rien n'appelle un LLM avant la phase 1 (rien à tracer).
Le brief interdit par ailleurs les postes dormants. Langfuse v3 self-hosted traîne
ClickHouse, Redis et un stockage objet — lourd pour un k3d sur Mac, à vide.

## Options considérées

1. **Tout monter en phase 0** (EKS, RDS, Langfuse) — conforme à la lettre du brief, mais
   paie un cluster et opère une stack d'observabilité sans aucune charge à observer.
2. **Bootstrap seul en phase 0, le reste en phase 1** — l'alerte de budget existe avant
   le premier euro de cloud ; l'infra arrive quand quelque chose la consomme.
3. **Zéro AWS en phase 0** — repousse aussi l'alerte de budget, qui est justement la
   protection qu'on veut en place avant tout le reste.

## Décision

Option 2. Phase 0 : module `infra/terraform/bootstrap/` uniquement (bucket d'état S3
chiffré/versionné avec verrouillage natif S3 — pas de DynamoDB, Terraform ≥ 1.10 — et
budget mensuel 55 USD ≈ 50 € avec alertes 80 %/100 % réel + 100 % prévisionnel). L'état
du bootstrap reste local (il crée le bucket d'état, œuf et poule). Langfuse s'installe
en phase 1 avec le premier appel LLM. Le dev local (k3d + Postgres/pgvector) est, lui,
bien livré en phase 0 : les loaders et la CI n'en dépendent pas, mais la phase 1 le
consommera dès son premier jour.

## Conséquences

Coût cloud de la phase 0 : ~0 €/mois. La phase 1 devra livrer : réseau + EKS + ECR + RDS
pgvector (Terraform, backend S3 du bootstrap), rôle OIDC GitHub Actions si la CI doit
déployer, et l'arbitrage Langfuse v3 complet vs alternative légère en local. À revisiter
si la phase 1 glisse : l'alerte de budget, elle, est déjà en place.
