# PHASE 9 — Voice (extension, ajoutée le 2026-08-27)

Le segment voice agents monte vite dans les offres 2026 et le banc d'essai n'avait aucun
composant audio. Même logique que tout le reste : **on branche sur le système existant, on
mesure**.

Pipeline temps réel STT → agent existant → TTS, exposé par l'API actuelle : streaming audio
bidirectionnel, barge-in (l'utilisateur coupe la parole à l'agent), gestion du silence et des
tours de parole. La latence perçue devient le sujet central : le TTFT devient un
**time-to-first-audio**, décomposé par étape (STT, agent, TTS) avec le harness d'observabilité
de la phase 5. Coût par minute de conversation, comparé au coût par requête texte. Dégradation
gracieuse vers le texte quand l'audio échoue.

**Jeux d'évaluation** à vérifier au démarrage de la phase (même protocole que la phase 0 :
disponibilité, taille, licence) — candidats : VoiceBench et équivalents ; à défaut, rejeu audio
des questions des jeux texte existants via TTS, avec la contamination de cette boucle
documentée.

**Notebooks** : (1) d'où vient la latence d'un agent vocal — la décomposition milliseconde par
milliseconde ; (2) évaluer un agent qu'on écoute : ce qui change quand la sortie n'est plus du
texte.

**En fin de phase** : décision GO/NO-GO sur la phase 10.
