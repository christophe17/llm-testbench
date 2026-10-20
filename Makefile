# LLM testbench — development targets.
# All Python commands go through uv; nothing is installed outside .venv.

.DEFAULT_GOAL := help
SHELL := /bin/bash

K3D_CLUSTER := llm-testbench
# One subfolder per phase (notebooks/phase-N/NN_slug.ipynb); nbmake walks the folder.
# A single one: make notebooks-ci NOTEBOOKS=notebooks/phase-1/01_robust_llm_call.ipynb
NOTEBOOKS ?= notebooks
DATABASE_URL ?= postgresql://testbench:testbench-local-only@localhost:5432/testbench

help: ## Lists the available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## Installs the environment (deps + pre-commit hooks + Jupyter kernel)
	uv sync
	uv run pre-commit install
	uv run python -m ipykernel install --user --name llm-testbench \
		--display-name "Python (llm-testbench)"

lint: ## Ruff: lint + format check (code and notebooks, like the pre-commit hook)
	uv run ruff check src tests notebooks
	uv run ruff format --check src tests notebooks

format: ## Ruff: fixes lint + format
	uv run ruff check --fix src tests notebooks
	uv run ruff format src tests notebooks

typecheck: ## Mypy strict
	uv run mypy

test: ## Offline tests (network tests are excluded)
	uv run python -m pytest -m "not network"

test-network: ## Network tests only (downloads the real datasets)
	uv run python -m pytest -m network

test-db: ## Postgres/pgvector tests (k3d cluster + port-forward required)
	LLM_TESTBENCH_DATABASE_URL=$(DATABASE_URL) uv run python -m pytest -m db

notebooks-ci: ## Runs the notebooks in offline sample mode (like the CI)
	LLM_TESTBENCH_SAMPLE=1 uv run python -m pytest --nbmake $(NOTEBOOKS)

notebooks-full: ## Runs the notebooks in full mode (downloads the real datasets)
	uv run python -m pytest --nbmake $(NOTEBOOKS)

check: lint typecheck test ## Everything the CI checks, except the notebooks

# ---------------------------------------------------------------- application

api: ## Runs the API locally (hot reload) — .env required
	uv run uvicorn llm_testbench.app.main:app --reload --port 8000

ingest-scifact: ## Indexes SciFact (BEIR) into pgvector — OPENAI_API_KEY and database required
	uv run python -m llm_testbench.ingest.cli scifact

ingest-qasper: ## Indexes QASPER (validation) into pgvector
	uv run python -m llm_testbench.ingest.cli qasper

bench-embeddings: ## Compares 3 embedding models on SciFact via mteb (bench group, OpenAI key) → data/results/
	uv run --group bench python -m llm_testbench.eval.embeddings_bench --device mps

# ---------------------------------------------------------------- local cluster

k3d-up: ## Creates the k3d cluster and deploys Postgres/pgvector
	k3d cluster create --config infra/k3d/config.yaml || true
	kubectl apply -k infra/k8s/local

k3d-down: ## Destroys the k3d cluster
	k3d cluster delete $(K3D_CLUSTER)

tilt-up: ## Dev loop with hot reload (requires the k3d cluster)
	tilt up

k8s-secrets: ## Creates/refreshes the API keys Secret in the cluster from .env
	@test -f .env || (echo ".env missing: copy .env.example" && exit 1)
	kubectl -n llm-testbench create secret generic llm-testbench-api-secrets \
		--from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -

docker-build: ## Builds the API image (arm64 locally)
	docker build -t llm-testbench-api:dev .

helm-lint: ## Validates the Helm chart with the local and dev values
	helm lint infra/helm/llm-testbench-api -f infra/helm/llm-testbench-api/values-local.yaml
	helm lint infra/helm/llm-testbench-api -f infra/helm/llm-testbench-api/values-dev.yaml
	helm template api infra/helm/llm-testbench-api -f infra/helm/llm-testbench-api/values-local.yaml > /dev/null

pg-port-forward: ## Exposes the cluster's Postgres on localhost:5432
	kubectl -n llm-testbench port-forward svc/postgres 5432:5432

# ---------------------------------------------------------------- local observability

langfuse-up: ## Deploys Langfuse (Helm) + single-node ClickHouse on the k3d (namespace observability)
	helm repo add langfuse https://langfuse.github.io/langfuse-k8s >/dev/null 2>&1 || true
	helm repo update langfuse >/dev/null
	kubectl apply -k infra/k8s/local/observability
	kubectl -n observability rollout status statefulset/clickhouse --timeout=300s
	helm upgrade --install langfuse langfuse/langfuse -n observability \
		-f infra/helm/langfuse/values-local.yaml --wait --timeout 20m

langfuse-down: ## Removes Langfuse and ClickHouse from the k3d
	helm uninstall langfuse -n observability || true
	kubectl delete -k infra/k8s/local/observability --ignore-not-found

langfuse-port-forward: ## Exposes the Langfuse UI on localhost:3000
	kubectl -n observability port-forward svc/langfuse-web 3000:3000

# ---------------------------------------------------------------- cloud infra

TF_DEV := infra/terraform/envs/dev
TFSTATE_BUCKET = llm-testbench-tfstate-$(shell aws sts get-caller-identity --query Account --output text)

infra-init: ## Terraform envs/dev — init with the bootstrap S3 backend
	cd $(TF_DEV) && terraform init -backend-config="bucket=$(TFSTATE_BUCKET)"

infra-plan: ## Terraform envs/dev — plan
	cd $(TF_DEV) && terraform plan

infra-up: ## Creates the dev environment (EKS, RDS, ECR, secrets) — ~20 min, ~$6/day while up
	cd $(TF_DEV) && terraform apply
	$(MAKE) kubeconfig

infra-down: ## Destroys the ENTIRE dev environment (database included, no snapshot)
	cd $(TF_DEV) && terraform destroy

infra-validate: ## Validates the Terraform configuration without backend or account
	cd $(TF_DEV) && terraform init -backend=false -input=false > /dev/null && terraform validate && terraform fmt -check -recursive

kubeconfig: ## Configures kubectl for the dev EKS cluster
	cd $(TF_DEV) && $$(terraform output -raw kubeconfig_command)

deploy: ## Builds and pushes the image to ECR (git SHA) then deploys the chart to the current cluster (same as the deploy.yml workflow, guide 09)
	$(eval ECR := $(shell cd $(TF_DEV) && terraform output -raw ecr_repository_url))
	$(eval TAG := $(shell git rev-parse --short HEAD))
	$(eval RDS_HOST := $(shell cd $(TF_DEV) && terraform output -raw rds_address))
	$(eval RDS_SECRET := $(shell cd $(TF_DEV) && terraform output -raw rds_master_secret_arn))
	aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin $(ECR)
	docker build -t $(ECR):$(TAG) .
	docker push $(ECR):$(TAG)
	kubectl create namespace llm-testbench --dry-run=client -o yaml | kubectl apply -f -
	helm upgrade --install api infra/helm/llm-testbench-api -n llm-testbench \
		-f infra/helm/llm-testbench-api/values-dev.yaml \
		--set image.repository=$(ECR) --set image.tag=$(TAG) \
		--set database.host=$(RDS_HOST) --set database.masterSecretArn=$(RDS_SECRET)

deploy-trigger: ## Triggers the GitHub Actions deployment workflow on main (OIDC role, guide 09)
	gh workflow run deploy.yml --ref main
	gh run list --workflow=deploy.yml --limit 1

cluster-addons: ## Installs External Secrets (Helm) and the ClusterSecretStore on the current cluster
	helm repo add external-secrets https://charts.external-secrets.io >/dev/null 2>&1 || true
	helm upgrade --install external-secrets external-secrets/external-secrets \
		-n external-secrets --create-namespace --wait
	kubectl apply -f infra/k8s/dev/cluster-secret-store.yaml

bootstrap-plan: ## Terraform bootstrap (remote state + budget alert) — plan
	cd infra/terraform/bootstrap && terraform init && terraform plan

bootstrap-apply: ## Terraform bootstrap — apply (run only once, AWS account required)
	cd infra/terraform/bootstrap && terraform init && terraform apply

.PHONY: help setup lint format typecheck test test-network notebooks-ci notebooks-full \
	test-db check api ingest-scifact ingest-qasper bench-embeddings k3d-up k3d-down tilt-up k8s-secrets docker-build helm-lint langfuse-up langfuse-down langfuse-port-forward pg-port-forward infra-init infra-plan infra-up infra-down infra-validate kubeconfig deploy deploy-trigger cluster-addons bootstrap-plan bootstrap-apply
