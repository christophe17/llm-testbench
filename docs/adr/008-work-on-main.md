# ADR 008 — Tout le travail sur `main`, sans branche de phase ni PR

- **Date** : 2026-10-16
- **Statut** : accepté

## Contexte

Le brief prévoyait « une phase = une branche = une PR avec une description sérieuse ». En
pratique, les branches vivaient des semaines (PR #3 ouverte le 2026-09-03, fusionnée le
2026-10-16), les amendements de documentation s'y empilaient, et une branche annexe de docs
(PR #2) devait être fusionnée avant l'autre. Un seul auteur, aucun relecteur tiers : la PR
servait de jalon, pas de revue. Christophe demande que tout soit sur `main`.

## Options considérées

1. **Garder branche + PR par phase** — jalon visible sur GitHub, description de PR comme récit de
   phase, et surtout la phase 2.7 peut **bloquer un merge** sur régression. Contre : branches
   longues, divergence, fusion différée de semaines, cérémonie sans relecteur.
2. **Tout sur `main`** — un seul état du projet, pas de divergence, la CI tourne sur chaque push.
   Contre : plus rien ne *bloque* l'entrée d'une régression ; le récit de phase doit trouver
   une autre place.

## Décision

Option 2. Commits petits et décrits, poussés quand la CI locale passe ; la CI GitHub tourne déjà
sur `push: [main]`. Le récit d'une phase va dans son entrée de clôture de `JOURNAL.md`.

Pour la phase 2.7, le blocage passe en amont : un hook `pre-push` lance la porte d'évaluation en
mode échantillon et refuse le push au-delà du seuil ; la même porte dans la CI GitHub passe au
rouge sur `main` si le hook a été contourné (`--no-verify`).

## Conséquences

- Plus de divergence ni de fusion différée ; `STATE.md` décrit toujours l'état de `main`.
- **Perte assumée** : un hook local est contournable et une CI rouge sur `main` constate au lieu
  d'empêcher. En entretien, la porte d'évaluation doit être présentée comme ce qu'elle est, et
  comparée honnêtement à une protection de branche en équipe (merge bloqué par check requis) —
  c'est la configuration à recommander dès qu'il y a plus d'un contributeur.
- Si un jour une revue externe (client, contributeur) entre dans le dépôt, revenir aux PR avec
  protection de `main` ; cet ADR sera alors remplacé.
