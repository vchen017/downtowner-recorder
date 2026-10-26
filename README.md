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
