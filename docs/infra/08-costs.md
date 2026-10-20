# Guide 08 — Les coûts : ce que chaque module coûte, allumé et éteint, et comment on le sait

**Durée** : 15 minutes. **Prérequis** : aucun pour la lecture ; guide 03 pour les
vérifications. **Code** : `infra/terraform/envs/dev/README.md` (table par module),
`Makefile` (`infra-up`, `infra-down`), `config/llm_pricing.toml` (le coût des appels LLM,
qui n'est pas de l'infra mais qui pèse autant).

---

## Le problème

Un compte cloud personnel ne coûte rien tant qu'il est vide, et une fortune quand on y
oublie une chose. Trois catégories de coûts se cachent derrière un « environnement de
dev » : ce qui se facture **à l'heure qu'il serve ou non** (plan de contrôle EKS, nœuds,
NAT Gateway, instance RDS), ce qui se facture **au stockage** (EBS, S3, ECR, snapshots,
logs) et survit à un `destroy` incomplet, et ce qui se facture **à l'usage** (trafic NAT,
appels LLM). Le positionnement de ce projet — *je chiffre ce que je déploie* — commence
par savoir lesquels de ces postes tournent en ce moment.

## Les options pour ne pas payer un cluster qui dort

| Option | Verdict |
|---|---|
| Laisser tourner et « faire attention » | Non : la NAT et le plan de contrôle ne préviennent pas. |
| Réduire à zéro nœud le soir (`node_desired_size = 0`) | Économise les nœuds (~0,08 $/h), pas EKS (0,10 $/h), ni NAT, ni RDS. Insuffisant. |
| **Détruire et recréer** (`make infra-down` / `make infra-up`) | **Retenu** : ~20 minutes de création, zéro coût dormant. Tout l'environnement est du code ; ce qui doit survivre (données) est régénérable ou dans S3. |
| Arrêter RDS (7 jours max) | Complément possible ; RDS redémarre seul après 7 jours. Inutile si on détruit. |

## Lecture guidée : la table des coûts

Lisez [`infra/terraform/envs/dev/README.md`](../../infra/terraform/envs/dev/README.md).
Trois colonnes : la ressource, son coût **allumé**, son coût **éteint** (après
`infra-down`). L'ordre des postes allumés, du plus cher au moins cher : plan de contrôle
EKS, nœuds, NAT Gateway, RDS. Les postes éteints qui restent : ECR (images, jusqu'à la
destruction), Secrets Manager (0,40 $/secret/mois au prorata), logs CloudWatch résiduels.

Total allumé : **~0,25 $/h, ~6 $/jour**. Total éteint : **~0 $**. Un mois oublié :
~180 $ — c'est le scénario que l'alerte du guide 00 (55 $/mois) attrape au bout de
neuf jours, et que `make infra-down` évite tout court.

**Les tags**, posés par le bloc `default_tags` de chaque module (`Project`, `Environment`,
`ManagedBy`, `Module`), sont ce qui rend le coût *par module* lisible dans Cost Explorer.
Sans tags, la facture est un total ; avec, une table.

## Exécution

**1. Activer les tags de répartition des coûts** (une fois par compte ; jusqu'à 24 h
pour apparaître) :

```bash
aws ce update-cost-allocation-tags-status --cost-allocation-tags-status \
  TagKey=Project,Status=Active TagKey=Module,Status=Active TagKey=Environment,Status=Active
```

**2. Lire le coût des sept derniers jours par service** :

```bash
aws ce get-cost-and-usage --time-period Start=$(date -v-7d +%F),End=$(date +%F) \
  --granularity DAILY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[].{day:TimePeriod.Start,cost:Groups[?Metrics.UnblendedCost.Amount>`0.01`].[Keys[0],Metrics.UnblendedCost.Amount]}' --output json
```

**3. Par module, une fois les tags actifs** :

```bash
aws ce get-cost-and-usage --time-period Start=$(date -v-7d +%F),End=$(date +%F) \
  --granularity MONTHLY --metrics UnblendedCost --group-by Type=TAG,Key=Module --output table
```

**4. Vérifier qu'il ne reste rien après `make infra-down`** :

```bash
aws eks list-clusters ; aws rds describe-db-instances --query 'DBInstances[].DBInstanceIdentifier'
aws ec2 describe-nat-gateways --filter Name=state,Values=available --query 'NatGateways[].NatGatewayId'
aws ec2 describe-volumes --filter Name=status,Values=available --query 'Volumes[].[VolumeId,Size]'
aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerName'
```

Tout doit être vide. Les volumes EBS `available` et les équilibreurs sont les deux
restes classiques d'un cluster détruit (créés par Kubernetes, inconnus de Terraform).

**5. Le coût des appels LLM**, lui, se lit dans nos traces (attribut
`llm_testbench.cost_usd`, notebook 1) et se projette avec la table de prix :

```bash
uv run python -c "
from llm_testbench.llm.cost import PricingTable; from llm_testbench.llm.types import Usage
p = PricingTable.from_settings(); u = Usage(input_tokens=1000, output_tokens=300)
print({m: round(p.cost_usd(m, u) * 100_000, 2) for m in p.models if p.models[m].output_per_mtok})"
```

Attendu : le coût de 100 000 appels par modèle — l'ordre de grandeur qui décide d'un
cache sémantique, d'un modèle plus petit, ou du self-hosting (phase 6).

## Les pièges

- **Les restes après destruction** : volumes EBS orphelins, équilibreurs créés par un
  `Service type: LoadBalancer`, snapshots RDS si `skip_final_snapshot` était à `false`,
  logs CloudWatch. Vérifiez (étape 4) plutôt que de supposer.
- **Le support étendu EKS** (guide 03) multiplie le plan de contrôle par six sans changer
  une ligne de code.
- **Le trafic NAT au gigaoctet** : tirer une image de 2 Go dix fois par jour, ce sont des
  centimes ; télécharger un jeu de données de 50 Go depuis un pod, un euro par
  téléchargement. Les caches de jeux vivent sur le bucket S3 de l'environnement (même
  région : gratuit), pas sur Hugging Face à chaque fois.
- **Cost Explorer a 24 h de retard** et l'alerte de budget jusqu'à 8 h : aucun des deux
  n'est un instrument de mesure en temps réel. Le temps réel, c'est `terraform show` et
  la console EC2.
- **Les tarifs changent** : la table du README porte une date, comme celle des LLM.

## Questions d'entretien

<details><summary><b>1. Comment estimez-vous le coût d'un environnement avant de le créer ?</b></summary>

Par module, à partir de la grille tarifaire de la région : les ressources à l'heure
(plan de contrôle, instances, NAT, base), au stockage (volumes, registre, logs) et à
l'usage (trafic, appels). On sépare allumé/éteint, on note la date des tarifs, et on
vérifie ensuite sur Cost Explorer que la réalité suit. `terraform plan` ne donne pas de
prix ; des outils comme Infracost le font à partir du plan, et c'est une bonne suite.
</details>

<details><summary><b>2. Quels sont les postes dormants classiques d'un compte AWS ?</b></summary>

NAT Gateway, plan de contrôle EKS, instances RDS et EC2 arrêtées « pour plus tard »,
volumes EBS détachés, adresses IP élastiques non associées, équilibreurs sans cible,
snapshots. Tous facturés sans servir.
</details>

<details><summary><b>3. Tags de coût : à quoi servent-ils et quelle est leur limite ?</b></summary>

À ventiler la facture par projet, environnement, module, équipe. Leur limite : ils ne
couvrent que les ressources taguées (certains services partagés ne le sont pas) et
n'apparaissent dans Cost Explorer qu'une fois activés comme tags de répartition, avec
un délai.
</details>

<details><summary><b>4. Coût d'un appel LLM ou coût de l'infra : lequel domine ?</b></summary>

Ça dépend du volume, et c'est tout l'objet de la phase 6 : à faible volume, l'API
domine et l'infra est négligeable ; à fort volume, l'infra self-hosted (GPU) devient
moins chère par million de tokens. Le seuil de bascule se calcule avec les chiffres des
deux tables — celle des tarifs API et celle de l'infra.
</details>

## Ce qu'on n'a pas fait, et pourquoi

- **Pas d'Infracost dans la CI** : le plan n'est pas produit en CI (elle reste hors ligne) ;
  à ajouter le jour où un pipeline fait des plans.
- **Pas de Cost Anomaly Detection** : phase 5, avec la maîtrise des coûts et le kill switch.
- **Pas de Savings Plans ni d'instances réservées** : ils supposent un usage continu, à
  l'opposé d'un environnement éphémère.
- **Pas de Spot** : noté au guide 03 pour les charges tolérantes aux interruptions.
