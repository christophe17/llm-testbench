# Image de l'API — deux étapes : résolution des dépendances avec uv, puis exécution sur
# une image Python minimale, sans uv ni outils de build, en utilisateur non root.
# Multi-arch : les images de base existent en arm64 (dev local) et amd64 (cloud).

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# Les dépendances d'abord (couche cacheable), le code ensuite.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY config ./config
COPY prompts ./prompts
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN useradd --system --uid 10001 --create-home app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER app
EXPOSE 8000
CMD ["uvicorn", "llm_testbench.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
