# Build log

All work by Abdul Muhaimin Khan. What was built, why, and what went wrong on the way.

## Early November: groundwork

- Practised the building blocks first: a first cloud VM, then containers with Docker.
- Getting a cloud account took longer than planned. The usual Azure sign-up form kept rejecting my details, so I got Azure access through the GitHub Developer Pack instead.
- Looked at several ideas (a study-room monitor, a fridge app, lost and found, an office-hours queue) before settling on this one.

## 18 November: the idea, and the limit that shaped it

- Picked **BVG Late Note**: original, built on real data every Berliner knows, with a natural event-driven part (a timer).
- Checked the BVG API before writing any code: free, no key, a delay in seconds for every departure. Its limit of about 100 requests per minute decided the architecture: collect on a schedule, serve users from my own database.

## 20 November: building the system

**Built**
- The `latenote` package: BVG client, database layer (PostgreSQL and SQLite), collector, and the web pages (find your train, late note, Hall of Shame, stop boards).
- The Dockerfile and a Compose setup with PostgreSQL on a named volume, tested end to end.
- The collector as an Azure Function with a timer trigger (kept in `function_app/`).
- Azure CLI scripts for the network and VM, PostgreSQL, Key Vault, Container Apps and the collector.
- Kubernetes manifests, and CI that runs the tests and publishes the image to ghcr.io.

**Decisions**
- One image for the web app and the collector, so local and cloud behave the same.
- Key Vault and managed identities instead of connection strings in app settings.
- Container Apps instead of AKS: it scales to zero and has no cluster cost.
- Watched stops around Sonnenallee in Neukölln, plus the big hubs.

**Problems found**
- Asking the API for one station also returns departures from its sub-stops, with their own IDs. Each departure is now stored by trip, exact stop and planned time.
- A later reading without real-time data overwrote a measured delay with nothing. The last known delay is now kept, with a test for it.
- A strict Content-Security-Policy blocked inline styles, so line badges and chart bars were invisible. Rewrote them with classes and SVG.

## 20 November, night: deployed to Azure at €0

- **Requirement:** everything on free offers. That changed the design:
  - The free VM size (B2ats_v2) was only offered to my subscription in **Sweden Central**, so everything runs there.
  - The VM got **no public IP** (public IPs are not free) and is managed with `az vm run-command`.
  - The collector became a **scheduled Container Apps job**, because a Function needs a storage account outside the free tier.
  - The Container Apps environment has no Log Analytics workspace.
- **Fixed on the way:** the PostgreSQL and Key Vault resource providers were not registered on the new subscription; newer `az` versions renamed the firewall-rule and database arguments; the new default Container Apps environment type ("Express") does not support Key Vault references; `tr </dev/urandom | head` died with SIGPIPE under `set -o pipefail`; Mosquitto 2.1 only accepts a password file owned by its own user.
- Added the **MQTT pipeline**: a virtual sensor publishes each departure to Mosquitto on the VM, and a subscriber stores it.
- CI now builds the image for amd64 and arm64, so it also runs on Apple-silicon laptops.
- Ran the `k8s/` manifests on a real local cluster (OrbStack): PostgreSQL as a StatefulSet with a volume, 2 web replicas behind a Service, and the collector as a CronJob ([screenshot](screenshots/k8s-orbstack-home.png)).
- Added the **"Tell them you're late"** message with Copy, Share, WhatsApp, email and SMS on every note.

## Next

- Watch a full week of real data and check the Hall of Shame against it.
- Rate-limit note creation, and move the database to a private endpoint if a paid tier is ever used (see [security.md](security.md)).
