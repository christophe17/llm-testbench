# ADR-001 — Jeux de données du banc d'essai

- **Statut** : accepté
- **Date** : 2026-08-26
- **Phase** : 0

## Contexte

Le brief impose des jeux publics à vérité annotée, comparables à la littérature.
La vérification du 2026-08-26 (`docs/datasets-verification-2026-08-26.md`) a
confirmé la disponibilité de tout le tableau, avec deux problèmes de licence et
plusieurs pièges pratiques.

## Options considérées

1. **Tout garder tel quel** — simple, mais FUNSD (non commercial, redistribution
   interdite) est incompatible avec un repo public vitrine, et le jeu complet
   BIRD (33 Go) / NQ (45 Go) tuerait l'itération.
2. **Sous-ensemble starter + retraits ciblés** — moins de couverture immédiate,
   mais itération rapide et licences propres.

## Décision

Option 2, validée par Christophe :

- **Retiré** : FUNSD (licence non commerciale). CORD couvre l'extraction champ
  par champ.
- **DocVQA** : conservé pour l'éval uniquement — licence non résolue, données
  hors git, source citée, pas de redistribution.
- **τ-bench → tau2-bench** (l'original est déprécié par Sierra).
- **BIRD → Mini-Dev SQLite** (500 instances) ; **NQ → optionnel** (SQuAD 2.0
  fournit le signal d'abstention à 1/1000e du coût).
- **Starter phase 0** : SciFact, NFCorpus, SQuAD 2.0, HotpotQA (dev), QASPER,
  Spider (dev), BIRD Mini-Dev, TAT-QA — loaders implémentés dans
  `src/llm_testbench/eval/loaders/`.
- **Aucune donnée versionnée dans le repo** (plusieurs jeux en CC BY-SA,
  copyleft) : `data/` est gitignoré, les loaders téléchargent et cachent.

## Conséquences

- Les scores seront comparables à la littérature dès la phase 2 ; les écarts
  seront traités comme des bugs.
- Les fixtures de test sont synthétiques (schéma identique, contenu inventé) —
  aucune question de licence.
- La contamination reste un sujet ouvert, traité en phase 2.5.
- MuSiQue, 2WikiMultihopQA, FiQA, les jeux agents/images seront ajoutés au fil
  des phases qui les consomment.
