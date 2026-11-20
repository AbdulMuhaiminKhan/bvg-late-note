#!/usr/bin/env bash
# Pause everything that runs, keep all data and settings. Resume with infra/resume.sh.
# - VM: deallocated (no compute hours; the disk keeps the setup).
# - PostgreSQL: stopped. Note: Azure starts a stopped server again by itself after 7 days.
# - Collector job: schedule moved to once a year (a job cannot be switched off).
# - Web app: its active revisions are deactivated, so the URL answers with an error until resume.
source "$(dirname "$0")/config.sh"

az containerapp job update -g "$RG" -n "$JOB" --cron-expression "0 0 1 1 *" -o none
az vm deallocate -g "$RG" -n "$VM" -o none
az postgres flexible-server stop -g "$RG" -n "$PG" -o none
for rev in $(az containerapp revision list -g "$RG" -n "$CA" --query "[?properties.active].name" -o tsv); do
  az containerapp revision deactivate -g "$RG" -n "$CA" --revision "$rev" -o none
done
echo "Paused. Resume with: bash infra/resume.sh"
