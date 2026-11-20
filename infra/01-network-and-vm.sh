#!/usr/bin/env bash
# Step 1 (building block: virtual machine, network, firewall).
# A virtual network with one subnet, a network security group (the firewall)
# and a small Ubuntu VM. Docker is installed on first boot by cloud-init.
#
# The VM is private: it has NO public IP address (public IPs are not on a free
# offer) and no SSH port open. It is reachable only from inside the VNet, and
# I administer it with `az vm run-command` (see infra/05-deploy-on-vm.sh).
source "$(dirname "$0")/config.sh"

# --default-outbound-access true: new subnets are private by default; this keeps
# Azure's free implicit outbound connection, so the VM can pull the image and
# reach the database without a public IP or a NAT gateway.
az network vnet create -g "$RG" -n "$VNET" -l "$LOCATION" --address-prefix 10.10.0.0/16 -o none
az network nsg create -g "$RG" -n "$NSG" -l "$LOCATION" -o none
az network vnet subnet create -g "$RG" --vnet-name "$VNET" -n "$SUBNET" \
  --address-prefixes 10.10.1.0/24 --network-security-group "$NSG" \
  --default-outbound-access true -o none

# One inbound rule: the web app (80 on the VM, 8000 in the container) and the
# MQTT broker (1883) only from inside the virtual network. No SSH rule at all.
# Everything from the internet is dropped by the default "DenyAllInBound" rule.
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n allow-web-from-vnet --priority 100 \
  --direction Inbound --access Allow --protocol Tcp --destination-port-ranges 80 8000 1883 \
  --source-address-prefixes VirtualNetwork -o none

# Standard_B2ats_v2 with a 64 GB Premium SSD (P6) is what the free offer covers
# (750 hours a month, 2 x 64 GB P6 disks). --assign-identity gives the VM its
# own managed identity, used to read the database URL from Key Vault.
az vm create -g "$RG" -n "$VM" -l "$LOCATION" --image Ubuntu2204 --size "$VM_SIZE" \
  --os-disk-size-gb 64 --storage-sku Premium_LRS \
  --admin-username azureuser --generate-ssh-keys \
  --vnet-name "$VNET" --subnet "$SUBNET" --nsg "" --public-ip-address "" \
  --assign-identity --custom-data "$(dirname "$0")/cloud-init.yml" -o table

echo "VM ready (private IP $(az vm show -d -g "$RG" -n "$VM" --query privateIps -o tsv), no public IP)."
echo "Run commands on it with: az vm run-command invoke -g $RG -n $VM --command-id RunShellScript --scripts 'uptime'"
echo "Tip: stop paying for it when you don't need it: az vm deallocate -g $RG -n $VM"
