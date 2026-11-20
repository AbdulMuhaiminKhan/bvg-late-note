# Presentation plan (solo)

Length still to be confirmed by the lecturer; this plan fits about 10 minutes.

| Part | Time | What to show |
|---|---|---|
| Idea and users | 1 min | "Has the U8 ever made you late?" The user is any Berlin commuter or student. Show a note on the phone. |
| Architecture | 2 min | `docs/architecture.png`: walk from the timer function to BVG, into PostgreSQL, out to the web app. Name the building block of each box and why it is there. |
| Live demo | 3 min | See the script below. |
| Cost | 1.5 min | `docs/cost.md`: €0 now, about €60–85 at 10,000 users, and why BVG calls do not grow with users. |
| Security | 1.5 min | `docs/security.md`: the access table, Key Vault + managed identities, the honest "not protected" list. |
| Lesson | 1 min | See below. |

## Demo script

1. Open the Container Apps URL on the projector. Point at "Last check 1 minute ago": the Function is running.
2. Hall of Shame: which line was worst this week, for real.
3. Pick a line that is late right now (check the board for S Sonnenallee first), find it, make a note.
4. Open the note link on my phone: same note, checkable by anyone.
5. Azure portal: Function "Monitor" tab with runs every 2 minutes; the resource group with every service.
6. If time: open the VM's IP to show the same image running on IaaS.

## Backup if the network fails

- A screen recording of the full demo (record it on Tue 24 Nov).
- The screenshots in `docs/screenshots/`.
- `docker compose up` on my laptop with a local database (demo data from `scripts/seed_demo_data.py`, clearly labelled as demo data).

## Lessons: things that failed and what I changed

- **Signing up for Azure for Students failed**: my university was not in Microsoft's list, so the form kept clearing the school name. I got the student offer through the GitHub Student Developer Pack instead.
- **The API reports more than one stop per station.** Asking for "Alexanderplatz" returns buses from a sub-stop with its own ID. My first idea of one row per trip and station would have mixed them up, so each departure is now stored by trip, exact stop and planned time.
- **The API limit shaped the design.** Calling BVG on every page view would break the 100 requests/minute limit at a few dozen users. Collecting on a timer and serving users from my own database solved it.
