# ADR 006 — Couche LLM : abstraction à deux implémentations, gouvernance des données par construction

- **Date** : 2026-09-03
- **Statut** : accepté

## Contexte

Le brief fige une abstraction multi-provider dès le premier appel (OpenAI ↔ Anthropic ↔
Mistral ↔ modèle local), Bedrock comme provider parmi d'autres en cloud, et des prompts en
fichiers versionnés. Au démarrage de la phase 1, deux éléments nouveaux : la demande de
passer par OpenRouter pour toute la roadmap (« basculer facilement de LLM »), et l'annonce
d'une contrainte de **gouvernance des données** à venir, de nature encore inconnue, à
prendre en compte le plus tôt possible (clients en vue, cible Suisse : banque, pharma,
assurance, résidence des données et on-premise).

## Options considérées

**Pour l'abstraction.**

1. **OpenRouter comme chemin unique.** Un seul client compatible OpenAI, un catalogue de
   modèles sans clé dédiée. Rejeté comme chemin unique : intermédiaire américain
   supplémentaire qui route chaque modèle vers un hébergeur tiers sans contrôle de la
   région d'inférence (incompatible avec la contrainte annoncée) ; plus petit dénominateur
   commun (pas d'API batch, structured outputs et cache de prompt partiellement exposés) ;
   comptage de tokens normalisé et commission sur les crédits qui brouillent le coût par
   requête de la phase 5.
2. **LiteLLM** (ou équivalent) comme abstraction. Couvre cent providers, mais masque
   précisément la mécanique que le projet veut exposer (retries, breaker, budget, cache),
   et ajoute une dépendance lourde. Comparé dans le notebook 1, pas empilé.
3. **Abstraction maison à deux implémentations** sur les SDK officiels : `anthropic`
   (qui sert aussi Bedrock via son client Bedrock, même API Messages) et `openai` avec URL
   de base (OpenAI, OpenRouter, Mistral, puis vLLM/Ollama en phase 6). **Retenu.** Deux
   implémentations couvrent six backends ; le modèle est une chaîne `backend/modèle` en
   configuration ; OpenRouter reste un **backend de largeur** pour les comparaisons.

**Pour la gouvernance.**

1. **Un document** listant les fournisseurs autorisés. Rejeté : non vérifiable, oublié au
   premier refactor, invisible dans les traces.
2. **Une propriété de la couche LLM**, vérifiée à chaque appel et tracée. **Retenu.**

## Décision

### Structure

Module `src/llm_testbench/llm/` :

| Fichier | Rôle |
|---|---|
| `types.py` | `Message`, `CompletionRequest`, `Completion`, `Usage`, `StreamChunk`, `ModelRef` |
| `errors.py` | hiérarchie d'erreurs typées, avec drapeau `retryable` |
| `provider.py` | protocole `LLMProvider` : `complete()`, `stream()`, capacités déclarées |
| `providers/anthropic.py`, `providers/openai_compatible.py` | les deux implémentations |
| `registry.py` | backends et modèles depuis `config/llm_backends.toml`, résolution `backend/modèle` |
| `governance.py` | classes de données, métadonnées de gouvernance, politique, décision |
| `resilience.py` | retry avec backoff exponentiel et gigue, circuit breaker à trois états, délais |
| `budget.py` | budget de tokens par requête et par fenêtre glissante |
| `cache.py` | cache exact (empreinte canonique de la requête) et sémantique (pgvector) |
| `structured.py` | sortie structurée : schéma natif quand le backend le supporte, validation Pydantic, boucle de réparation bornée |
| `prompts.py` | registre de prompts versionnés (`prompts/*.md`, en-tête + corps Jinja2 strict), empreinte SHA-256 |
| `cost.py` | table de prix `config/llm_pricing.toml` datée, coût par appel, `None` si inconnu |
| `client.py` | façade `LLMClient` : gouvernance → cache → breaker → retry → provider → budget → coût → trace |

### Choix qui ne vont pas de soi

- **Les SDK ne retentent pas** (`max_retries=0`) : une seule politique de retry, la nôtre,
  observable par tentative, consciente du budget et du breaker. Deux couches de retry
  empilées multiplient les tentatives sans que personne ne le voie.
- **Sortie structurée** : schéma JSON natif (`output_config.format` chez Anthropic,
  `response_format` json_schema chez OpenAI et compatibles qui le supportent), sinon
  consigne dans le prompt et extraction. Dans tous les cas validation Pydantic, puis au plus
  N tentatives de réparation où l'erreur de validation est renvoyée au modèle. Chaque
  tentative est tracée : le taux de réparation est une métrique, pas un secret.
- **Cache exact** sur l'empreinte canonique de la requête entière (backend, modèle,
  messages, paramètres, version du prompt). **Cache sémantique** sur l'embedding du dernier
  message utilisateur, seuil de similarité configurable, réservé aux requêtes sans historique.
  Les deux dans Postgres ; un backend mémoire pour les tests. Un coup de cache est tracé
  comme tel avec un coût nul.
- **Streaming** : générateur asynchrone de `StreamChunk` ; la fermeture du générateur
  (déconnexion du client SSE) ferme le flux provider. Aucune accumulation cachée.
- **Prompts** : fichiers `prompts/<nom>.md`, en-tête (nom, version, description, backends
  conseillés) et corps Jinja2 à variables strictes (une variable manquante est une erreur,
  pas une chaîne vide). Le rendu porte son empreinte SHA-256, inscrite dans la trace : on
  saura toujours quel texte exact a produit quel chiffre. Le registre de la phase 5
  (rollback à chaud) s'appuiera dessus.
- **Coût** : table de prix versionnée avec date de vérification et source. Un modèle sans
  prix connu donne un coût `None` et un attribut de trace `cost.unknown=true` : un chiffre
  absent vaut mieux qu'un chiffre inventé.
- **Configuration en TOML** (`tomllib`, bibliothèque standard) : lisible, typé, pas de
  dépendance.

### Gouvernance des données

- Chaque requête porte une **classe de données** : `public`, `internal`, `confidential`,
  `personal`, `regulated`. Sans classe explicite, une requête est refusée : le défaut
  implicite est la première faille.
- Chaque backend déclare, dans `config/llm_backends.toml`, ses **métadonnées de
  gouvernance** : entité juridique et pays, région d'inférence (`eu`, `us`, `self`,
  `variable`), rétention par défaut et disponibilité de la rétention zéro, usage des
  entrées pour l'entraînement, sous-traitants (OpenRouter : hébergeurs variables),
  certifications. Ces métadonnées sont des affirmations à vérifier contractuellement, pas
  des garanties : leur date de vérification est inscrite.
- Une **politique** associe chaque classe à des exigences et décide **par refus par
  défaut** avant tout appel réseau. Politique initiale, **provisoire** tant que les
  contraintes réelles ne sont pas connues : `public` sans exigence ; `internal` exige
  l'absence d'entraînement sur les entrées ; `confidential`, `personal`, `regulated`
  exigent région `eu` ou `self`, rétention zéro et absence d'entraînement. Elle vit dans
  un fichier de configuration, pas dans le code.
- La **décision** (classe, backend, résultat, règle) est un attribut de la trace de chaque
  appel, à côté de l'identifiant exact du modèle et de la région. Un refus est une
  exception typée, jamais un repli silencieux vers un autre backend : le repli est une
  décision de l'appelant, tracée elle aussi.
- La même politique s'applique aux **embeddings** (le texte part de la même manière) et,
  en phase 2, au **juge**.
- Sur le banc, toutes les données sont publiques : le mécanisme est exercé par les tests
  et démontré dans le notebook (une requête étiquetée `regulated` refuse OpenRouter). À
  partir de la phase 6, le tableau maître gagne une ligne « coût de la gouvernance » :
  latence, prix et qualité du chemin conforme contre le chemin libre.

## Conséquences

Générateur par défaut de la phase 1 : `anthropic/claude-sonnet-5` ; second provider OpenAI,
qui servira de juge en phase 2 (juge ≠ générateur). OpenRouter et Bedrock sont des backends
déclarés dès la phase 1, Bedrock activé avec l'infra cloud. La politique de gouvernance sera
durcie quand les contraintes se préciseront, sans toucher au code. Coût : deux SDK à suivre
au lieu d'un, et une table de prix à maintenir à la main — c'est le prix d'un chiffre de
coût auquel on peut croire. Phase 7 (PII, AI Act) et phase 4.7 (permissions) se branchent
sur les mêmes attributs de trace.
