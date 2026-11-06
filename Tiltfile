# Local dev loop on k3d: Postgres/pgvector (phase 0) + the API (phase 1).
#
# `tilt up` builds the API image, pushes it to the cluster's local registry, deploys it
# with the Helm chart (local values) and resyncs src/, prompts/ and config/ on every save
# without rebuilding the image. The sync only copies files: the restart comes from
# `uvicorn --reload`, set by the local values (values-local.yaml, `args`).

k8s_yaml(kustomize('infra/k8s/local'))
# The namespace and the database Secret belong to postgres rather than to "uncategorized":
# `tilt up postgres pgvector-init` (make tilt-db) then deploys everything Postgres needs.
k8s_resource(
    'postgres',
    objects=['llm-testbench:namespace', 'postgres-credentials:secret'],
    port_forwards='5432:5432',
    labels=['data'],
)
k8s_resource('pgvector-init', resource_deps=['postgres'], labels=['data'])

# Dev secrets from .env (API keys) — never in the chart, never in git.
# After postgres, which creates the namespace.
local_resource(
    'api-secrets',
    cmd='make k8s-secrets',
    deps=['.env'],
    resource_deps=['postgres'],
    labels=['api'],
)

docker_build(
    'llm-testbench-registry:5050/llm-testbench-api',
    context='.',
    dockerfile='Dockerfile',
    live_update=[
        sync('./src', '/app/src'),
        sync('./prompts', '/app/prompts'),
        sync('./config', '/app/config'),
    ],
)

k8s_yaml(helm(
    'infra/helm/llm-testbench-api',
    name='api',
    namespace='llm-testbench',
    values=['infra/helm/llm-testbench-api/values-local.yaml'],
))
k8s_resource(
    'api',
    objects=['api:serviceaccount', 'api-config:configmap'],
    port_forwards='8000:8000',
    resource_deps=['postgres', 'api-secrets'],
    labels=['api'],
)
