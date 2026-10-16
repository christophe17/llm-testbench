# Boucle de dev locale sur k3d : Postgres/pgvector (phase 0) + l'API (phase 1).
#
# `tilt up` construit l'image de l'API, la pousse dans le registre local du cluster, la
# déploie avec le chart Helm (valeurs locales) et resynchronise src/ à chaque sauvegarde
# sans reconstruire l'image (uvicorn --reload fait le reste).

k8s_yaml(kustomize('infra/k8s/local'))
k8s_resource('postgres', port_forwards='5432:5432', labels=['data'])
k8s_resource('pgvector-init', resource_deps=['postgres'], labels=['data'])

# Secrets de dev depuis .env (clés API) — jamais dans le chart, jamais dans git.
local_resource(
    'api-secrets',
    cmd='make k8s-secrets',
    deps=['.env'],
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
    set=['image.tag=dev'],
))
k8s_resource('api', port_forwards='8000:8000', resource_deps=['postgres', 'api-secrets'], labels=['api'])
