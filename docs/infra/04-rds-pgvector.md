# Guide 04 — RDS PostgreSQL avec pgvector : la base managée, son accès, l'index

**Durée** : 20 minutes. **Prérequis** : guide 03 (environnement créé). **Coût** :
~0,02 $/h + ~2 $/mois de stockage, détruit avec l'environnement. **Code** :
`infra/terraform/envs/dev/rds.tf`, `secrets.tf` (URL de la base),
`src/llm_testbench/ingest/sql/001_schema.sql`.

---

## Le problème

En local, Postgres est un `StatefulSet` qu'on relance sans état d'âme. En cloud, une base
qu'on opère soi-même coûte des nuits : sauvegardes, correctifs, disque plein, bascule.
RDS vend exactement ça. La question devient : **quelle instance, quel réseau, quel mot de
passe, et comment pgvector arrive-t-il dedans** — et, pour ce banc, comment l'API trouve
la base sans qu'un secret ne traverse un fichier.

## Les options

| Option | Verdict |
|---|---|
| **RDS PostgreSQL 16, `db.t4g.micro`, mono-AZ** | **Retenu** : la plus petite instance Graviton (2 vCPU partagés, 1 Go), suffisante pour 5 000 abstracts et une poignée de requêtes par seconde ; pgvector est disponible nativement. |
| Aurora Serverless v2 | Monte et descend à zéro (0,5 ACU minimum ≈ 0,06 $/h) : plus cher qu'un micro allumé, intéressant pour un environnement qu'on laisse en place sans trafic. Noté pour la phase 5. |
| Postgres dans le cluster (comme en local) | Zéro coût RDS, mais un volume EBS à gérer et pas de sauvegarde gérée : c'est le choix que le brief refuse pour le cloud. |
| Un service vectoriel dédié | Refusé par le brief (Postgres + pgvector, ADR 007). |

## Lecture guidée du code réel

**[`rds.tf`](../../infra/terraform/envs/dev/rds.tf)** — le module `terraform-aws-modules/rds` :

- `engine_version = "16"`, `family = "postgres16"` : la **famille** est celle du groupe de
  paramètres ; oubliée ou décalée, l'apply échoue tard avec un message obscur.
- `manage_master_user_password = true` : RDS génère le mot de passe et le range dans
  Secrets Manager, avec rotation possible. Personne ne le voit passer dans une variable.
- `db_subnet_group_name = module.vpc.database_subnet_group_name` : la base vit dans les
  sous-réseaux `database`, sans route vers Internet (guide 02).
- `vpc_security_group_ids = [aws_security_group.rds.id]` avec **une seule règle
  d'entrée** : le port 5432 depuis le groupe de sécurité des nœuds EKS. Pas d'adresse,
  pas de CIDR : une identité de groupe de sécurité, qui suit les nœuds quand ils changent.
- `multi_az = false`, `backup_retention_period = 1`, `skip_final_snapshot = true`,
  `deletion_protection = false` : les quatre réglages qu'on inverse en production, ici
  assumés pour un environnement jetable. Ils sont explicites pour être relus.
- `apply_immediately = true` : un changement de paramètre s'applique tout de suite, pas
  à la prochaine fenêtre de maintenance (qu'on n'atteindra jamais).
- `parameters` : `log_min_duration_statement = 1000` — chaque requête de plus d'une
  seconde apparaît dans les logs. Le premier outil de diagnostic d'un index HNSW mal
  dimensionné.
- `performance_insights_enabled = false`, `monitoring_interval = 0` : les deux postes
  de coût optionnels du monitoring RDS, désactivés en dev.

**[`secrets.tf`](../../infra/terraform/envs/dev/secrets.tf)**, partie base : Terraform lit
le secret géré par RDS (`data.aws_secretsmanager_secret_version.rds_master`), compose
l'URL `postgresql://user:mot-de-passe@hôte:5432/testbench` et l'écrit dans un secret
`llm-testbench/dev/database-url`. External Secrets (guide 05) la livrera au pod telle
quelle. **Compromis documenté** : le mot de passe transite par l'état Terraform (chiffré,
guide 00). La réponse de production : un template External Secrets qui compose l'URL
dans le cluster, ou l'authentification IAM à la base (`iam_database_authentication_enabled`).

**[`001_schema.sql`](../../src/llm_testbench/ingest/sql/001_schema.sql)** : c'est
l'application, pas Terraform, qui crée l'extension et les tables au démarrage
(`CREATE EXTENSION IF NOT EXISTS vector`). Sur RDS, l'utilisateur maître a le droit de
créer les extensions de la liste supportée, dont pgvector.

## Exécution

**1. Vérifier l'instance** :

```bash
aws rds describe-db-instances --db-instance-identifier llm-testbench-dev \
  --query 'DBInstances[0].[DBInstanceStatus,Engine,EngineVersion,DBInstanceClass,PubliclyAccessible,MultiAZ]' --output table
```

Attendu : `available`, `postgres`, `16.x`, `db.t4g.micro`, `False`, `False`.

**2. Vérifier que la base n'est pas joignable de votre Mac** (c'est le résultat attendu) :

```bash
cd infra/terraform/envs/dev && terraform output -raw rds_address ; cd -
nc -z -w 3 <adresse> 5432 || echo "injoignable depuis Internet : correct"
```

**3. Ingérer depuis le cluster.** L'index doit être construit *dans* RDS ; le plus simple
est un pod éphémère avec l'image de l'API et les secrets du pod :

```bash
kubectl -n llm-testbench run ingest --rm -i --restart=Never \
  --image=$(cd infra/terraform/envs/dev && terraform output -raw ecr_repository_url):$(git rev-parse --short HEAD) \
  --overrides='{"spec":{"containers":[{"name":"ingest","image":"IMAGE","envFrom":[{"secretRef":{"name":"llm-testbench-api-secrets"}}],"command":["python","-m","llm_testbench.ingest.cli","scifact"]}]}}' \
  --image-pull-policy=IfNotPresent
```

(Remplacez `IMAGE` par la même image que `--image`.) Attendu : le rapport JSON de
l'ingestion — ~5 000 documents, ~5 000 chunks, ~0,05 $ d'embeddings.

**4. Constater la readiness** :

```bash
kubectl -n llm-testbench get pods            # api 1/1 READY
kubectl -n llm-testbench port-forward svc/api 8000:80 &
curl -s localhost:8000/readyz
curl -s localhost:8000/sources | python3 -m json.tool
```

**5. Regarder la base de l'intérieur** (depuis un pod, pas de votre Mac) :

```bash
kubectl -n llm-testbench run psql --rm -it --restart=Never --image=postgres:16 \
  --env="PGURL=$(kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data.LLM_TESTBENCH_DATABASE_URL}' | base64 -d)" \
  -- sh -c 'psql "$PGURL" -c "\dx" -c "select index_key, embedding_model, dimensions from indexes" -c "select count(*) from chunks"'
```

Attendu : l'extension `vector` listée, une ligne d'index, ~5 000 chunks.

## Les pièges

- **Le mot de passe dans l'URL doit être encodé** : RDS génère des caractères spéciaux
  (`/`, `@`, `%`). `secrets.tf` passe par `urlencode()` ; sans ça, une URL sur trois est
  invalide — et l'erreur ne dit pas pourquoi.
- **`db.t4g.micro` a des crédits CPU** : sous charge soutenue (phase 5), il s'effondre
  quand les crédits sont épuisés. La montée en gamme est une variable.
- **La famille de paramètres** doit suivre la version majeure : passer en Postgres 17
  demande `family = "postgres17"`, pas seulement `engine_version`.
- **Un `terraform destroy` avec `skip_final_snapshot = false`** demande un nom de
  snapshot et échoue sinon. En dev, `true` ; en production, l'inverse, toujours.
- **Le HNSW se construit à l'insertion** : ingérer 5 000 vecteurs de 1 536 dimensions
  prend une minute sur un micro ; à 500 000, on crée l'index *après* le chargement
  (phase 3, matrice d'expériences).
- **Le groupe de sécurité référence celui des nœuds** : si vous recréez le cluster EKS
  seul, la règle suit le nouveau groupe ; si vous ajoutez des nœuds hors du module (Karpenter),
  vérifiez qu'ils portent le même groupe.

## Questions d'entretien

<details><summary><b>1. RDS ou Aurora, quand ?</b></summary>

RDS est Postgres tel quel sur une instance : prévisible, moins cher à petite taille, une
seule zone si on veut. Aurora réécrit le stockage (réplication à six copies, lectures
distribuées, Serverless v2 qui suit la charge) : plus cher au repos, meilleur pour une
charge variable ou une haute disponibilité exigée. Pour un banc d'essai : RDS ; pour
l'environnement de dev d'une équipe qui l'oublie allumé : Aurora Serverless.
</details>

<details><summary><b>2. Comment l'application obtient-elle le mot de passe sans qu'il soit dans le code ?</b></summary>

RDS le génère dans Secrets Manager ; External Secrets le lit avec l'identité du pod et
le pose dans un `Secret` Kubernetes ; le pod le reçoit en variable d'environnement. Rien
n'est écrit par un humain, tout est tracé par CloudTrail. La rotation change la valeur
dans Secrets Manager, External Secrets la resynchronise, le pod redémarre.
</details>

<details><summary><b>3. Pourquoi une base sans accès public, et comment l'administrer alors ?</b></summary>

Une base publique est une cible permanente de scans. Sans accès public, on administre
depuis le VPC : un pod éphémère (comme ci-dessus), un bastion, ou SSM Session Manager
avec transfert de port. Le port-forward Kubernetes vers un pod `psql` est l'outil le plus
simple au quotidien.
</details>

<details><summary><b>4. pgvector sur RDS : quelles limites ?</b></summary>

La version de l'extension suit celle proposée par RDS (souvent quelques mois de retard) ;
l'index HNSW tient en mémoire ou la base rame — la mémoire de l'instance devient le
paramètre de dimensionnement principal, avant le CPU. Et `CREATE EXTENSION` demande un
rôle avec le privilège, ce que l'utilisateur maître a.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas d'authentification IAM à la base** : élégante (plus de mot de passe du tout),
  mais elle demande un jeton renouvelé toutes les 15 minutes côté application ; à
  regarder en phase 5 avec le runbook « le provider est indisponible ».
- **Pas de réplica de lecture ni de Multi-AZ** : rien à protéger en dev.
- **Pas de RDS Proxy** : utile quand des centaines de connexions courtes saturent la
  base (fonctions serverless) ; notre pool psycopg suffit.
- **Pas de Performance Insights** : quelques euros par mois pour des graphiques qu'on ne
  regardera pas avant la phase 5.
