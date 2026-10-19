# Guide 05 — Les secrets : Secrets Manager, External Secrets, identités de pods

**Durée** : 15 minutes. **Prérequis** : guide 03 (cluster et add-ons). **Coût** :
~0,40 $/mois par secret (trois clés, plus le secret géré par RDS), détruits avec
l'environnement. **Code** :
`infra/terraform/envs/dev/secrets.tf`, `iam.tf`, `infra/k8s/dev/cluster-secret-store.yaml`,
`infra/helm/llm-testbench-api/templates/externalsecret.yaml`.

---

## Le problème

Une clé d'API LLM donne accès à un compte facturé à l'usage : c'est un moyen de paiement.
Elle doit arriver dans le pod sans passer par git, par une image, par un fichier de
valeurs Helm, ni par le terminal d'un collègue. Et quand elle change (rotation, fuite),
le changement doit se propager sans redéploiement manuel.

## Les options

| Option | Verdict |
|---|---|
| `Secret` Kubernetes créé à la main | Ce qu'on fait en local (`make k8s-secrets`) : simple, mais la vérité est sur un poste de travail, et rien ne resynchronise. |
| Secret chiffré dans git (SOPS, Sealed Secrets) | Bon pour GitOps ; mais les clés d'API changent hors de git et la source de vérité serait dédoublée. |
| **Secrets Manager + External Secrets Operator** | **Retenu** : la vérité est dans Secrets Manager (audité, rotatif), l'opérateur la copie dans un `Secret` Kubernetes et la resynchronise ; l'authentification passe par l'identité de pod. |
| SSM Parameter Store (SecureString) | Gratuit en standard, sans rotation intégrée ni versionnage riche. Correct pour de la configuration, moins pour des moyens de paiement. |
| Secrets Store CSI Driver | Monte les secrets en fichiers, sans `Secret` Kubernetes ; plus de pièces mobiles pour un gain limité ici. |

## Lecture guidée du code réel

**[`secrets.tf`](../../infra/terraform/envs/dev/secrets.tf)** — trois secrets de clés
(`llm-testbench/dev/anthropic-api-key`, `openai-api-key`, `openrouter-api-key`), et rien
d'autre : l'URL de base n'est pas un secret Terraform (voir le template plus bas). Deux
détails qui comptent :

- `recovery_window_in_days = 0` : Secrets Manager garde normalement un secret supprimé
  30 jours (et le nom reste bloqué). Zéro, pour qu'un `infra-down` suivi d'un `infra-up`
  ne bute pas sur « secret déjà planifié pour suppression ».
- la version initiale vaut `REPLACE_ME` avec `ignore_changes = [secret_string]` :
  Terraform crée le secret mais **n'en gère jamais la valeur**. Vous la posez à la main ;
  Terraform ne l'écrasera jamais, et elle n'entrera jamais dans l'état.

**[`iam.tf`](../../infra/terraform/envs/dev/iam.tf)** — le rôle `external_secrets` : lire
et décrire les secrets sous le préfixe `llm-testbench/dev/*` et le secret géré par RDS
(`module.rds.db_instance_master_user_secret_arn`), rien d'autre ; associé par
Pod Identity au ServiceAccount `external-secrets` du namespace du même nom (créé par le
chart de l'opérateur).

**[`cluster-secret-store.yaml`](../../infra/k8s/dev/cluster-secret-store.yaml)** — le
`ClusterSecretStore` dit à l'opérateur *où* lire (Secrets Manager, région) et *comment*
s'authentifier : rien de déclaré, donc la chaîne d'identifiants par défaut du SDK, qui
trouve l'identité de pod. Pas de clé, pas d'ARN de rôle : l'association est faite par
Terraform.

**[`externalsecret.yaml`](../../infra/helm/llm-testbench-api/templates/externalsecret.yaml)**
— dans le namespace de l'API, un `ExternalSecret` par déploiement : chaque entrée
`data` associe une variable d'environnement à une clé Secrets Manager ; l'opérateur
fabrique le `Secret` `llm-testbench-api-secrets` que le Deployment consomme, et le
rafraîchit toutes les heures (`refreshInterval`). Quand `database.masterSecretArn` est
renseigné (par `make deploy` ou le workflow, depuis les sorties Terraform / l'API RDS),
deux entrées `data` supplémentaires lisent `username` et `password` dans le secret géré par
RDS (`remoteRef.property`), et un bloc `target.template` (moteur v2) compose
`LLM_TESTBENCH_DATABASE_URL` dans le cluster, mot de passe encodé par `urlquery`. Lisez les
accolades à deux niveaux : `{{ .Values... }}` est rendu par Helm, `{{ .db_password }}` est
laissé tel quel pour l'opérateur. C'est la réponse de production au compromis d'avant
(ADR 009) : le mot de passe ne quitte Secrets Manager que pour le `Secret` Kubernetes.

## Exécution

**1. Poser les vraies valeurs** (une seule fois par environnement, depuis votre poste) :

```bash
aws secretsmanager put-secret-value --secret-id llm-testbench/dev/anthropic-api-key --secret-string "$ANTHROPIC_API_KEY"
aws secretsmanager put-secret-value --secret-id llm-testbench/dev/openai-api-key --secret-string "$OPENAI_API_KEY"
aws secretsmanager put-secret-value --secret-id llm-testbench/dev/openrouter-api-key --secret-string "$OPENROUTER_API_KEY"
```

Chargez `.env` avant (`set -a; source .env; set +a`) pour ne pas coller de clé dans
l'historique du shell. L'URL de base, elle, est composée par l'opérateur à partir du secret
géré par RDS : rien à poser.

**2. Vérifier la synchronisation** :

```bash
kubectl -n llm-testbench get externalsecret api        # STATUS SecretSynced, READY True
kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data}' | python3 -c "import sys,json; print(list(json.load(sys.stdin)))"
```

Attendu : les quatre clés (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`,
`LLM_TESTBENCH_DATABASE_URL`). Si `READY False` : `kubectl describe externalsecret api`
donne la raison (accès refusé → association Pod Identity, préfixe ou ARN de la politique
IAM ; secret introuvable → nom ; erreur de template → une clé `data` manquante).

Vérifiez l'URL composée **sans afficher le mot de passe** :

```bash
kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data.LLM_TESTBENCH_DATABASE_URL}' \
  | base64 -d | sed -E 's#//[^:]+:[^@]+@#//<user>:<password>@#'
```

Attendu : `postgresql://<user>:<password>@<adresse RDS>:5432/testbench`. Si le pod ne se
connecte pas alors que l'adresse est bonne, c'est l'encodage : comparez la longueur du mot
de passe dans Secrets Manager et dans le `Secret` — `urlquery` allonge les caractères
réservés (`%23` pour `#`).

**3. Prouver que le pod n'a aucune clé AWS** :

```bash
kubectl -n llm-testbench exec deploy/api -- env | grep -c AWS_ACCESS_KEY_ID || echo "aucune clé statique"
kubectl -n external-secrets exec deploy/external-secrets -- env | grep AWS_CONTAINER_CREDENTIAL_FULL_URI
```

**4. Faire tourner une clé** : changez la valeur dans Secrets Manager
(`put-secret-value`), attendez le `refreshInterval` (ou annotez l'`ExternalSecret` avec
`force-sync=$(date +%s)`), puis redémarrez l'API (`kubectl rollout restart deploy/api`) :
un processus ne relit pas ses variables d'environnement.

## Les pièges

- **La suppression avec fenêtre de récupération** bloque le nom pendant 30 jours : sans
  `recovery_window_in_days = 0`, le deuxième `infra-up` échoue.
- **`ignore_changes` coupe dans les deux sens** : Terraform ne restaurera pas non plus
  une valeur effacée par erreur. La sauvegarde de la valeur, c'est vous.
- **Le `Secret` synchronisé n'est pas relu par un pod en marche** : après une rotation,
  redémarrez. Un outil comme Reloader peut automatiser ce redémarrage sur changement de
  `Secret` ; à ajouter si les rotations deviennent fréquentes.
- **Le préfixe IAM est strict** : un secret nommé hors de `llm-testbench/dev/` est
  invisible pour l'opérateur, par construction. C'est une protection, pas un bug.
- **Un `ClusterSecretStore` est global au cluster** : n'importe quel namespace peut y
  créer un `ExternalSecret`. Dans un cluster partagé, un `SecretStore` par namespace et
  des rôles distincts.
- **Le secret RDS géré n'est pas au format attendu** par l'application (JSON
  `{username, password}`) : d'où le template de l'`ExternalSecret`, qui lit deux propriétés et
  compose l'URL. **`mergePolicy` vaut `Replace` par défaut** : seules les clés écrites par le
  template entrent dans le `Secret`, donc le template redit chaque clé d'API — en oublier une,
  c'est la faire disparaître du pod sans message d'erreur.

## Questions d'entretien

<details><summary><b>1. Où est la source de vérité d'un secret, et pourquoi pas dans le cluster ?</b></summary>

Dans un gestionnaire de secrets (Secrets Manager) : chiffré par KMS, versionné, audité
par CloudTrail, avec rotation. Un `Secret` Kubernetes est encodé en base64 dans etcd
(chiffré au repos seulement si on l'a configuré, ce que `create_kms_key` fait ici) et
lisible par quiconque a `get secrets` dans le namespace. Le `Secret` Kubernetes est une
copie de travail, pas la vérité.
</details>

<details><summary><b>2. Comment l'opérateur s'authentifie-t-il auprès d'AWS ?</b></summary>

Par l'identité de pod : son ServiceAccount est associé à un rôle IAM dont la politique se
limite au préfixe des secrets du projet. Aucune clé d'accès. Le SDK AWS dans le pod trouve
les identifiants temporaires via l'agent Pod Identity, exactement comme l'API pour Bedrock.
</details>

<details><summary><b>3. Secrets Manager ou Parameter Store ?</b></summary>

Parameter Store standard est gratuit et suffit pour de la configuration, y compris
chiffrée (SecureString). Secrets Manager coûte 0,40 $/secret/mois et apporte la rotation
intégrée (RDS, Lambda), le versionnage riche et la réplication. Règle simple : moyen de
paiement ou mot de passe qui tourne → Secrets Manager ; réglage → Parameter Store.
</details>

<details><summary><b>4. Que se passe-t-il quand une clé fuit ?</b></summary>

Révoquer chez le fournisseur, poser la nouvelle valeur dans Secrets Manager, forcer la
synchronisation, redémarrer les pods ; puis lire CloudTrail pour savoir qui a lu le secret
et quand. La phase 5 ajoutera le kill switch de coût : une clé qui fuit se voit d'abord
sur la facture.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas de rotation automatique des clés LLM** : les fournisseurs n'exposent pas d'API de
  rotation ; la rotation est manuelle par construction.
- **Pas de Reloader** : une rotation rare se gère avec un `rollout restart`.
- **Pas d'authentification IAM à la base** (guide 04) : le mot de passe existe toujours,
  mais il ne quitte plus Secrets Manager que pour le `Secret` Kubernetes, composé dans le
  cluster. Le template a remplacé le compromis Terraform le 2026-10-19 (ADR 009).
- **Pas de SecretStore par namespace** : un seul locataire sur ce cluster.
