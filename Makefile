# Banc d'essai LLM — cibles de développement.
# Toutes les commandes Python passent par uv ; rien ne s'installe hors de .venv.

.DEFAULT_GOAL := help
SHELL := /bin/bash

K3D_CLUSTER := llm-testbench
NOTEBOOKS := notebooks/00_visite_guidee.ipynb

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

notebooks-ci: ## Exécute les notebooks en mode échantillon hors ligne (comme la CI)
	LLM_TESTBENCH_SAMPLE=1 uv run python -m pytest --nbmake $(NOTEBOOKS)

notebooks-full: ## Exécute les notebooks en mode complet (télécharge les vrais datasets)
	uv run python -m pytest --nbmake $(NOTEBOOKS)

check: lint typecheck test ## Tout ce que la CI vérifie, sauf les notebooks

# ---------------------------------------------------------------- cluster local

k3d-up: ## Crée le cluster k3d et déploie Postgres/pgvector
	k3d cluster create --config infra/k3d/config.yaml || true
	kubectl apply -k infra/k8s/local

k3d-down: ## Détruit le cluster k3d
	k3d cluster delete $(K3D_CLUSTER)

tilt-up: ## Boucle de dev avec hot-reload (nécessite le cluster k3d)
	tilt up

pg-port-forward: ## Expose Postgres du cluster sur localhost:5432
	kubectl -n llm-testbench port-forward svc/postgres 5432:5432

# ---------------------------------------------------------------- infra cloud

bootstrap-plan: ## Terraform bootstrap (état distant + alerte budget) — plan
	cd infra/terraform/bootstrap && terraform init && terraform plan

bootstrap-apply: ## Terraform bootstrap — apply (à lancer une seule fois, compte AWS requis)
	cd infra/terraform/bootstrap && terraform init && terraform apply

.PHONY: help setup lint format typecheck test test-network notebooks-ci notebooks-full \
	check k3d-up k3d-down tilt-up pg-port-forward bootstrap-plan bootstrap-apply
