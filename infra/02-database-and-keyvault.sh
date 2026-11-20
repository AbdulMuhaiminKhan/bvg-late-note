#!/usr/bin/env bash
# Step 2 (building blocks: storage, managed service, secrets).
# Managed PostgreSQL (Azure keeps it patched and backed up) and a Key Vault
# that holds the only secret of the system: the database connection string.
# The password is generated here, goes straight into Key Vault and is never
# printed or written to a file.
source "$(dirname "$0")/config.sh"
IP="$(my_ip)"
PG_PASSWORD="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 28)Aa9"

# Burstable B1ms with 32 GB is the smallest size, and the one in Azure's
# free-services list (750 hours a month for 12 months on free accounts;
# check "Free services" in the portal for your subscription).
az postgres flexible-server create -g "$RG" -n "$PG" -l "$LOCATION" \
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 --version 16 \
  --admin-user "$PG_ADMIN" --admin-password "$PG_PASSWORD" \
  --public-access 0.0.0.0 --yes -o none
# --public-access 0.0.0.0 adds the "allow Azure services" rule, so the Function
# and Container App can connect. Note: it allows connections from ANY Azure IP,
# including other customers' services; the password is the real protection.
# A private endpoint would close this (see docs/security.md, "next").
# Add my IP so I can inspect the data with psql:
az postgres flexible-server firewall-rule create -g "$RG" -n "$PG" \
  --rule-name allow-admin-ip --start-ip-address "$IP" --end-ip-address "$IP" -o none
az postgres flexible-server db create -g "$RG" -s "$PG" -d "$PG_DB" -o none

az keyvault create -g "$RG" -n "$KV" -l "$LOCATION" --enable-rbac-authorization true -o none
KV_ID="$(az keyvault show -n "$KV" --query id -o tsv)"
ME="$(az ad signed-in-user show --query id -o tsv)"
az role assignment create --assignee "$ME" --role "Key Vault Secrets Officer" --scope "$KV_ID" -o none
echo "Waiting 60 s for the role assignment to take effect..."
sleep 60

DATABASE_URL="postgresql://$PG_ADMIN:$PG_PASSWORD@$PG.postgres.database.azure.com:5432/$PG_DB?sslmode=require"
az keyvault secret set --vault-name "$KV" -n database-url --value "$DATABASE_URL" -o none
unset PG_PASSWORD DATABASE_URL
echo "Database $PG is ready. Its connection string is in Key Vault $KV as 'database-url'."
