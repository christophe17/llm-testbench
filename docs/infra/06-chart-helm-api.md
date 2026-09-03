# Guide 06 — Le chart Helm de l'API : probes, ressources, HPA, PDB, secrets, sécurité

**Durée** : 20 minutes de lecture, 5 d'exécution. **Prérequis** : guide 01 (cluster
local). **Coût** : 0 €. **Code** : `infra/helm/llm-testbench-api/`.

---

## Le problème

Déployer un conteneur, tout le monde sait faire. Le déployer pour qu'il **survive** à une
mise à jour, à la panne d'un nœud, à un pic de trafic et à un fichier de configuration
modifié — sans intervention humaine — c'est ce qu'un chart de niveau production encode.
Chaque valeur par défaut de `values.yaml` répond à un incident classique.

## Les options

| Option | Verdict |
|---|---|
| Manifests YAML bruts | Lisibles, mais dupliqués entre local et cloud, et sans paramétrage propre. |
| Kustomize | Bien pour des surcharges simples (on l'utilise pour Postgres local) ; faible pour la logique conditionnelle (ExternalSecret ou pas, HPA ou pas). |
| **Helm** | **Retenu** : un chart, des fichiers de valeurs par environnement, des conditions. Le standard des équipes que vous rejoindrez. |
| Un chart générique du marché | Cache les choix qu'on veut expliquer ici. Le nôtre fait 180 lignes de templates. |

## Lecture guidée du code réel

**[`values.yaml`](../../infra/helm/llm-testbench-api/values.yaml)**, du haut vers le bas :

- **`replicaCount: 2`** — deux réplicas minimum : un seul pod, c'est zéro tolérance à la
  panne et zéro mise à jour sans interruption.
- **`config`** — les variables d'environnement *non secrètes*, rendues en `ConfigMap`.
- **`secrets.existingSecret`** — le chart ne crée jamais de secret ; il en référence un.
  En local, `make k8s-secrets` le crée depuis `.env`. En cloud,
  `secrets.externalSecret.enabled: true` rend un `ExternalSecret` qui demande à External
  Secrets Operator de le fabriquer depuis Secrets Manager (guide 05).
- **`resources`** — des `requests` (ce que le scheduler réserve) et une limite mémoire,
  **mais pas de limite CPU** : la limite CPU déclenche du throttling CFS qui dégrade la
  latence sans protéger personne ; la limite mémoire, elle, évite qu'un pod qui fuit
  emporte le nœud.
- **`autoscaling`** — un HPA sur le CPU (70 %), de 2 à 6 réplicas. Il a besoin de
  `metrics-server` (add-on managé sur EKS, guide 03 ; livré avec k3s en local).
- **`podDisruptionBudget: minAvailable 1`** — lors d'un drain de nœud (mise à jour, scale
  down), Kubernetes n'évincera jamais le dernier pod disponible.
- **`probes`** — trois sondes, trois questions (guide 01, question 1). Le `startupProbe` à
  30 × 2 s laisse 60 s au pool Postgres et au schéma ; sans lui, une liveness impatiente
  tuerait un pod en plein démarrage, en boucle.
- **`podSecurityContext` / `securityContext`** — non root, pas d'escalade de privilèges,
  système de fichiers en lecture seule (d'où le volume `/tmp` en `emptyDir`), toutes les
  capacités Linux retirées, profil seccomp par défaut. C'est le niveau « restricted » des
  Pod Security Standards.

**[`templates/deployment.yaml`](../../infra/helm/llm-testbench-api/templates/deployment.yaml)** :

- **`strategy.rollingUpdate: maxUnavailable 0, maxSurge 1`** — une mise à jour crée le
  nouveau pod avant de retirer l'ancien : jamais moins de réplicas que demandé.
- **`checksum/config`** — l'empreinte du `ConfigMap` dans les annotations du pod : quand
  la configuration change, le hash change, le Deployment redéploie. Sans ça, un
  `helm upgrade` qui ne touche que la configuration ne redémarre rien, et le nouveau
  réglage n'est jamais lu.
- **`envFrom`** — le `ConfigMap` et le `Secret` (marqué `optional`, pour que l'API
  démarre et dise elle-même ce qui lui manque via `/readyz`).
- **`topologySpreadConstraints`** — répartir les réplicas sur des nœuds différents quand
  c'est possible (`ScheduleAnyway` : en local, un seul nœud, on n'empêche rien).
- **`automountServiceAccountToken: false`** — l'API n'appelle pas l'API Kubernetes ; un
  jeton monté par défaut serait une surface d'attaque gratuite.

**[`templates/externalsecret.yaml`](../../infra/helm/llm-testbench-api/templates/externalsecret.yaml)**
— rendu seulement si activé : pour chaque entrée `data`, une clé du `Secret` cible
alimentée par une clé Secrets Manager. `creationPolicy: Owner` : le `Secret` appartient
à l'`ExternalSecret`, il disparaît avec lui.

**Les deux fichiers de valeurs.** `values-local.yaml` : image du registre local, un
réplica, pas d'HPA ni de PDB, URL de base vers le service `postgres` du namespace.
`values-dev.yaml` : image ECR au SHA git, External Secrets, annotation du rôle IAM sur
le ServiceAccount (Pod Identity, guide 03).

## Exécution

**1. Lint et rendu**, avant tout déploiement :

```bash
make helm-lint
helm template api infra/helm/llm-testbench-api -f infra/helm/llm-testbench-api/values-local.yaml | less
```

Lisez le rendu : c'est exactement ce que le cluster recevra. Cherchez `checksum/config`,
`readOnlyRootFilesystem`, `maxUnavailable`.

**2. Déployer en local** (guide 01, étape 4) puis observer les probes :

```bash
kubectl -n llm-testbench describe pod -l app.kubernetes.io/instance=api | sed -n '/Liveness/,/Environment/p'
kubectl -n llm-testbench get events --sort-by=.lastTimestamp | tail -5
```

**3. Provoquer une mise à jour sans interruption** : changez `LLM_TESTBENCH_RETRIEVAL_K`
dans `values-local.yaml`, relancez `helm upgrade`, et regardez `kubectl get pods -w` : un
nouveau pod naît, devient prêt, l'ancien s'arrête. L'annotation de checksum a fait le
travail.

**4. Provoquer un redémarrage par liveness** : `kubectl -n llm-testbench exec <pod> --
kill 1` termine uvicorn ; le conteneur redémarre (`RESTARTS` passe à 1). Aucun
`kubectl delete` nécessaire.

## Les pièges

- **Un `ConfigMap` modifié ne redémarre rien** sans l'annotation de checksum. Le symptôme
  classique : « j'ai changé la config, ça n'a rien changé ».
- **La limite CPU** est le réglage le plus souvent copié-collé et le plus souvent nocif :
  du throttling apparaît bien avant que le pod n'atteigne sa limite, sur des pics courts.
- **Un HPA sans `metrics-server`** reste à `<unknown>` et ne fait rien, silencieusement.
  `kubectl get hpa` doit afficher un pourcentage, pas `<unknown>`.
- **`readOnlyRootFilesystem` casse les bibliothèques qui écrivent** dans leur dossier
  (caches de modèles, fichiers temporaires). Le volume `/tmp` couvre le cas courant ; un
  modèle local (phase 6) aura besoin d'un volume dédié.
- **Le PDB peut bloquer un drain** si `minAvailable` ne peut pas être satisfait (un seul
  réplica avec `minAvailable: 1`). Les valeurs locales le désactivent pour cette raison.
- **`helm upgrade --wait` expire** si la readiness ne passe jamais : ce n'est pas le
  chart, c'est l'API qui refuse le trafic (guide 01, étape 4).

## Questions d'entretien

<details><summary><b>1. Pourquoi des requests sans limite CPU ?</b></summary>

Les requests servent au placement (le scheduler réserve) et à la priorité en cas de
contention. La limite CPU impose un plafond strict par période d'ordonnancement (CFS) et
provoque du throttling dès qu'un pic dépasse le quota, même si le nœud a du CPU libre.
Pour un service de latence, on réserve sans plafonner. La mémoire, elle, ne se partage
pas : on la limite pour qu'un pod ne tue pas ses voisins.
</details>

<details><summary><b>2. Que se passe-t-il pendant un rolling update avec maxUnavailable 0 ?</b></summary>

Kubernetes crée un pod de la nouvelle version (surge), attend qu'il soit prêt (readiness),
puis termine un ancien pod ; et recommence jusqu'au dernier. La capacité ne descend
jamais sous le nombre demandé. Le prix : temporairement un réplica de plus, donc un peu
de capacité de nœud en réserve.
</details>

<details><summary><b>3. PDB et HPA : lequel protège de quoi ?</b></summary>

L'HPA ajuste le nombre de réplicas à la charge (montée et descente). Le PDB limite les
évictions *volontaires* (drain, mise à jour de nœud) : il ne protège pas d'une panne
matérielle. Les deux se combinent : l'HPA fixe combien de pods, le PDB combien peuvent
disparaître en même temps.
</details>

<details><summary><b>4. Comment le pod obtient-il ses secrets sans qu'ils soient dans git ?</b></summary>

Le chart référence un `Secret` par son nom. Qui le crée dépend de l'environnement : un
humain depuis `.env` en local, External Secrets Operator depuis Secrets Manager en cloud,
authentifié par l'identité de pod (pas de clé AWS dans le cluster). Le chart est le même.
</details>

<details><summary><b>5. Pourquoi un startupProbe alors qu'on a déjà une liveness ?</b></summary>

Une liveness assez stricte pour détecter un blocage en production (quelques dizaines de
secondes) est trop stricte pour un démarrage lent (pool de connexions, chargement d'un
modèle). Le startupProbe donne un délai généreux au démarrage seulement, puis passe la
main à la liveness stricte. Sans lui : redémarrages en boucle au démarrage.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas d'Ingress ni de TLS** par défaut : l'exposition dépend de l'environnement (guide
  03 pour EKS) ; le template existe, désactivé.
- **Pas de NetworkPolicy** : à ajouter avec les sources SQL/API de la phase 4, quand il y
  aura des flux à restreindre.
- **Pas de PriorityClass ni de Karpenter** : un seul service, un seul groupe de nœuds ;
  phase 5, avec le générateur de trafic.
- **Pas de tests de chart automatisés** (helm-unittest) : `helm lint` + rendu suffisent
  à ce stade ; à revoir quand le chart aura plus d'une variante.
