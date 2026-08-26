# ADR 004 — Interface de chargement des jeux d'évaluation

- **Date** : 2026-08-26
- **Statut** : accepté

## Contexte

Une dizaine de jeux publics rejoindront le banc au fil des phases, chacun avec son format
(Parquet HF en 2-3 dépôts, zips, JSON GitHub) et ses pièges (ids typés int, requêtes non
jugées, splits gated). La phase 0 fige le contrat avec UN loader de référence (SciFact).

## Options considérées

1. **Réutiliser un cadre existant** (`ir_datasets`, paquet `beir`) — couvre le retrieval,
   mais pas les familles suivantes (QA, SQL, images), impose ses types, et masque
   précisément la mécanique que le projet veut exposer.
2. **Types maison validés + loaders par famille** — plus de code à nous, mais un contrat
   unique extensible et une validation d'intégrité explicite.

## Décision

Option 2. Un loader produit un `RetrievalDataset` Pydantic **frozen** qui valide à la
construction : unicité des ids, qrels sans référence orpheline, aucune requête sans
jugement (les requêtes hors split sont filtrées par le loader — SciFact en a 1 109 pour
300 jugées en test). La jointure est une fonction pure (`build_retrieval_dataset`),
identique pour les données réelles et les fixtures de test. La provenance (`DatasetInfo` :
source, licence telle qu'affichée, homepage) voyage avec les données, et le flag `sampled`
aussi : un chiffre calculé sur un jeu tronqué s'auto-déclare non publiable.

Les familles suivantes (QA, SQL…) auront leurs propres types de sortie mais le même
contrat : provenance déclarée, intégrité validée, mode échantillon explicite.

## Conséquences

Ajouter un jeu BEIR = une entrée dans `BEIR_DATASETS` + fixtures + tests. Le harness de
la phase 2 consommera ces types tels quels. Limite assumée : le mode échantillon garde
uniquement les documents jugés (plus de distracteurs) — suffisant pour vérifier la
mécanique, dénué de sens pour un score, et c'est marqué dessus.
