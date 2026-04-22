# Kubernetes deployment

Production-oriented Kubernetes manifests for `ugc-polls` with horizontal scaling and high availability primitives.

## Structure

- `base/`: core app deployment (web, service, ingress, migration job, HPA, PDB, config).
- `optional-stateful/`: in-cluster PostgreSQL and Redis (StatefulSets + PVCs).
- `overlays/full-stack/`: combines `base` + `optional-stateful`.

## 1) Prepare image

Update image in `base/deployment-web.yaml` and `base/job-migrate.yaml`:

- `ghcr.io/your-org/ugc-polls:latest`

## 2) Create secret

Template: `base/secret.example.yaml`.

Recommended:

```bash
kubectl create namespace ugc-polls
kubectl -n ugc-polls create secret generic ugc-polls-secret \
  --from-literal=SECRET_KEY='replace-me' \
  --from-literal=DB_PASSWORD='replace-me'
```

## 3) Deploy

### Option A: managed Postgres/Redis

Make sure `DB_HOST` and `REDIS_URL` in `base/configmap.yaml` point to managed services.

```bash
kubectl apply -k k8s/base
kubectl apply -f k8s/base/job-migrate.yaml
```

### Option B: in-cluster Postgres/Redis

```bash
kubectl apply -k k8s/overlays/full-stack
kubectl apply -f k8s/base/job-migrate.yaml
```

## 4) Post-deploy checks

```bash
kubectl -n ugc-polls get pods
kubectl -n ugc-polls get hpa
kubectl -n ugc-polls get ingress
```

## Notes

- Readiness endpoint: `/health/ready/` (checks PostgreSQL + Redis).
- Liveness endpoint: `/health/live/`.
- `HPA` requires metrics-server.
- `PDB` keeps at least one web pod available during voluntary disruptions.
- For production, replace placeholder host `api.example.com`, TLS secret, and resource sizes.
