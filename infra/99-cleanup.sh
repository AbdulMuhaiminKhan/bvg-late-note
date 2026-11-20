#!/usr/bin/env bash
# Delete everything. One command, because everything lives in one resource group.
source "$(dirname "$0")/config.sh"
read -r -p "Delete resource group $RG and everything in it? [y/N] " ok
[[ "$ok" == "y" ]] || exit 0
az group delete -n "$RG" --yes
# Key Vaults are kept for 90 days after deletion ("soft delete"); purge it so
# the name can be reused and nothing lingers.
az keyvault purge -n "$KV" -l "$LOCATION" || true
