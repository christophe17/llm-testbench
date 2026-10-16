# PHASE 7 — Sécurité résiduelle et conformité (semaine 16, partagée avec la phase 8)

L'essentiel a été traité en phase 4 (sécurité des outils, AgentDojo) et en phase 5 (audit,
journalisation). Reste :

- OWASP LLM Top 10 appliqué à l'architecture complète ;
- injection indirecte par **document** empoisonné dans le corpus (les documents empoisonnés
  viennent du corpus maison de la phase 2.5) ;
- exfiltration via les citations ;
- filtrage de sortie ;
- détection et masquage de PII (Presidio) ;
- red teaming automatisé (garak, promptfoo redteam) dans la CI.

Puis `docs/ai-act.md` : exercice de conformité **appliqué à un déploiement hypothétique en
entreprise** — le banc d'essai n'a pas d'utilisateurs, donc poser le cadre explicitement, puis
la classification de risque au sens de l'EU AI Act, les obligations de documentation et de
journalisation, et la minimisation RGPD. La grille de défendabilité de la phase 5B s'y
rattache. L'objectif est que je sache tenir cette conversation en entretien, pas de produire un
dossier réglementaire.
