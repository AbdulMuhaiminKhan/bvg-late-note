# Cost per month

Prices are approximate list prices for a European region, rounded, from the
Azure pricing pages. Before presenting, check the current numbers in the
[Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
for the region I actually deployed to.

## What drives the cost

| Part | How it is billed | Our usage |
|---|---|---|
| Azure Function (Flex Consumption, 512 MB) | per execution and GB-seconds; monthly free grant | 30 runs/hour × 24 × 30 = **21,600 runs**, about 2 s each |
| Container Apps (0.25 vCPU, 0.5 GiB) | per vCPU-second and GiB-second while running; monthly free grant of 180,000 vCPU-s, 360,000 GiB-s and 2 million requests | scales to zero when nobody visits |
| PostgreSQL Flexible Server B1ms + 32 GB | per hour, whether busy or not | runs all month: the **largest fixed cost** |
| VM Standard_B1s | per hour while running | only needed for the IaaS comparison: deallocate it after the demo |
| Key Vault, storage account, logs | per operation / GB | cents |
| BVG API | free | 7 stops × 21,600 runs = 151,200 calls/month, **3.5 per minute** of the allowed 100 |

## At 100 users

| Service | Estimate |
|---|---|
| Function | €0 (inside the free grant) |
| Container Apps | €0 (inside the free grant) |
| PostgreSQL B1ms | €0 on the 12-month free offer, otherwise about €15–18 |
| VM B1s | €0 on the free offer, otherwise about €8 if left running; €0 when deallocated (the disk costs about €1) |
| Key Vault, storage, logs | under €1 |
| **Total** | **about €0 on student/free offers, about €17–27 without them** |

## At 10,000 users

Assumption: each user opens 5 pages a day, so about 1.5 million requests a month.

| Service | What changes | Estimate |
|---|---|---|
| Function | **nothing**: it calls BVG on a timer, not per user | €0 |
| Container Apps | keep 1 replica always warm (no cold starts), up to 3 at peak | about €15–25 |
| PostgreSQL | move to B2s for more memory and connections | about €45–55 |
| VM | not needed: Container Apps serves the users | €0 |
| Logs | more requests, more log data | €2–5 |
| **Total** | | **about €60–85** |

The key point: 100× more users does **not** mean 100× more BVG calls or 100×
the bill. Only the collector talks to BVG, and the database answers the users.

## How I keep it under control

1. Budget alert before creating anything (or the credit balance page on Azure for Students).
2. Everything in one resource group: `infra/99-cleanup.sh` deletes it all.
3. Scale to zero on Container Apps; the Function only runs every 2 minutes.
4. `az vm deallocate` when the VM is not being shown.
5. Old departures are deleted after 30 days (`RETENTION_DAYS`), so the database stays small.
6. Smallest sizes everywhere: B1s, B1ms, 0.25 vCPU, 512 MB function instances.
