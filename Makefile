.DEFAULT_GOAL := help
CLUSTER := llm-testbench

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Environnement Python + hooks pre-commit + kernel Jupyter du projet
	uv sync --all-groups
	uv run pre-commit install
	uv run python -m ipykernel install --user --name llm-testbench --display-name "Python (llm-testbench)"

lint: ## Ruff (check + format)
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck: ## mypy strict
	uv run mypy

test: ## Tests offline (les tests réseau sont exclus)
	uv run pytest

test-network: ## Tests qui téléchargent des données
	uv run pytest -m network --override-ini="addopts="

check: lint typecheck test ## Lint + typecheck + tests

notebooks: ## Exécute les notebooks de bout en bout (nbmake)
	uv run pytest --nbmake notebooks/*.ipynb --override-ini="addopts="

data-starter: ## Télécharge le sous-ensemble de démarrage (~150 Mo)
	uv run python -m llm_testbench.eval.loaders.starter

data-starter-large: ## Idem + HotpotQA (1,3 Go) et BIRD Mini-Dev (~500 Mo)
	uv run python -m llm_testbench.eval.loaders.starter --large

cluster-up: ## Crée le cluster k3d local + Postgres/pgvector
	k3d cluster create --config infra/k3d/config.yaml || true
	kubectl apply -k infra/k8s/local
	kubectl -n llm-testbench rollout status statefulset/postgres --timeout=120s

cluster-down: ## Détruit le cluster k3d local
	k3d cluster delete $(CLUSTER)

db-forward: ## Expose Postgres local sur localhost:5432
	kubectl -n llm-testbench port-forward svc/postgres 5432:5432

tilt-up: ## Boucle de dev avec hot-reload (phase 1+)
	tilt up

.PHONY: help install lint typecheck test test-network check notebooks \
	data-starter data-starter-large cluster-up cluster-down db-forward tilt-up
