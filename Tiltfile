# Boucle de dev locale. Phase 0 : uniquement Postgres/pgvector.
# L'API FastAPI et son hot-reload arrivent en phase 1.

k8s_yaml(kustomize('infra/k8s/local'))

k8s_resource(
    'postgres',
    port_forwards='5432:5432',
    labels=['data'],
)
k8s_resource(
    'pgvector-init',
    resource_deps=['postgres'],
    labels=['data'],
)
