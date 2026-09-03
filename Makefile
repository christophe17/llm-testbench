# Banc d'essai LLM — cibles de développement.
# Toutes les commandes Python passent par uv ; rien ne s'installe hors de .venv.

.DEFAULT_GOAL := help
SHELL := /bin/bash

K3D_CLUSTER := llm-testbench
NOTEBOOKS := notebooks/00_visite_guidee.ipynb
DATABASE_URL ?= postgresql://testbench:testbench-local-only@localhost:5432/testbench

help: ## Liste les cibles disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## Installe l'environnement (deps + hooks pre-commit + kernel Jupyter)
	uv sync
	uv run pre-commit install
	uv run python -m ipykernel install --user --name llm-testbench \
		--display-name "Python (llm-testbench)"

lint: ## Ruff : lint + format check
	uv run ruff check src tests
	uv run ruff format --check src tests

format: ## Ruff : corrige lint + format
	uv run ruff check --fix src tests
	uv run ruff format src tests

typecheck: ## Mypy strict
	uv run mypy

test: ## Tests hors ligne (les tests réseau sont exclus)
	uv run python -m pytest -m "not network"

test-network: ## Tests réseau uniquement (télécharge les datasets réels)
	uv run python -m pytest -m network

test-db: ## Tests Postgres/pgvector (cluster k3d + port-forward requis)
	LLM_TESTBENCH_DATABASE_URL=$(DATABASE_URL) uv run python -m pytest -m db

notebooks-ci: ## Exécute les notebooks en mode échantillon hors ligne (comme la CI)
	LLM_TESTBENCH_SAMPLE=1 uv run python -m pytest --nbmake $(NOTEBOOKS)

notebooks-full: ## Exécute les notebooks en mode complet (télécharge les vrais datasets)
	uv run python -m pytest --nbmake $(NOTEBOOKS)

check: lint typecheck test ## Tout ce que la CI vérifie, sauf les notebooks

# ---------------------------------------------------------------- application

api: ## Lance l'API en local (rechargement à chaud) — .env requis
	uv run uvicorn llm_testbench.app.main:app --reload --port 8000

ingest-scifact: ## Indexe SciFact (BEIR) dans pgvector — OPENAI_API_KEY et base requis
	uv run python -m llm_testbench.ingest.cli scifact

ingest-qasper: ## Indexe QASPER (validation) dans pgvector
	uv run python -m llm_testbench.ingest.cli qasper

# ---------------------------------------------------------------- cluster local

k3d-up: ## Crée le cluster k3d et déploie Postgres/pgvector
	k3d cluster create --config infra/k3d/config.yaml || true
	kubectl apply -k infra/k8s/local

k3d-down: ## Détruit le cluster k3d
	k3d cluster delete $(K3D_CLUSTER)

tilt-up: ## Boucle de dev avec hot-reload (nécessite le cluster k3d)
	tilt up

k8s-secrets: ## Crée/actualise le Secret des clés API dans le cluster depuis .env
	@test -f .env || (echo ".env absent : copier .env.example" && exit 1)
	kubectl -n llm-testbench create secret generic llm-testbench-api-secrets \
		--from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -

docker-build: ## Construit l'image de l'API (arm64 en local)
	docker build -t llm-testbench-api:dev .

helm-lint: ## Valide le chart Helm avec les valeurs locales et dev
	helm lint infra/helm/llm-testbench-api -f infra/helm/llm-testbench-api/values-local.yaml
	helm lint infra/helm/llm-testbench-api -f infra/helm/llm-testbench-api/values-dev.yaml
	helm template api infra/helm/llm-testbench-api -f infra/helm/llm-testbench-api/values-local.yaml > /dev/null

pg-port-forward: ## Expose Postgres du cluster sur localhost:5432
	kubectl -n llm-testbench port-forward svc/postgres 5432:5432

# ---------------------------------------------------------------- infra cloud

TF_DEV := infra/terraform/envs/dev
TFSTATE_BUCKET = llm-testbench-tfstate-$(shell aws sts get-caller-identity --query Account --output text)

infra-init: ## Terraform envs/dev — init avec le backend S3 du bootstrap
	cd $(TF_DEV) && terraform init -backend-config="bucket=$(TFSTATE_BUCKET)"

infra-plan: ## Terraform envs/dev — plan
	cd $(TF_DEV) && terraform plan

infra-up: ## Crée l'environnement dev (EKS, RDS, ECR, secrets) — ~20 min, ~6 $/jour allumé
	cd $(TF_DEV) && terraform apply
	$(MAKE) kubeconfig

infra-down: ## Détruit TOUT l'environnement dev (base incluse, sans snapshot)
	cd $(TF_DEV) && terraform destroy

infra-validate: ## Valide la configuration Terraform sans backend ni compte
	cd $(TF_DEV) && terraform init -backend=false -input=false > /dev/null && terraform validate && terraform fmt -check -recursive

kubeconfig: ## Configure kubectl sur le cluster EKS dev
	cd $(TF_DEV) && $$(terraform output -raw kubeconfig_command)

cluster-addons: ## Installe External Secrets (Helm) et le ClusterSecretStore sur le cluster courant
	helm repo add external-secrets https://charts.external-secrets.io >/dev/null 2>&1 || true
	helm upgrade --install external-secrets external-secrets/external-secrets \
		-n external-secrets --create-namespace --wait
	kubectl apply -f infra/k8s/dev/cluster-secret-store.yaml

bootstrap-plan: ## Terraform bootstrap (état distant + alerte budget) — plan
	cd infra/terraform/bootstrap && terraform init && terraform plan

bootstrap-apply: ## Terraform bootstrap — apply (à lancer une seule fois, compte AWS requis)
	cd infra/terraform/bootstrap && terraform init && terraform apply

.PHONY: help setup lint format typecheck test test-network notebooks-ci notebooks-full \
	test-db check api ingest-scifact ingest-qasper k3d-up k3d-down tilt-up k8s-secrets docker-build helm-lint pg-port-forward infra-init infra-plan infra-up infra-down infra-validate kubeconfig cluster-addons bootstrap-plan bootstrap-apply
