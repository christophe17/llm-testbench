# llm-testbench

**Banc d'essai LLM chiffré.** Chaque technique de retrieval, de génération et d'agentique
implémentée ici est mesurée sur des jeux de données publics à vérité de référence annotée
(BEIR, HotpotQA, SQuAD 2.0, QASPER, Spider, BIRD…), et comparée aux scores publiés dans la
littérature. Le système est déployable et opéré pour de vrai — API, Kubernetes,
observabilité, coûts — mais son argument est la mesure, pas le cas d'usage.

> 🚧 Projet en construction, phase 0 (fondations). Le tableau maître des résultats
> apparaîtra à partir de la phase 2.

## Ce que ce banc d'essai ne simule pas

Il n'y a **ni utilisateurs ni trafic réel**. Tout ce qui suppose de la production — A/B
testing, canary, détection de drift, boucle de feedback — sera démontré sur un générateur
de trafic synthétique rejouant les requêtes des jeux publics selon des profils de charge
configurables. Cette simulation ne capture ni le comportement adversarial ou hors
distribution de vrais utilisateurs, ni la saisonnalité réelle, ni le feedback humain
authentique. C'est une limite assumée du dispositif, pas un détail.

Par ailleurs, les jeux publics utilisés sont probablement présents dans les données
d'entraînement des modèles évalués : la contamination est traitée comme un sujet de mesure
(phase 2), pas ignorée.

## Démarrage

```bash
make setup          # uv sync + hooks pre-commit
make check          # lint + typecheck + tests hors ligne
make notebooks-ci   # notebooks en mode échantillon (comme la CI)
make k3d-up         # cluster local k3d + Postgres/pgvector
```

## Structure

Voir `CLAUDE.md` (brief complet), `STATE.md` (état courant), `docs/adr/` (décisions),
`notebooks/00_visite_guidee.ipynb` (visite guidée de l'architecture et des jeux de données).

## Licences des données

Le code est sous licence MIT. Les jeux de données conservent leurs licences propres —
détail vérifié dans `docs/datasets-verification-2026-08-26.md`. Aucune donnée n'est
redistribuée dans ce dépôt en dehors de fixtures de tests minuscules ; en particulier,
certains jeux (FUNSD, ChartQA, DocVQA) portent des licences qui interdisent ou
compliquent la redistribution.
