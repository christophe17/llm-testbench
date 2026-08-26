# llm-testbench

**Banc d'essai technique chiffré** pour les systèmes LLM en production : RAG, agents
multi-sources, text-to-SQL, évaluation, observabilité, inférence self-hosted.

Chaque technique implémentée est **mesurée sur des jeux de données publics à vérité de
référence annotée** (BEIR, HotpotQA, SQuAD 2.0, QASPER, Spider, BIRD, τ-bench, BFCL,
TAT-QA, ChartQA, CORD, AgentDojo…) et **comparée aux scores publiés dans la littérature**.
L'argument de vente est la mesure, pas le cas d'usage.

> 🚧 **Statut : phase 0 — fondations.** Le tableau maître des résultats arrivera avec la
> phase 2 (harness d'évaluation). Roadmap complète dans [CLAUDE.md](CLAUDE.md),
> état courant dans [STATE.md](STATE.md), décisions dans [docs/adr/](docs/adr/).

## Ce que ce repo contient

- `src/llm_testbench/` — code de production : API, couche LLM multi-provider, sources,
  ingestion, retrieval, génération, agents, harness d'évaluation, observabilité.
- `notebooks/` — notebooks pédagogiques qui **importent et exécutent le code réel** de
  `src/` (aucune réimplémentation simplifiée), avec sorties intermédiaires visibles.
- `infra/` — k3d + Tilt en local, Terraform + Helm pour AWS (EKS, RDS pgvector, ECR).
- `docs/adr/` — une décision structurante = un ADR.
- `data/` — cache local des jeux publics, **jamais versionné** (licences) ; les loaders
  de `src/llm_testbench/eval/loaders/` téléchargent et vérifient tout.

## Démarrage

```bash
make install        # uv sync + pre-commit
make check          # lint + typecheck + tests (offline)
make data-starter   # télécharge le sous-ensemble de démarrage (~150 Mo)
make cluster-up     # k3d + Postgres/pgvector local
```

## Licence

Code sous [MIT](LICENSE). Les jeux de données conservent leurs licences respectives
(détail : [docs/datasets-verification-2026-08-26.md](docs/datasets-verification-2026-08-26.md)) ;
aucune donnée n'est redistribuée dans ce repo.
