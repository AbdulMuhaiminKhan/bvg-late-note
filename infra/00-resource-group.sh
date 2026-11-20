#!/usr/bin/env bash
# Step 0: one resource group for everything. Delete it and every cost is gone.
source "$(dirname "$0")/config.sh"

cat <<'MSG'
Before you create anything: set a budget alert.
  Portal > Cost Management > Budgets > Add: €10 per month, e-mail at 50%, 80%, 100%.
  If budgets are not offered on your subscription, check the credit at
  https://www.microsoftazuresponsorships.com/balance instead.
MSG
read -r -p "Budget alert set (or credit checked)? [y/N] " ok
[[ "$ok" == "y" ]] || { echo "Set it first."; exit 1; }

az group create --name "$RG" --location "$LOCATION" --tags project=bvg-late-note -o table
