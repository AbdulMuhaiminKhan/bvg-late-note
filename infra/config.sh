#!/usr/bin/env bash
# Shared settings for every infra script. `source infra/config.sh` first.
# Names need a unique suffix (storage accounts, Key Vaults and database
# servers are global). It is created once and kept in infra/.names.env
# (git-ignored). Nothing secret is stored here.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$HERE/.names.env" ]]; then
  echo "SUFFIX=$(head -c 300 /dev/urandom | LC_ALL=C tr -dc 'a-z0-9' | cut -c1-5)" > "$HERE/.names.env"
fi
# shellcheck disable=SC1091
source "$HERE/.names.env"

# Some subscriptions only allow some regions (here: swedencentral, germanywestcentral,
# italynorth, austriaeast, denmarkeast). Sweden Central is the one that offers the
# free-tier VM size (B2ats_v2) to this subscription, so everything runs there.
LOCATION="${LOCATION:-swedencentral}"
RG="${RG:-rg-latenote}"

VNET="vnet-latenote"
SUBNET="snet-app"
NSG="nsg-latenote"
VM="vm-latenote"
VM_SIZE="Standard_B2ats_v2"   # the size covered by the free 750 VM hours a month
PG="pg-latenote-$SUFFIX"
PG_ADMIN="latenoteadmin"
PG_DB="latenote"
KV="kv-latenote-$SUFFIX"
CAE="cae-latenote"
CA="ca-latenote"
JOB="job-collector"
IMAGE="${IMAGE:-ghcr.io/abdulmuhaiminkhan/bvg-late-note:latest}"

my_ip() { curl -fsS https://api.ipify.org; }
