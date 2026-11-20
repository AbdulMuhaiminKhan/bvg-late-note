# Presentation plan (solo)

Length still to be confirmed by the lecturer; this plan fits about 10 minutes.

| Part | Time | What to show |
|---|---|---|
| Idea and users | 1 min | "Has the U8 ever made you late?" The user is any Berlin commuter or student. Show a note on the phone. |
| Architecture | 2 min | `docs/architecture.png`: the IoT pipeline (virtual sensor → MQTT broker → subscriber → PostgreSQL → web dashboard), then the serverless collector job to BVG, into PostgreSQL, out to the web app. Name the building block of each box and why it is there. |
| Live demo | 3 min | See the script below. |
| Cost | 1.5 min | `docs/cost.md`: €0 now (every resource on a free offer), about €60–80 at 10,000 users, and why BVG calls do not grow with users. |
| Security | 1.5 min | `docs/security.md`: the access table, Key Vault + managed identities, the honest "not protected" list. |
| Lesson | 1 min | See below. |

## Demo script

1. Open the Container Apps URL on the projector. Point at "Last check 1 minute ago": the collector job is running.
2. Hall of Shame: which line was worst this week, for real.
3. Pick a line that is late right now (check the board for S Sonnenallee first), find it, make a note.
4. Open the note link on my phone: same note, checkable by anyone.
5. Azure portal: the collector job's "Execution history" with a run every 2 minutes; the resource group with every service.
6. MQTT stage on the VM (IoT pipeline): show live messages from the virtual sensor:
   ```bash
   az vm run-command invoke -g rg-latenote -n vm-latenote --command-id RunShellScript \
     --scripts 'set -a; . /etc/latenote.env; docker exec mosquitto mosquitto_sub -u latenote -P "$MQTT_PASSWORD" -t "bvg/departures/#" -v -C 3 -W 150' \
     --query "value[0].message" -o tsv
   ```
   Then `docker logs subscriber | tail` the same way, and `curl -s localhost/healthz`: the same image running on the private VM (IaaS).

## Backup if the network fails

- A screen recording of the full demo (record it on Tue 24 Nov).
- The screenshots in `docs/screenshots/`.
- `docker compose up` on my laptop with a local database (demo data from `scripts/seed_demo_data.py`, clearly labelled as demo data).

## Lessons: things that failed and what I changed

- **Signing up for Azure for Students failed**: my university was not in Microsoft's list, so the form kept clearing the school name. I got the student offer through the GitHub Student Developer Pack instead.
- **The API reports more than one stop per station.** Asking for "Alexanderplatz" returns buses from a sub-stop with its own ID. My first idea of one row per trip and station would have mixed them up, so each departure is now stored by trip, exact stop and planned time.
- **The API limit shaped the design.** Calling BVG on every page view would break the 100 requests/minute limit at a few dozen users. Collecting on a timer and serving users from my own database solved it.
- **Staying at €0 changed the design on deployment day.** The free VM size (B2ats_v2) was only offered to my subscription in Sweden Central, public IPs and the Function's storage account are not free, so the VM became private (run-command instead of SSH) and the collector became a scheduled Container Apps job.
