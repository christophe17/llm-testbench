---
name: structured_output_instruction
version: 1
description: Consigne ajoutée au system prompt quand le backend ne sait pas imposer un schéma JSON lui-même.
---
Réponds uniquement avec un objet JSON valide, conforme au schéma JSON ci-dessous. Aucun texte avant ou après, aucun bloc de code, aucune explication.

Schéma JSON attendu :
{{ schema_json }}
