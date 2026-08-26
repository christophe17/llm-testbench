# ADR-002 — Dev local k3d d'abord, AWS écrit mais différé, Langfuse en phase 1

- **Statut** : accepté
- **Date** : 2026-08-26
- **Phase** : 0

## Contexte

Le brief demande une infra niveau production dès la phase 1, un cluster qui ne
tourne pas 24/7, et Langfuse self-hosted. Contraintes du jour : pas encore de
compte AWS, budget « le minimum nécessaire », machine M1 32 Go.

## Options considérées

1. **Tout monter en phase 0** (EKS + Langfuse local complet) — conforme à la
   lettre du brief, mais dépense AWS immédiate et ~5 Go de RAM pour une stack
   Langfuse v3 (ClickHouse + Redis + MinIO) qui n'a **aucune trace à recevoir**
   avant le premier appel LLM.
2. **k3d seul en phase 0 ; Terraform écrit mais non appliqué ; Langfuse au
   premier appel LLM instrumenté (phase 1)** — coût cloud nul en phase 0,
   chaque brique arrive quand elle a un consommateur.

## Décision

Option 2, validée par Christophe. Détails :

- Dev quotidien sur **k3d** (1 server + 1 agent), Postgres+pgvector en
  StatefulSet, manifests kustomize dans `infra/k8s/local/`. Tilt prêt pour le
  hot-reload de l'API en phase 1.
- **Terraform relu en phase 0, appliqué en phase 1** : bootstrap d'état S3
  (lock natif, pas de DynamoDB), `envs/dev` à plat sur les modules
  communautaires `terraform-aws-modules` (vpc, eks) — pas de modules maison
  avant le besoin réel (création de `prod`). Nœuds Graviton spot, un seul NAT,
  coûts documentés dans `infra/terraform/README.md`.
- Rythme assumé : dev sur k3d, `infra-up` ponctuel pour valider les
  déploiements, `infra-down` systématique (~20 min par sens, accepté).

## Conséquences

- Phase 0 : 0 € de cloud. Le « déployé sur le cluster » du brief se joue en
  phase 1, comme prévu.
- Langfuse local tournera en docker-compose (hors k3d) pour ne pas alourdir le
  cluster jetable ; décision fine à prendre au moment de l'installer.
- Écart au brief documenté : Langfuse était listé en phase 0 — déplacé au
  premier consommateur, avec l'accord de Christophe.
