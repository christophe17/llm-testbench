# Guide 07 — Observabilité : Langfuse self-hosted, traces OpenTelemetry, coût par span

**Durée** : 30 minutes dont 10 d'attente. **Prérequis** : guide 01 (cluster local), VM
Docker à 12 Go recommandé (8 Go passent, à l'étroit). **Coût** : 0 € en local. **Code** :
`src/llm_testbench/obs/tracing.py`, `infra/k8s/local/observability/`,
`infra/helm/langfuse/values-local.yaml`, cibles `make langfuse-*`.

---

## Le problème

Un appel LLM sans trace est une boîte noire facturée : on ne sait ni quel prompt exact est
parti, ni quel modèle a répondu, ni combien de tokens ont été lus depuis le cache, ni ce que
ça a coûté, ni pourquoi c'était lent. Et quand la qualité baisse « sans changement de code »
(runbook de la phase 5), la trace est la seule preuve. Il faut donc, dès le premier appel,
**une trace par appel** avec ses attributs, envoyée à un système qui sait les lire, les
agréger et les afficher — **chez nous**, parce que les traces contiennent les prompts, donc
les données (gouvernance, ADR 006).

## Les options

| Option | Verdict |
|---|---|
| SDK Langfuse dans le code (décorateurs, `langfuse.trace()`) | Simple, mais le code applicatif dépend d'un fournisseur de traces. Refusé : on instrumente en **OpenTelemetry**, standard, et Langfuse n'est qu'un récepteur. |
| Langfuse Cloud | Zéro infra, mais les prompts partent chez un tiers : contraire au brief (self-hosted). |
| **Langfuse self-hosted, alimenté en OTLP** | **Retenu** : le code n'a qu'un exporteur OTel ; Langfuse, Tempo ou Jaeger se branchent sans le modifier. |
| Grafana Tempo + dashboards maison | Générique, sans la lecture « LLM » (prompts, coûts, sessions). Prometheus/Grafana arrivent en phase 5 pour les métriques, pas pour remplacer Langfuse. |

**Pour ClickHouse en local** (Langfuse v4 stocke les événements dans ClickHouse) : le chart
officiel 2.x le déploie via un **opérateur** (CRD, trois keepers, 2 Go de mémoire réservés) —
trop lourd pour « le strict nécessaire » sur un Mac. Le chart accepte un ClickHouse externe
non clusterisé : **un StatefulSet de 60 lignes**, image officielle multi-arch, fait l'affaire.

## Lecture guidée du code réel

**[`obs/tracing.py`](../../src/llm_testbench/obs/tracing.py)** — deux familles d'attributs
posés sur chaque span : `gen_ai.*` (**conventions sémantiques GenAI** d'OpenTelemetry :
opération, provider, modèle demandé et servi, tokens, raison de fin) et `llm_testbench.*`
(ce que la convention ne couvre pas et que le banc mesure : coût, cache, tentatives,
gouvernance, empreinte du prompt). `configure_tracing` installe un fournisseur de traces
avec, au choix, un exporteur fourni (mémoire, pour les tests et les notebooks) ou un
exporteur **OTLP/HTTP** vers un endpoint ; `langfuse_otlp_headers` fabrique l'en-tête
Basic auth `clé publique:clé secrète` que Langfuse attend.

**[`app/main.py`](../../src/llm_testbench/app/main.py)**, `_configure_tracing_from` : l'API
lit `LLM_TESTBENCH_OTLP_ENDPOINT` et les deux clés dans ses réglages ; sans endpoint, les
spans sont des no-op — le code applicatif ne change pas d'une ligne.

**[`infra/k8s/local/observability/clickhouse.yaml`](../../infra/k8s/local/observability/clickhouse.yaml)**
— un StatefulSet mono-nœud, mot de passe en clair (local uniquement), sonde `/ping`,
10 Go de volume `local-path`.

**[`infra/helm/langfuse/values-local.yaml`](../../infra/helm/langfuse/values-local.yaml)** —
les points à lire :

- `clickhouse.deploy: false`, `crdCheck: false`, `host`, `cluster.enabled: false`,
  `migration.url` : le chart utilise notre ClickHouse et ne cherche pas l'opérateur ;
- `postgresql`, `redis` (Valkey), `s3` (SeaweedFS) embarqués, volumes réduits — Langfuse v4
  a besoin des quatre : Postgres pour les métadonnées, ClickHouse pour les événements,
  Redis pour les files, S3 pour les charges utiles brutes ;
- `langfuse.additionalEnv` avec `LANGFUSE_INIT_*` : **initialisation headless** —
  organisation, projet, utilisateur et **clés d'API** créés au premier démarrage, pour que
  l'API du banc puisse tracer sans qu'un humain clique dans l'interface. Les valeurs sont des
  constantes de dev ; en cloud (phase 5), elles viendront de Secrets Manager.

## Exécution

**1. Déployer** (images ~1,5 Go la première fois, ~10 minutes) :

```bash
make langfuse-up
kubectl -n observability get pods
```

Attendu : `clickhouse-0`, `langfuse-postgresql-0`, `langfuse-redis-*`, `langfuse-s3-*`,
`langfuse-web-*`, `langfuse-worker-*` en `Running`. Le pod `web` redémarre deux ou trois
fois pendant les migrations ClickHouse (46 migrations) : normal. **Si le `worker` a démarré
avant la fin des migrations, redémarrez-le** (`kubectl -n observability rollout restart
deploy/langfuse-worker`) : il aurait sinon des erreurs « table does not exist » et ne
consommerait pas les files.

**2. Ouvrir l'interface** :

```bash
make langfuse-port-forward &
open http://localhost:3000     # dev@llm-testbench.local / local-only-password
```

Projet `phase-1` déjà créé (initialisation headless).

**3. Envoyer une trace depuis la couche LLM, sans clé ni réseau** — le provider simulé
suffit, la trace est réelle :

```bash
uv run python - <<'PY'
import asyncio
from llm_testbench.llm import CompletionRequest, DataClass, Message, ModelRef, Role
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.testing import Step, anthropic_message, scripted_anthropic_provider
from llm_testbench.obs.tracing import configure_tracing, get_tracer, langfuse_otlp_headers
tp = configure_tracing(otlp_endpoint="http://localhost:3000/api/public/otel/v1/traces",
                       otlp_headers=langfuse_otlp_headers("pk-lf-local-0000000000000000", "sk-lf-local-0000000000000000"),
                       set_global=False)
client = LLMClient.from_settings(tracer=get_tracer(tp))
client.register_provider("anthropic", scripted_anthropic_provider([Step(json_body=anthropic_message("Paris.", input_tokens=900, output_tokens=7))])[0])
req = CompletionRequest(model=ModelRef.parse("anthropic/claude-sonnet-5"),
                        messages=(Message(role=Role.USER, content="Capitale de la France ?"),), data_class=DataClass.PUBLIC)
print(asyncio.run(client.complete(req)).cost_usd); tp.force_flush(); tp.shutdown()
PY
```

**4. La relire par l'API v2** (Langfuse v4 fonctionne en mode `events_only` : les anciens
endpoints `/api/public/traces` et `/observations` répondent 404, c'est documenté) :

```bash
curl -s -u pk-lf-local-0000000000000000:sk-lf-local-0000000000000000 \
  "http://localhost:3000/api/public/v2/observations?limit=1" | python3 -m json.tool | head -40
```

Attendu : une observation `GENERATION` nommée `chat anthropic/claude-sonnet-5`, `model`
`claude-sonnet-5`, `usage` 900/7, et un **coût calculé par Langfuse** (`calculatedTotalCost`)
égal à celui de notre table de prix (0,00187 $ pour 900 + 7 tokens sur Sonnet 5). Deux
tables de prix indépendantes qui tombent d'accord : un contrôle croisé gratuit.

**5. Brancher l'API du cluster** : `values-local.yaml` porte déjà l'endpoint in-cluster
(`http://langfuse-web.observability:3000/...`) et les clés locales. Redéployez l'API
(guide 01, étape 4 ou `tilt up`) : chaque `/chat` produit une trace.

**6. Lire une trace dans l'interface** : Tracing → Observations. Ouvrez-en une : les
attributs `gen_ai.*` et `llm_testbench.*` sont dans les métadonnées, le modèle et l'usage
dans l'en-tête, le coût calculé à droite.

## Les pièges

- **Langfuse v4 = `events_only`** : les guides et SDK d'avant 2026 parlent de
  `/api/public/traces` ; ils renvoient 404. Les lectures passent par
  `/api/public/v2/observations` (bornez par `fromStartTime`/`toStartTime`) et Metrics v2.
- **L'ordre de démarrage** : le worker qui démarre pendant les migrations reste en erreur
  sans redémarrer. Le symptôme : les charges utiles sont bien dans le bucket S3
  (`otel/<projet>/...json`), rien n'arrive dans ClickHouse. Un `rollout restart` suffit.
- **Le coût Langfuse à 0 sur la toute première observation** : sa table de prix se charge
  en cache au premier passage ; la deuxième observation est chiffrée. Notre coût, lui, est
  calculé côté client : c'est celui qu'on utilise pour les tableaux.
- **L'OTLP renvoie 200 même sur un corps vide** : un 200 ne prouve pas l'ingestion ;
  seule la relecture (étape 4) la prouve.
- **Mémoire** : ClickHouse + SeaweedFS + Postgres + Valkey + web + worker ≈ 2,5 Go réservés.
  À 8 Go de VM avec notre Postgres et l'API, ça passe ; avec un modèle local (phase 6), non.
- **`$path` en zsh est `PATH`** : une boucle `for path in …` dans un script de vérification
  a effacé le PATH du shell pendant le diagnostic. Vingt minutes perdues pour un nom de
  variable — consigné pour que ça n'arrive qu'une fois.

## Questions d'entretien

<details><summary><b>1. Pourquoi instrumenter en OpenTelemetry plutôt qu'avec le SDK de Langfuse ?</b></summary>

Pour que le code applicatif ne dépende d'aucun fournisseur de traces : un exporteur OTLP se
pointe vers Langfuse, Tempo, Jaeger ou un collecteur sans changer une ligne. Les conventions
sémantiques GenAI donnent un vocabulaire que tous savent lire. Le prix : quelques attributs
spécifiques (sessions, scores) sont moins directs qu'avec le SDK natif.
</details>

<details><summary><b>2. Que contient une trace d'appel LLM utile, et pourquoi ces champs ?</b></summary>

Le modèle demandé *et* le modèle servi (un provider peut changer de révision), les tokens
d'entrée, de sortie, lus et écrits en cache (le coût en dépend), la raison de fin (une réponse
tronquée n'est pas une réponse), le coût, le nombre de tentatives, la décision de gouvernance,
l'empreinte du prompt (pour relier un chiffre au texte exact qui l'a produit).
</details>

<details><summary><b>3. Pourquoi Langfuse a-t-il besoin de quatre stockages ?</b></summary>

Postgres pour les métadonnées transactionnelles (projets, utilisateurs, clés), ClickHouse
pour les événements analytiques (volumineux, requêtés par agrégats), Redis pour les files
d'ingestion asynchrone, S3 pour les charges utiles brutes (prompts, réponses) qu'on ne veut
pas dans une base. C'est l'architecture d'un système d'analytique événementielle, pas
d'une application CRUD.
</details>

<details><summary><b>4. Les traces contiennent les prompts : quelles conséquences ?</b></summary>

Elles contiennent donc les données des utilisateurs : même politique de gouvernance que les
appels eux-mêmes (self-hosted, rétention, accès), masquage des PII avant export (phase 7),
et un contrôle d'accès à l'interface. Une trace envoyée à un SaaS de traces est une donnée
qui sort.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas de collecteur OTel ni de Prometheus/Grafana** : phase 5, quand il y aura des
  métriques de charge à agréger (générateur de trafic) ; en phase 1, Langfuse suffit.
- **Pas de Langfuse en cloud** : il suivra l'API sur EKS en phase 5 avec le même chart
  (ClickHouse via l'opérateur, cette fois, sur des nœuds dimensionnés).
- **Pas de scores ni de sessions** : ils arrivent avec le juge (phase 2) et la mémoire
  d'agent (phase 4).
- **Pas de masquage des prompts dans les traces** : données publiques en phase 1 ; Presidio
  en phase 7.
