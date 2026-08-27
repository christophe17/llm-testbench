# AWS — ce que je dois connaître

Périmètre calibré pour : projet banc d'essai AI Engineer (EKS, RDS, Bedrock, observabilité) + postes visés en startup / scale-up.

**Cadrage.** Avec 20 ans de systèmes et de Terraform, l'essentiel de l'apprentissage AWS est du **mapping de vocabulaire**, pas de la compréhension. Le risque n'est pas de ne pas comprendre : c'est de perdre trois semaines dans un cours généraliste de 24 heures.

**Séquencement recommandé.** Ne pas faire un bloc de formation avant de démarrer. Lancer la phase 0, laisser Claude Code générer le Terraform et les manifests, et suivre le cours **en parallèle**. Le mapping s'ancre dix fois plus vite quand on le voit dans du code qu'on est en train de relire.

---

## 1. Socle indispensable

Priorité : ⭐⭐⭐ critique · ⭐⭐ important · ⭐ à connaître

### IAM ⭐⭐⭐

- Utilisateurs, groupes, rôles, politiques (identity-based vs resource-based)
- `assume role`, politiques de confiance, STS et identifiants temporaires
- Moindre privilège, Access Analyzer, IAM Identity Center
- **IRSA / EKS Pod Identity** — le mécanisme qui donne des droits AWS à un pod

> C'est le pont entre mon monde (k8s) et AWS, et le point qui bloque tout le monde. Si je ne dois maîtriser qu'une chose, c'est celle-là.

### VPC et réseau ⭐⭐⭐

- Sous-réseaux publics et privés, tables de routage, passerelle Internet
- **NAT Gateway** — principal poste de coût dormant du projet
- **VPC endpoints** (gateway pour S3, interface pour les autres) — le moyen d'éviter la NAT
- Groupes de sécurité vs ACL réseau

### EKS ⭐⭐⭐

- Groupes de nœuds managés vs Fargate
- **Access entries** — attention : l'ancien mécanisme `aws-auth` est en voie de disparition, beaucoup de cours sont datés là-dessus
- AWS Load Balancer Controller, Ingress et target groups
- Pilotes CSI EBS et EFS
- **Karpenter** pour l'autoscaling — très cité en offre d'emploi

### ECR ⭐⭐

- Push / pull, authentification depuis la CI
- Politiques de cycle de vie, scan de vulnérabilités

### S3 ⭐⭐

- Classes de stockage, versioning, règles de cycle de vie
- URLs présignées, politiques de bucket, chiffrement

### RDS PostgreSQL ⭐⭐⭐

- Groupes de paramètres, sauvegardes, restauration à un instant donné
- **Extension pgvector** : disponibilité et activation
- Gestion des connexions, RDS Proxy
- Aurora Serverless v2 : pertinent pour l'environnement de dev (montée et descente à zéro)

### Secrets ⭐⭐

- Secrets Manager vs SSM Parameter Store : arbitrage coût / rotation / usage
- Consommation depuis le cluster via External Secrets

### Observabilité ⭐⭐⭐

- CloudWatch : logs, métriques, alarmes, Container Insights
- **ADOT** (AWS Distro for OpenTelemetry) — collecteur OTel managé, directement concerné par la phase 5
- Articulation avec la stack Prometheus / Grafana / Langfuse auto-hébergée

### Coûts ⭐⭐⭐

- Cost Explorer, budgets et alertes
- Tags de répartition des coûts
- Notion de Savings Plans, instances réservées, Spot
- Estimation du coût mensuel par module Terraform

> Directement lié à mon positionnement « je chiffre ce que je déploie ». Ne pas survoler.

### Terraform sur AWS ⭐⭐⭐

- Backend S3 avec verrouillage d'état
- Structure multi-environnements, modules réutilisables
- Providers AWS et Kubernetes/Helm dans un même plan : les pièges de dépendance

---

## 2. Couche IA

### Bedrock ⭐⭐⭐

- API Converse, streaming
- Disponibilité des modèles selon la région
- Quotas, débit à la demande vs provisionné
- Guardrails
- Tarification et suivi du coût
- **Usage dans le projet** : un provider parmi d'autres, derrière l'abstraction LLM

### À savoir situer, sans investir ⭐

Bedrock Knowledge Bases · Bedrock Agents · SageMaker · OpenSearch Serverless en mode vectoriel · Kendra

> On me posera la question en entretien. Je dois pouvoir dire ce que c'est **et quand je ne m'en servirais pas**.

### Asynchrone et orchestration ⭐⭐

- Lambda, SQS, EventBridge
- **Step Functions** — utile concrètement pour la démonstration « ici, un agent est la mauvaise réponse »

### GPU ⭐

Familles d'instances, quotas, Spot. Survol seulement : le GPU est découplé du cloud principal (module dédié vers un fournisseur spécialisé en phase 6).

---

## 3. À ignorer volontairement

CloudFront · Route 53 au-delà des bases · Elastic Beanstalk · DynamoDB en profondeur · Redshift · Glue · EMR · Kinesis · Organizations et Control Tower · et globalement la moitié du catalogue.

Un cours de certification me les fera tous avaler. C'est le principal gaspillage à éviter.

---

## 4. Cours

### Le généraliste — SAA-C03 (Stéphane Maarek, Udemy)

Le standard du marché, le plus complet et le mieux tenu à jour. **Mais les deux tiers ne me serviront pas.**

Mode d'emploi : le prendre en accéléré, sauter sans culpabilité, s'en servir comme d'une carte du territoire et non d'un programme.

Sur l'examen : à ne passer que si j'envisage un jour une ESN ou un grand groupe. En scale-up, il ne pèsera presque rien.

### Le spécialisé IA — AWS Certified Generative AI Developer Professional (Maarek / Frank Kane, Udemy)

Couvre Bedrock, SageMaker, les pipelines RAG avec embeddings et bases vectorielles, les workflows agentiques avec Bedrock Agents, et Bedrock Evaluations.

> ⚠️ **Piège de fond.** Ces services font précisément à ma place ce que je viens apprendre. Cliquer sur « Knowledge Base » n'apprend rien sur le chunking, le hybrid search ou le re-ranking.
>
> **Règle : après les phases 1 à 3, jamais avant, jamais à la place.**

### Pour la pratique — ateliers AWS (gratuits)

EKS Workshop et le guide de bonnes pratiques EKS. Souvent supérieurs à n'importe quelle vidéo, parce que maintenus par ceux qui font le produit. À privilégier pour tout ce qui touche EKS, IRSA et Karpenter.

### Si je veux de la profondeur

Adrian Cantrill (hors Udemy) : plus long, plus profond, mieux adapté à un profil expérimenté que les cours orientés QCM.

---

## 5. Points de vigilance

- **Les cours AWS datent vite.** Vérifier systématiquement contre la documentation officielle sur les sujets qui bougent : EKS access entries, Karpenter, Bedrock (modèles et régions), tarification.
- **Ne pas confondre le cours et le projet.** Le cours donne le vocabulaire ; les compétences viennent du Terraform et des manifests que je relis et critique.
- **Surveiller la facture dès le premier jour.** Budget + alerte configurés avant le premier `terraform apply`.
