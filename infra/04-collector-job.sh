#!/usr/bin/env bash
# Step 4 (managed, event-driven service).
# The collector as a scheduled Azure Container Apps job: every 2 minutes Azure
# starts one container from the same image, it calls the BVG API for the 7
# watched stops, writes to PostgreSQL and exits. Billed per second of run time,
# which stays inside the Container Apps monthly free grant.
# (function_app/ holds the same collector as an Azure Function; it is not
# deployed because a Function needs a storage account outside the free tier.)
source "$(dirname "$0")/config.sh"

az containerapp job create -g "$RG" -n "$JOB" --environment "$CAE" \
  --trigger-type Schedule --cron-expression "*/2 * * * *" \
  --replica-timeout 120 --replica-retry-limit 0 --parallelism 1 --replica-completion-count 1 \
  --image "$IMAGE" --cpu 0.25 --memory 0.5Gi \
  --mi-system-assigned -o none
# Run the collector instead of the image's default command (the web server).
# Set through ARM as JSON, because the az parser mistakes "-m" for one of its own flags.
az resource update -g "$RG" -n "$JOB" --resource-type Microsoft.App/jobs -o none \
  --set 'properties.template.containers[0].command=["python","-m","latenote.collector"]'

# The job's own identity reads the database URL from Key Vault.
PRINCIPAL="$(az containerapp job show -g "$RG" -n "$JOB" --query identity.principalId -o tsv)"
KV_ID="$(az keyvault show -n "$KV" --query id -o tsv)"
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KV_ID" -o none
echo "Waiting 60 s for the role assignment to take effect..."
sleep 60

az containerapp job secret set -g "$RG" -n "$JOB" -o none \
  --secrets "database-url=keyvaultref:https://$KV.vault.azure.net/secrets/database-url,identityref:system"
az containerapp job update -g "$RG" -n "$JOB" -o none --set-env-vars "DATABASE_URL=secretref:database-url"

echo "Collector job scheduled every 2 minutes. Runs: az containerapp job execution list -g $RG -n $JOB -o table"
