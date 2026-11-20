#!/usr/bin/env bash
# Undo infra/pause.sh: start the database and the VM, put the collector back on its schedule.
source "$(dirname "$0")/config.sh"

az postgres flexible-server start -g "$RG" -n "$PG" -o none || true   # may already be running (7-day auto-start)
az vm start -g "$RG" -n "$VM" -o none          # its containers restart by themselves (--restart unless-stopped)
az containerapp job update -g "$RG" -n "$JOB" --cron-expression "*/10 * * * *" -o none
LATEST="$(az containerapp show -g "$RG" -n "$CA" --query properties.latestRevisionName -o tsv)"
az containerapp revision activate -g "$RG" -n "$CA" --revision "$LATEST" -o none
az containerapp ingress traffic set -g "$RG" -n "$CA" --revision-weight latest=100 -o none
FQDN="$(az containerapp show -g "$RG" -n "$CA" --query properties.configuration.ingress.fqdn -o tsv)"
echo "Resumed. Check: curl https://$FQDN/healthz"
