# PHASE 6 — Inférence et modèles ouverts (semaines 14–15)

**Note stratégique** : la Suisse (banque, pharma, assurance) est une contrainte du programme, et
la résidence des données et le déploiement on-premise y sont des exigences fortes. Cette phase a
une valeur supérieure à la moyenne — ne pas la sacrifier en cas de retard. Proposer au moins un
modèle ouvert européen en plus des classiques.

**vLLM** : continuous batching, PagedAttention, KV cache — je veux comprendre **pourquoi** c'est
rapide, pas seulement comment le lancer. Branché comme backend compatible OpenAI de la couche
LLM (ADR 006).

**Quantization** AWQ / GPTQ / FP8 avec **impact qualité mesuré par notre harness sur les jeux
publics** : presque personne ne fait cette mesure, c'est exactement ce qui me distinguera.

**Modèle économique** : throughput vs latence, sizing GPU, coût par million de tokens self-host
vs API, **seuil de bascule en volume**.

**Déploiement** GPU sur Kubernetes, autoscaling, cold start. Embeddings et reranker
self-hosted. Deux cibles pour le même chart vLLM, mesurées l'une contre l'autre (ADR 009) :
(a) un module Terraform GPU **éphémère** vers un fournisseur spécialisé découplé du cloud
principal — le chemin par défaut, destruction évidente ; (b) **un node group GPU sur l'EKS
existant** (g6, GPU L4, Spot via Karpenter), si le quota « Running On-Demand G and VT
instances » a été accordé — demandé dès la phase 1 (`STATE.md`), car il prend des jours à des
semaines. Une ligne de plus dans le tableau : coût par million de tokens, cold start, temps de
montée, sur chaque cible. C'est le seul endroit où « infra GPU », la mission préférée du
programme (PD-18), et « LLMOps sur AWS » se rencontrent : l'ADR sur le découplage devient un
ADR sur le choix de cible, chiffré.

**Gouvernance mesurée** : ligne « coût de la gouvernance » du tableau maître (ADR 006) — ce
que coûte le refus de router une classe de données vers un backend non conforme.

**Fine-tuning** : un LoRA/QLoRA sur un cas justifié, évalué contre la baseline prompt-only — **et
documenter les cas où le fine-tuning n'était pas la bonne réponse, chiffres à l'appui**. Chaque
run d'entraînement, LoRA compris, écrit le **manifeste de run** défini en 5B.3. Le garder assez
complet (config hachée, graine, révision du jeu, identifiant exact du modèle, métriques, coût)
pour servir de point de départ SFT au module R1.1 de la roadmap Research Engineer
(`~/Roadmaps/roadmap-research-engineer`), qui suppose les phases 2, 3, 6 et 7 livrées.

**5B rejouée** : le bras LLM de la phase 5B sur un modèle self-hosted — coût marginal et qualité,
une ligne de plus dans son tableau.

**Notebooks** : (1) ce que vLLM fait vraiment sous le capot ; (2) le vrai coût qualité de la
quantization ; (3) self-host vs API, le calcul complet avec mes chiffres.
