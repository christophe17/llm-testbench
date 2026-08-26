# data/

- `cache/` — cache local des jeux publics téléchargés (Hugging Face, zips…). **Jamais
  versionné** (`.gitignore`) : tout se retélécharge à partir des loaders de
  `src/llm_testbench/eval/loaders/`, qui sont la seule source de vérité sur la provenance.
- Le golden set maison (phase 2) vivra ici, **lui versionné**, avec son CHANGELOG.

Ne jamais committer de données publiques redistribuées : certaines licences l'interdisent
(détail dans `docs/datasets-verification-2026-08-26.md`). Les seules données versionnées
dans le dépôt sont les fixtures minuscules de `tests/fixtures/`, rédigées à la main.
