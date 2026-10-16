---
name: structured_output_repair
version: 1
description: Message de réparation envoyé après une sortie structurée invalide, avec l'erreur de validation.
---
Ta réponse précédente n'est pas conforme au schéma attendu. Erreur de validation :

{{ error }}

Renvoie uniquement l'objet JSON corrigé, complet, sans texte autour ni bloc de code.
