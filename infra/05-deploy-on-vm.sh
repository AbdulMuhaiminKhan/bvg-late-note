#!/usr/bin/env bash
# Step 5: the IaaS path and the MQTT stage, on the private VM.
#   mosquitto  - MQTT broker (login required, port 1883 open only inside the VNet)
#   sensor     - "virtual sensor": polls BVG, publishes to bvg/departures/<stop>
#   subscriber - reads bvg/departures/# and writes to PostgreSQL
#   latenote   - the same web app image as on Container Apps (port 80)
# The VM has no public IP and no SSH, so the admin path is `az vm run-command`.
# Secrets are NOT passed through run-command (its scripts are stored in Azure):
# the VM's managed identity reads the database URL and the MQTT password from
# Key Vault on the VM itself, into a root-only file.
source "$(dirname "$0")/config.sh"

PRINCIPAL="$(az vm show -g "$RG" -n "$VM" --query identity.principalId -o tsv)"
KV_ID="$(az keyvault show -n "$KV" --query id -o tsv)"
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KV_ID" -o none

# The MQTT password: generated once, straight into Key Vault, never printed.
if ! az keyvault secret show --vault-name "$KV" -n mqtt-password -o none 2>/dev/null; then
  az keyvault secret set --vault-name "$KV" -n mqtt-password -o none \
    --value "$(head -c 600 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-28)"
fi
echo "Waiting 60 s for the role assignment to take effect..."
sleep 60

# The database firewall already has the "allow Azure services" rule from step 2,
# which covers the VM's default outbound address.
read -r -d '' SCRIPT <<SH || true
set -e
cloud-init status --wait >/dev/null || true
kv() {
  TOKEN=\$(curl -fsS -H Metadata:true 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
  curl -fsS -H "Authorization: Bearer \$TOKEN" "https://$KV.vault.azure.net/secrets/\$1?api-version=7.4" | python3 -c 'import sys,json;print(json.load(sys.stdin)["value"])'
}
umask 077
DB_URL=\$(kv database-url); MQ_PW=\$(kv mqtt-password)
printf 'DATABASE_URL=%s\nMQTT_HOST=mosquitto\nMQTT_USERNAME=latenote\nMQTT_PASSWORD=%s\n' "\$DB_URL" "\$MQ_PW" > /etc/latenote.env
mkdir -p /etc/mosquitto-latenote && rm -f /etc/mosquitto-latenote/passwd   # -c will not overwrite
printf 'listener 1883\nallow_anonymous false\npassword_file /mosquitto/config/passwd\npersistence false\nlog_dest stdout\n' > /etc/mosquitto-latenote/mosquitto.conf
# Mosquitto 2.1 runs as user "mosquitto" (uid 1883) and only accepts a password
# file in a directory that this user owns. Directory 700, passwd (a hash) 600.
chown -R 1883:1883 /etc/mosquitto-latenote && chmod 700 /etc/mosquitto-latenote
docker run --rm -v /etc/mosquitto-latenote:/mosquitto/config eclipse-mosquitto:2 \
  sh -c "mosquitto_passwd -b -c /mosquitto/config/passwd latenote '\$MQ_PW' && chown mosquitto:mosquitto /mosquitto/config/passwd && chmod 600 /mosquitto/config/passwd" >/dev/null
unset DB_URL MQ_PW TOKEN

docker network create latenote-net >/dev/null 2>&1 || true
docker pull -q $IMAGE >/dev/null
for c in mosquitto sensor subscriber latenote; do docker rm -f \$c >/dev/null 2>&1 || true; done
docker run -d --name mosquitto --network latenote-net --restart unless-stopped \
  -v /etc/mosquitto-latenote:/mosquitto/config -p 1883:1883 eclipse-mosquitto:2 >/dev/null
docker run -d --name subscriber --network latenote-net --restart unless-stopped --no-healthcheck \
  --env-file /etc/latenote.env $IMAGE python -m latenote.subscriber >/dev/null
sleep 5
docker run -d --name sensor --network latenote-net --restart unless-stopped --no-healthcheck \
  --env-file /etc/latenote.env $IMAGE python -m latenote.sensor --loop --interval 120 >/dev/null
docker run -d --name latenote --network latenote-net --restart unless-stopped \
  --env-file /etc/latenote.env -p 80:8000 $IMAGE >/dev/null
sleep 20
docker ps --format '{{.Names}}: {{.Status}}'
docker logs sensor 2>&1 | grep 'sensor round' | tail -1
docker logs subscriber 2>&1 | grep -E 'connected|stored' | tail -2
curl -fsS localhost/healthz
SH

az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "$SCRIPT" \
  --query "value[0].message" -o tsv
echo "Running on the VM (private only, http://$(az vm show -d -g "$RG" -n "$VM" --query privateIps -o tsv) inside the VNet)."
echo "Watch the MQTT messages: see docs/demo.md (mosquitto_sub via run-command)."
