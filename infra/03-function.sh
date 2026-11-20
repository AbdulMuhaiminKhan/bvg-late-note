#!/usr/bin/env bash
# Step 3 (building block: managed, event-driven service).
# The collector as an Azure Function on the Flex Consumption plan: it runs
# every 2 minutes and is billed per run. It reads the database URL from
# Key Vault with its own managed identity, so no password sits in its settings.
# Needs Azure Functions Core Tools (`func`) installed locally.
source "$(dirname "$0")/config.sh"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

az storage account create -g "$RG" -n "$ST" -l "$LOCATION" --sku Standard_LRS \
  --allow-blob-public-access false --min-tls-version TLS1_2 -o none

# If Flex Consumption is not offered in your region, replace the
# --flexconsumption-location line with:
#   --consumption-plan-location "$LOCATION" --os-type Linux --functions-version 4 \
az functionapp create -g "$RG" -n "$FUNC" --storage-account "$ST" \
  --flexconsumption-location "$LOCATION" \
  --runtime python --runtime-version 3.11 --instance-memory 512 -o none

PRINCIPAL="$(az functionapp identity assign -g "$RG" -n "$FUNC" --query principalId -o tsv)"
KV_ID="$(az keyvault show -n "$KV" --query id -o tsv)"
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KV_ID" -o none

az functionapp config appsettings set -g "$RG" -n "$FUNC" -o none --settings \
  "DATABASE_URL=@Microsoft.KeyVault(VaultName=$KV;SecretName=database-url)"

# Ship the shared code with the function, then publish (remote build on Azure).
rm -rf "$ROOT/function_app/latenote"
cp -r "$ROOT/latenote" "$ROOT/function_app/latenote"
(cd "$ROOT/function_app" && func azure functionapp publish "$FUNC" --python)
echo "Collector deployed. Logs: Portal > $FUNC > Monitor, or: func azure functionapp logstream $FUNC"
