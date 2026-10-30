# Yale Downtowner recorder

Records the live feeds behind https://yale.downtownerapp.com/routes every 5 minutes
using GitHub Actions (see `.github/workflows/record.yml`).

Data is in `data/<UTC date>/`:

| File | One row per |
|---|---|
| `buses.csv` | bus per poll: position, heading, route, last stop |
| `etas.csv` | predicted arrival per stop per poll (every stop on an active route) |
| `route_status.csv` | route per poll: whether it is running |
| `announcements.csv` | announcement in effect per poll |

`data/routes.json` and `data/stops.json` hold the latest route shapes and stop list.
All times are UTC.

## Alert

`.github/workflows/check.yml` runs every hour and fails if nothing has been saved
for 30 minutes, which makes GitHub email the account that set it up. To test it:
Actions tab → saving check → Run workflow, with minutes set to 0.

## Known gaps

475 polls between Oct 27 and Oct 30, 2026 are missing because of a bug in the
workflow (fixed Oct 30, 13:40 UTC). Their rows can't be recovered: the Downtowner
site only serves live data. A gap means the recorder didn't save, **not** that no
buses were running.

`data/gaps.csv` lists every missing poll. For 461 of them the job log kept a
one-line summary, so the file still has the number of active routes, buses,
announcements and ETAs at that time (these counts match the saved data exactly
wherever both exist). The other 14 had no run at all.

| UTC | Eastern | Polls | Cause |
|---|---|---|---|
| Oct 27 05:45–11:20 | Tue 1:45 AM–7:20 AM | 68 | run could not save |
| Oct 27 17:10–22:45 | Tue 1:10 PM–6:45 PM | 68 | run could not save |
| Oct 28 04:35–10:10 | Wed 12:35 AM–6:10 AM | 68 | run could not save |
| Oct 28 16:00–21:35 | Wed 12:00 PM–5:35 PM | 68 | run could not save |
| Oct 29 03:25–09:00 | Wed 11:25 PM–Thu 5:00 AM | 68 | run could not save |
| Oct 29 14:50–15:55 | Thu 10:50 AM–11:55 AM | 14 | no run started |
| Oct 29 21:45–Oct 30 03:20 | Thu 5:45 PM–11:20 PM | 68 | run could not save |
| Oct 30 09:10–13:30 | Fri 5:10 AM–9:30 AM | 53 | run could not save |

Other notes:
- On Oct 26, `buses.csv` starts at 17:52 UTC; the other files start at 18:09, when they were added.
- The Oct 30 13:35:36 UTC poll comes from a local test run of the same script, not from GitHub Actions.
