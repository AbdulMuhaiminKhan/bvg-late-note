# Security review

## Who can access what

| Who | Can reach | How it is enforced |
|---|---|---|
| Anyone on the internet | the web pages (read delays, make a note) | Container Apps ingress (HTTPS) and the VM's port 80 |
| Me (admin) | SSH to the VM, psql to the database | NSG rule: port 22 only from my IP; database firewall rule for my IP |
| The Function | the database and one Key Vault secret | its managed identity has only "Key Vault Secrets User" on this vault |
| The Container App | the database and one Key Vault secret | same, with its own identity |
| Everyone else | nothing else | NSG default deny; database only accepts Azure IPs and listed IPs, and needs the password over TLS |

## Where the secrets live

There is exactly one secret: the database connection string.

- It is **generated** by `infra/02-database-and-keyvault.sh`, stored in **Key Vault**
  and never printed, committed or baked into an image.
- The Function and the Container App read it at runtime with **managed identities**
  (no passwords in their settings, only a Key Vault reference).
- On the VM it lives in `/etc/latenote.env` (root-only, `chmod 600`), copied over SSH.
- Locally it is in `.env`, which is git-ignored. `.env.example` has only placeholders.
- CI publishes the image with GitHub's short-lived workflow token: no stored secrets.

## What is protected

- Database not reachable from the internet except from my own IP and from Azure IPs (see below), always with TLS (`sslmode=require`).
- SSH not open to the world.
- HTTPS for the main app (Container Apps).
- Container runs as a non-root user; secrets are not in the image.
- The web app sends security headers (no framing, no MIME sniffing, a strict content security policy).
- Notes are not guessable: random 8-character codes.
- The delay on a note comes from data the system collected itself, not from user input, so a user can't type in a fake delay.

## What is not protected (honest list)

- **The VM serves plain HTTP** on port 80. Fine for the IaaS comparison, not for real users.
- **No user accounts and no rate limiting**: anyone can create many notes.
- **The database has a public endpoint.** The "allow Azure services" rule lets any Azure IP try to connect, including other customers' services; only the password and TLS stop them. Private networking (VNet integration and a private endpoint) would be safer but costs more and complicates the student setup.
- **The BVG API is a free community service** with no guarantee: if it goes down, no new delays are recorded (old notes still work).
- A note proves *the train* was late, not that *the person* was on it.

## What I would do next

1. Private endpoint for PostgreSQL and VNet integration for the Function and Container Apps.
2. Rate limiting on note creation (for example, Azure Front Door or a simple per-IP limit).
3. HTTPS on the VM with Caddy and a free certificate, or retire the VM entirely.
4. Alerts in Azure Monitor when the collector fails several runs in a row.
