#!/usr/bin/env bash
# Shared settings for every infra script. `source infra/config.sh` first.
# Names need a unique suffix (storage accounts, Key Vaults and database
# servers are global). It is created once and kept in infra/.names.env
# (git-ignored). Nothing secret is stored here.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$HERE/.names.env" ]]; then
  echo "SUFFIX=$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 5)" > "$HERE/.names.env"
fi
# shellcheck disable=SC1091
source "$HERE/.names.env"

# Azure for Students only allows some regions. If you get a "RequestDisallowedByPolicy"
# error, run: export LOCATION=swedencentral   (or westeurope) and try again.
LOCATION="${LOCATION:-germanywestcentral}"
RG="${RG:-rg-latenote}"

VNET="vnet-latenote"
SUBNET="snet-app"
NSG="nsg-latenote"
VM="vm-latenote"
PG="pg-latenote-$SUFFIX"
PG_ADMIN="latenoteadmin"
PG_DB="latenote"
KV="kv-latenote-$SUFFIX"
ST="stlatenote$SUFFIX"
FUNC="func-latenote-$SUFFIX"
CAE="cae-latenote"
CA="ca-latenote"
IMAGE="${IMAGE:-ghcr.io/abdulmuhaiminkhan/bvg-late-note:latest}"

my_ip() { curl -fsS https://api.ipify.org; }
