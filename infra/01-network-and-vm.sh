#!/usr/bin/env bash
# Step 1 (building block: virtual machine, network, firewall).
# A virtual network with one subnet, a network security group (the firewall)
# and the smallest Ubuntu VM. Docker is installed on first boot by cloud-init.
source "$(dirname "$0")/config.sh"
IP="$(my_ip)"

az network vnet create -g "$RG" -n "$VNET" --address-prefix 10.10.0.0/16 \
  --subnet-name "$SUBNET" --subnet-prefix 10.10.1.0/24 -o none

az network nsg create -g "$RG" -n "$NSG" -o none
# Rule 1: SSH only from my own IP address, not from the whole internet.
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n allow-ssh-from-me --priority 100 \
  --direction Inbound --access Allow --protocol Tcp --destination-port-ranges 22 \
  --source-address-prefixes "$IP/32" -o none
# Rule 2: the web page (HTTP) from anywhere. Everything else stays blocked by
# the default "DenyAllInBound" rule.
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n allow-http --priority 110 \
  --direction Inbound --access Allow --protocol Tcp --destination-port-ranges 80 \
  --source-address-prefixes Internet -o none
az network vnet subnet update -g "$RG" --vnet-name "$VNET" -n "$SUBNET" --network-security-group "$NSG" -o none

az vm create -g "$RG" -n "$VM" --image Ubuntu2204 --size Standard_B1s \
  --admin-username azureuser --generate-ssh-keys \
  --vnet-name "$VNET" --subnet "$SUBNET" --nsg "" --public-ip-sku Standard \
  --custom-data "$(dirname "$0")/cloud-init.yml" -o table

echo "VM ready. SSH: ssh azureuser@$(az vm show -d -g "$RG" -n "$VM" --query publicIps -o tsv)"
echo "Tip: stop paying for it when you don't need it: az vm deallocate -g $RG -n $VM"
