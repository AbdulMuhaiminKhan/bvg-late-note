# The same system on Kubernetes (local)

The cloud deployment uses **Azure Container Apps** (see `infra/03-container-apps.sh`),
a managed service that runs on Kubernetes for us. These manifests run the same
image on a real Kubernetes cluster on my laptop, to compare the two. Everything
here is local and costs nothing.

| File | What it creates |
|---|---|
| `postgres.yaml` | PostgreSQL 16 as a StatefulSet with a 1 Gi PersistentVolumeClaim, and a ClusterIP Service `latenote-db` (local only; Azure uses the managed server) |
| `web.yaml` | the web app: Deployment with 2 replicas, readiness and liveness probes on `/healthz`, and a Service |
| `collector.yaml` | the collector as a CronJob every 2 minutes |

## Run it on OrbStack (macOS)

OrbStack has a built-in single-node Kubernetes cluster.

```bash
orb start k8s
kubectl config use-context orbstack

# Secrets, created by hand and never committed (the password is random):
P=$(head -c 300 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-24)
kubectl create secret generic latenote-pg --from-literal=POSTGRES_PASSWORD="$P"
kubectl create secret generic latenote-db \
  --from-literal=DATABASE_URL="postgresql://latenote:$P@latenote-db:5432/latenote"
unset P

kubectl apply -f k8s/
kubectl get pods -w                       # web pods become Ready, db-0 Running
kubectl get jobs                          # a collector Job every 2 minutes
```

Open the app: OrbStack gives every Service a local name, so
<http://latenote-web.default.svc.cluster.local> works in the browser on the Mac.
Otherwise: `kubectl port-forward svc/latenote-web 8080:80` and open <http://localhost:8080>.

Check that the collector writes data:

```bash
kubectl logs job/$(kubectl get jobs -o name | tail -1 | cut -d/ -f2) | grep "collector run"
curl -s http://latenote-web.default.svc.cluster.local/healthz     # "departures" > 0
```

Clean up: `kubectl delete -f k8s/ && kubectl delete secret latenote-pg latenote-db && kubectl delete pvc -l app=latenote`
(the PVC is named `data-latenote-db-0`: `kubectl delete pvc data-latenote-db-0`).

## Alternative: minikube

```bash
minikube start
# same two "kubectl create secret" commands as above
kubectl apply -f k8s/
minikube service latenote-web
```

## Kubernetes vs. Azure Container Apps

| | Kubernetes (here: OrbStack / AKS) | Azure Container Apps |
|---|---|---|
| Who runs the cluster | me: nodes, upgrades, add-ons | Azure (it is Kubernetes underneath, hidden) |
| Cost when idle | the nodes run all month (AKS: at least one VM) | scales to zero; inside the free grant at our size |
| Scaling | Deployment replicas, HPA if installed | built-in rules, 0 to 3 replicas |
| HTTPS | needs an ingress controller + cert-manager | built-in ingress with a managed certificate |
| Scheduled work | CronJob | Container Apps job with a cron trigger |
| Secrets | Kubernetes Secrets (base64, not encrypted by default) | Key Vault references + managed identity |
| Database | here a StatefulSet + PVC, I own backups | managed PostgreSQL, Azure does backups |
| Portability | the same YAML runs on any cluster | Azure-specific (`az containerapp`) |

Why Container Apps in the cloud: a cluster (AKS) needs at least one VM running
all month and someone to upgrade it, which is outside the free tier. Container
Apps gives the same container, scaling and scheduled jobs without that.
