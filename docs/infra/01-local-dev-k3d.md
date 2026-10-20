# Guide 01 — Dev local : k3d, Postgres/pgvector, l'API dans le cluster, la boucle Tilt

**Durée** : 20 minutes la première fois. **Prérequis** : Docker Desktop (VM à 12 Go de
mémoire recommandé pour accueillir Langfuse au guide 07), k3d ≥ 5.9, kubectl, Helm ≥ 3,
Tilt. **Coût** : 0 €. **Code** : `infra/k3d/`, `infra/k8s/local/`, `Tiltfile`, `Dockerfile`.

---

## Le problème

L'API doit tourner **comme en production** dès la phase 1 : dans un conteneur, sur
Kubernetes, derrière des probes, avec ses secrets injectés et une base Postgres à côté.
Mais l'itération doit rester rapide : sauvegarder un fichier et voir l'effet en deux
secondes, pas en deux minutes de build. Et tout doit tourner sur un Mac Apple Silicon sans
émulation, qui rend Docker dix fois plus lent.

## Les options

| Option | Verdict |
|---|---|
| Kubernetes de Docker Desktop | Refusé par le brief : un seul cluster figé, pas de registre local, configuration opaque. |
| minikube / kind | Corrects. kind est proche de k3d ; minikube est plus lourd (VM). |
| **k3d** (k3s dans Docker) | **Retenu** : démarre en 30 s, registre local intégré, configuration déclarative, plusieurs clusters possibles. |
| Pas de Kubernetes en local, `uvicorn` seul | Utile pour un test rapide (`make api`), mais on ne verrait jamais les probes, les secrets et le chart avant le cloud. |

Pour la boucle de dev : **Tilt** plutôt que Skaffold, pour son `live_update` (synchronise
les fichiers dans le conteneur sans reconstruire l'image) et son tableau de bord.

## Lecture guidée du code réel

**[`infra/k3d/config.yaml`](../../infra/k3d/config.yaml)** — un seul nœud serveur (pas
d'agent : un Mac n'a pas besoin de simuler trois machines), un **registre local**
`llm-testbench-registry` exposé sur le port 5050 de l'hôte, Traefik désactivé (on expose
par port-forward, pas d'Ingress en local). Le registre est le point subtil : depuis votre
Mac il s'appelle `localhost:5050`, depuis l'intérieur du cluster
`llm-testbench-registry:5050` — k3d ajoute l'entrée DNS dans les nœuds.

**[`infra/k8s/local/`](../../infra/k8s/local/)** — un kustomize avec le namespace, un
`StatefulSet` Postgres sur l'image `pgvector/pgvector:pg16` (build arm64 natif, vérifié :
pas d'émulation) avec un volume `local-path` (le provisionneur par défaut de k3s), des
probes `pg_isready`, et un `Job` `pgvector-init` qui exécute `CREATE EXTENSION vector`.
Le mot de passe est en clair dans un `Secret` : **en local uniquement** ; en cloud c'est
External Secrets (guide 05).

**[`Dockerfile`](../../Dockerfile)** — deux étapes. La première résout les dépendances
avec `uv` en deux couches : `pyproject.toml` + `uv.lock` d'abord (cache Docker : ne
change presque jamais), le code ensuite. La seconde repart d'une image Python minimale,
sans `uv` ni compilateur, copie le venv, et tourne en utilisateur non root (`uid 10001`).
Les images de base existent en arm64 et amd64 : la même recette produit l'image du Mac
et celle du cloud.

**[`Tiltfile`](../../Tiltfile)** — quatre ressources : Postgres et son job (kustomize),
un `local_resource` qui crée le `Secret` des clés API depuis `.env`, le build de l'image
avec `live_update` (synchronisation de `src/`, `prompts/`, `config/` dans le conteneur ;
`uvicorn --reload` n'est pas activé dans l'image, donc un changement de code demande un
redémarrage du pod par Tilt, ce qu'il fait seul), et le chart Helm de l'API avec ses
valeurs locales (guide 06).

**[`Makefile`](../../Makefile)** — `k3d-up`, `k3d-down`, `pg-port-forward`,
`k8s-secrets`, `docker-build`, `helm-lint`, `tilt-up`, `ingest-scifact`, `api`.

## Exécution

**1. Le cluster et la base.**

```bash
make k3d-up
kubectl config current-context        # doit afficher k3d-llm-testbench
kubectl -n llm-testbench get pods     # postgres-0 Running, pgvector-init Completed
```

Le journal du 26/08 raconte un `kubectl apply` parti sur un vieux cluster : **vérifiez le
contexte** avant tout `apply`, c'est le réflexe qui coûte le moins cher.

**2. Vérifier pgvector depuis votre machine.**

```bash
make pg-port-forward &      # laisse un port-forward en arrière-plan
LLM_TESTBENCH_DATABASE_URL=postgresql://testbench:testbench-local-only@localhost:5432/testbench \
  uv run python -c "import psycopg; c=psycopg.connect('$LLM_TESTBENCH_DATABASE_URL'); \
  print(c.execute(\"select extversion from pg_extension where extname='vector'\").fetchone())"
make test-db                 # les 6 tests de stockage sur la vraie base
```

Attendu : `('0.8.6',)` puis `6 passed`.

**3. Les secrets.** Copiez `.env.example` en `.env`, renseignez vos clés, puis :

```bash
make k8s-secrets
kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data}' | head -c 200
```

Le `Secret` contient toutes les lignes de `.env` (clés API et URL de base). Il n'est ni
dans le chart ni dans git.

**4. L'image et son déploiement, à la main une fois** (pour voir chaque étape) :

```bash
make docker-build
docker tag llm-testbench-api:dev localhost:5050/llm-testbench-api:dev
docker push localhost:5050/llm-testbench-api:dev
helm upgrade --install api infra/helm/llm-testbench-api -n llm-testbench \
  -f infra/helm/llm-testbench-api/values-local.yaml --set image.tag=dev
kubectl -n llm-testbench get pods -w
```

Le pod passe `Running` mais reste `0/1 READY` avec des `Readiness probe failed: 503`.
**C'est voulu** : `/readyz` refuse le trafic tant que l'index configuré n'existe pas dans
la base. Un pod qui ne peut pas répondre ne doit pas recevoir de requêtes, et il dit
pourquoi :

```bash
kubectl -n llm-testbench port-forward svc/api 8000:80 &
curl -s localhost:8000/readyz
```

Attendu : `{"error":"not_ready","detail":"index 'scifact-recursive-oai-small' absent du registre : lancer l'ingestion",...}`.

**5. L'ingestion** (clé OpenAI requise pour les embeddings, ~5 000 abstracts, ~0,05 $) :

```bash
set -a; source .env; set +a
make ingest-scifact
curl -s localhost:8000/readyz            # {"status":"ready"}
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"question": "Does vitamin D deficiency increase mortality?", "k": 5}' | python3 -m json.tool
```

Vous devez voir une réponse avec des citations `[n]`, les preuves et leur provenance, le
coût et l'identifiant de trace.

**6. La boucle de dev.**

```bash
make tilt-up
```

Tilt ouvre un tableau de bord (`http://localhost:10350`) : construit l'image, la pousse
dans le registre local, déploie le chart, expose `8000`. Modifiez un fichier de `src/` :
Tilt le synchronise dans le conteneur et redémarre le pod. `Ctrl-C` puis `tilt down`
pour retirer l'API (Postgres reste).

## Les pièges

- **Le mauvais contexte kubectl.** `k3d cluster create` change le contexte courant, un
  cluster hérité peut traîner. `kubectl config current-context`, toujours.
- **Le port-forward tombe** dès que le pod redémarre (Tilt le relance, pas
  `kubectl port-forward` lancé à la main). Si `curl` échoue sans raison, relancez-le.
- **`--wait` de Helm et la readiness.** `helm upgrade --wait` attend que les pods soient
  `Ready` ; sans index, il expirera. Ce n'est pas un bug du chart, c'est la readiness qui
  fait son travail. Ingérez d'abord, ou déployez sans `--wait`.
- **Mémoire de la VM Docker.** Postgres + API tiennent dans 8 Go ; Langfuse (guide 07)
  ajoute ClickHouse, Redis et MinIO : passez la VM à 12 Go dans Docker Desktop.
- **Images sans build arm64.** Une image amd64 seule tourne sous émulation, dix fois
  plus lente, et parfois pas du tout. `docker manifest inspect <image> | grep arm64`
  avant d'adopter une image.
- **Le registre local n'est pas `localhost` dans le cluster.** Un pod tire
  `llm-testbench-registry:5050/...` ; vous poussez sur `localhost:5050/...`. Les valeurs
  locales du chart utilisent le premier nom.
- **`.env` chargé deux fois.** Le `Secret` Kubernetes est créé depuis `.env` ; le
  `make api` local lit aussi `.env` (pydantic-settings). Après avoir changé une clé,
  relancez `make k8s-secrets` *et* le pod : un `Secret` mis à jour n'est pas relu par un
  processus en marche.

## Questions d'entretien

<details><summary><b>1. Différence entre liveness, readiness et startup probe ?</b></summary>

Liveness : « le processus est-il vivant ? » — en échec, le conteneur est redémarré.
Readiness : « peut-il servir du trafic maintenant ? » — en échec, le pod sort du
Service, sans redémarrage. Startup : « a-t-il fini de démarrer ? » — désactive les deux
autres pendant le démarrage, pour ne pas tuer un processus lent à s'initialiser. L'API
utilise `/healthz` pour liveness et startup, `/readyz` (base + index) pour readiness.
</details>

<details><summary><b>2. Pourquoi ne pas mettre la clé API dans l'image ou dans le chart ?</b></summary>

Une image se partage et se scanne, un chart se versionne : les deux fuient. Le secret
vit dans un `Secret` Kubernetes créé hors du chart (en local depuis `.env`, en cloud
depuis Secrets Manager par External Secrets), et le chart ne fait que le référencer.
</details>

<details><summary><b>3. À quoi sert un registre local avec k3d ?</b></summary>

À ce que les nœuds tirent l'image qu'on vient de construire sans passer par un registre
distant : pas de push sur Internet, pas d'identifiants, deux secondes au lieu d'une minute.
Le prix : deux noms pour le même registre (hôte et cluster), à connaître.
</details>

<details><summary><b>4. Que synchronise Tilt exactement, et quand reconstruit-il l'image ?</b></summary>

`live_update` copie les fichiers modifiés (ici `src/`, `prompts/`, `config/`) dans le
conteneur en cours d'exécution. Tout changement hors de ces chemins (Dockerfile,
`pyproject.toml`, `uv.lock`) déclenche une reconstruction complète.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas d'Ingress local** : port-forward suffit pour un développeur seul ; l'Ingress est
  une question de cloud (guide 03).
- **Pas de `uvicorn --reload` dans l'image** : l'image est celle de production ; le
  rechargement est le rôle de Tilt (redémarrage du pod), pas de l'image.
- **Pas de Langfuse ici** : guide 07, une fois l'API en place.
- **Pas de tests d'intégration automatisés sur le cluster** : la CI reste hors ligne
  (ADR 003) ; le cluster local se vérifie à la main, avec ce guide.
