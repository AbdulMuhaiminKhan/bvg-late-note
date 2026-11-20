# Cost per month

Goal: **€0**. Every resource is on a free offer of my Azure for Students
subscription (checked on the portal's "Free services" page, 20 Nov 2026).
Prices for the 10,000-user case are approximate list prices for Sweden Central,
rounded; check them in the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
before presenting.

## What runs, and which free offer covers it

| Resource | Size | How it is billed | Free offer that covers it |
|---|---|---|---|
| Container App (web) | 0.25 vCPU, 0.5 GiB, 0 to 3 replicas | per vCPU-second and GiB-second while running | Container Apps monthly grant: 180,000 vCPU-s, 360,000 GiB-s, 2 million requests. Scales to zero when nobody visits. |
| Container Apps job (collector) | 0.25 vCPU, 0.5 GiB, every 2 minutes, a few seconds per run | same | same grant: 21,600 runs × ~10 s × 0.25 vCPU ≈ 54,000 vCPU-s |
| Container Apps environment | Consumption, **no Log Analytics** (`--logs-destination none`) | free itself | n/a |
| PostgreSQL Flexible Server | Burstable B1ms, 32 GB storage, 7-day backups | per hour, all month | 750 hours of B1ms + 32 GB storage + 32 GB backup |
| Key Vault | Standard | per 10,000 operations | 10,000 transactions a month (we use a few hundred) |
| VM | Standard_B2ats_v2, Ubuntu, 64 GB Premium SSD (P6), runs Mosquitto + sensor + subscriber + web | per hour while running | 750 hours of B2ats_v2 Linux + 2 × P6 disks. A month has at most 744 hours, so the VM can run 24/7 for free. |
| MQTT broker | Eclipse Mosquitto in Docker on the VM | nothing extra | open source, runs on the free VM |
| VNet, subnet, NSG | | free | always free |
| Public IP | **none** | | The VM has no public IP on purpose: public IPs are not on a free offer. |
| BVG API | | free | 2 collectors (job + MQTT sensor) × 7 stops × 21,600 runs = 302,400 calls/month, **7 per minute** of the allowed 100 |

Not used, because they are outside the free tier: a storage account (needed by
an Azure Function, so the collector runs as a Container Apps job instead), Log
Analytics, Azure Container Registry (the image is on ghcr.io), a public IP or NAT gateway.

## At 100 users

| Service | Estimate |
|---|---|
| Container Apps web + collector job | €0 (inside the monthly grant) |
| PostgreSQL B1ms | €0 (750 free hours) |
| Key Vault | €0 |
| VM B2ats_v2 (private, with the MQTT stage) | €0 (750 free hours cover 24/7) |
| **Total** | **€0** |

## At 10,000 users

Assumption: each user opens 5 pages a day, so about 1.5 million requests a month.

| Service | What changes | Estimate |
|---|---|---|
| Collector job | **nothing**: it calls BVG on a schedule, not per user | €0 |
| Container Apps web | keep 1 replica always warm (no cold starts), up to 3 at peak; the warm replica uses more than the free grant | about €15–25 |
| PostgreSQL | move up to B2s for more memory and connections | about €45–55 |
| Key Vault | still a few hundred reads | €0 |
| VM + MQTT | unchanged: the sensor polls BVG on a schedule, not per user | €0 on the free hours |
| **Total** | | **about €60–80** |

The key point: 100× more users does **not** mean 100× more BVG calls or 100×
the bill. Only the collector talks to BVG, and the database answers the users.

## How I keep it under control

1. A €10/month budget on the subscription with alerts at 50, 80 and 100 % (created before anything else).
2. Everything in one resource group: `infra/99-cleanup.sh` deletes it all.
3. Container Apps scales to zero; the collector job runs only a few seconds every 2 minutes.
4. One VM only: 750 free hours cover it running all month. A second VM would not be free.
5. No public IP, no Log Analytics, no storage account: the paid extras are left out on purpose.
6. Old departures are deleted after 30 days (`RETENTION_DAYS`), so the database stays small.
