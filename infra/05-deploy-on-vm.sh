#!/usr/bin/env bash
# Step 5: run the same container image on the VM (the IaaS path), so both
# hosting models can be compared side by side. The database URL is fetched
# from Key Vault by you and sent over SSH into a root-only file on the VM:
# it never appears in the image, the repo, or the VM's custom data.
source "$(dirname "$0")/config.sh"
VM_IP="$(az vm show -d -g "$RG" -n "$VM" --query publicIps -o tsv)"

# Allow the VM to reach the database.
az postgres flexible-server firewall-rule create -g "$RG" -n "$PG" \
  --rule-name allow-vm --start-ip-address "$VM_IP" --end-ip-address "$VM_IP" -o none

DATABASE_URL="$(az keyvault secret show --vault-name "$KV" -n database-url --query value -o tsv)"
printf 'DATABASE_URL=%s\nPUBLIC_URL=http://%s\n' "$DATABASE_URL" "$VM_IP" | \
  ssh "azureuser@$VM_IP" 'sudo tee /etc/latenote.env >/dev/null && sudo chmod 600 /etc/latenote.env'
unset DATABASE_URL

ssh "azureuser@$VM_IP" "sudo docker pull $IMAGE && (sudo docker rm -f latenote 2>/dev/null || true) && \
  sudo docker run -d --name latenote --restart unless-stopped --env-file /etc/latenote.env -p 80:8000 $IMAGE"
echo "Running on the VM: http://$VM_IP"
