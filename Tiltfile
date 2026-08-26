# Boucle de dev locale. Phase 0 : seulement Postgres/pgvector.
# Phase 1 ajoutera docker_build() + le déploiement de l'API avec hot-reload.

allow_k8s_contexts('k3d-llm-testbench')

k8s_yaml(kustomize('infra/k8s/local'))
k8s_resource('postgres', port_forwards='5432:5432', labels=['data'])
