# Optional: the same system on a small Kubernetes cluster

The cloud deployment uses **Azure Container Apps** (see `infra/04-container-apps.sh`),
a managed service that runs on Kubernetes for us. These manifests show the same
setup on a local cluster (minikube or kind), to compare the two.

```bash
minikube start
kubectl create secret generic latenote-db --from-literal=DATABASE_URL='postgresql://...'   # never commit this
kubectl apply -f k8s/
kubectl get pods
minikube service latenote-web
```

Why Container Apps in the cloud instead: a cluster (AKS) needs at least one VM
running all month and someone to upgrade it. Container Apps scales to zero,
gives HTTPS out of the box and stays inside the free monthly grant at our size.
