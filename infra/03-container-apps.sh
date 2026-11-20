#!/usr/bin/env bash
# Step 3 (building block: orchestration).
# The web app on Azure Container Apps: a managed container service (built on
# Kubernetes) that gives HTTPS, scaling from 0 to 3 replicas and rolling
# updates, without a cluster to pay for or patch.
source "$(dirname "$0")/config.sh"

az extension add --name containerapp --upgrade -o none
az provider register --namespace Microsoft.App --wait

# --logs-destination none: no Log Analytics workspace, which would not be free.
# Logs are still visible live with `az containerapp logs show`.
# --environment-mode WorkloadProfiles: the newer default ("Express") does not
# support Key Vault references. Only the built-in Consumption profile is used,
# which is what the monthly free grant covers.
az containerapp env create -g "$RG" -n "$CAE" -l "$LOCATION" --logs-destination none \
  --environment-mode WorkloadProfiles -o none

az containerapp create -g "$RG" -n "$CA" --environment "$CAE" \
  --image "$IMAGE" --target-port 8000 --ingress external \
  --cpu 0.25 --memory 0.5Gi --min-replicas 0 --max-replicas 3 \
  --system-assigned -o none

# Let the app's identity read the secret, then point the app at it.
PRINCIPAL="$(az containerapp show -g "$RG" -n "$CA" --query identity.principalId -o tsv)"
KV_ID="$(az keyvault show -n "$KV" --query id -o tsv)"
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KV_ID" -o none
echo "Waiting 60 s for the role assignment to take effect..."
sleep 60

SECRET_URI="https://$KV.vault.azure.net/secrets/database-url"
FQDN="$(az containerapp show -g "$RG" -n "$CA" --query properties.configuration.ingress.fqdn -o tsv)"
az containerapp secret set -g "$RG" -n "$CA" -o none \
  --secrets "database-url=keyvaultref:$SECRET_URI,identityref:system"
az containerapp update -g "$RG" -n "$CA" -o none \
  --set-env-vars "DATABASE_URL=secretref:database-url" "PUBLIC_URL=https://$FQDN"

echo "Live at https://$FQDN"
