# PHASE 8 — Packaging (semaine 16, commencé dès la semaine 4)

**README du banc d'essai** : ce que le projet mesure → l'architecture (un schéma) → **le tableau
maître des résultats**, technique par technique, avec écart à la littérature, coût et latence
(dont la ligne « régénération depuis zéro » de la phase 3 et la ligne « coût de la
gouvernance » de la phase 6), et l'arbre de décision ML classique / LLM de la phase 5B → les
décisions et arbitrages → ce qui a cassé et ce que j'en ai tiré → ce que je ferais
différemment à l'échelle 100× → les limites du dispositif (pas d'utilisateurs, trafic
synthétique). Les phases non faites (10 si NO-GO) y ont leur paragraphe « pas fait, et
pourquoi ».

**Deux posts techniques** tirés du JOURNAL : « le harness d'évaluation que j'ai construit, et
pourquoi les métriques standard mentent » ; « self-host vs API : le calcul complet, avec mes
chiffres ».

**Une contribution open source** ciblée dans l'écosystème réellement utilisé.

**CV** : tenu par le programme (`~/Roadmaps/program/docs/01-career-strategy.md` §7) et préparé
par le module R4 de la roadmap Research Engineer ; ce banc fournit les chiffres du bloc
« production et opérations », pas un CV à part (2026-10-19).

**Préparation d'entretien** : system design IA chronométré, argumentaire build vs buy sur trois
briques, et **trois histoires d'incident au format situation-action-résultat chiffré**. Elles
ne viendront pas d'utilisateurs — il n'y en a pas — mais de la construction elle-même : une
régression détectée par la porte d'évaluation, une dérive de coût, un juge mal calibré, une
quantization qui dégrade en silence, un pipeline qui reconstruit tout au lieu de l'incrément.
Ce sont de vrais incidents ; ils sont tenus à jour dans `JOURNAL.md` au fil de l'eau, jamais
reconstitués après coup.

**À vérifier à ce moment-là** : le raisonnement sur le mot « pipeline » des offres (2026-10-15)
repose sur la connaissance générale des offres 2026, pas sur un corpus relu — le confronter à
de vraies offres.
