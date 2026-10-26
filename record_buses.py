#!/usr/bin/env python3
"""Poll the Yale Downtowner live feeds every 5 minutes and record them.

Endpoints (found in the /routes page's JS bundle), all under
https://yale.downtownerapp.com :
  routes_buses.php                 live bus positions
  routes_routes.php?inactive=true  routes, incl. whether each is active now
  routes_eta.php?stop=<id>         predicted arrivals at one stop
  routes_announcements.php         service announcements
  routes_stops.php                 stop list (reference)

Usage:
  python3 record_buses.py            poll forever, every 5 minutes
  python3 record_buses.py --once     poll once and exit (used by the GitHub Actions job)
Environment:
  RECORDER_DAILY=1   write CSVs to data/<UTC date>/ instead of data/
  RECORDER_RAW=0     don't save raw JSON responses

Outputs (next to this script), one row per item per poll:
  data/buses.csv          bus positions
  data/etas.csv           predicted arrivals at every stop on an active route
  data/route_status.csv   active flag for every route
  data/announcements.csv  announcements in effect
  data/raw/<time>.json    raw responses of every poll
  data/routes.json, data/stops.json   reference data, refreshed each poll
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://yale.downtownerapp.com"
INTERVAL = 5 * 60
ETA_WORKERS = 4
OUT = Path(__file__).resolve().parent / "data"
RAW = OUT / "raw"
DAILY = os.environ.get("RECORDER_DAILY") == "1"
SAVE_RAW = os.environ.get("RECORDER_RAW", "1") != "0"

TABLES = {
    "buses.csv": ["polled_at_utc", "bus_id", "bus_name", "route_id", "route_name",
                  "lat", "lon", "heading", "last_stop_id", "last_stop_name", "last_update_utc"],
    "etas.csv": ["polled_at_utc", "stop_id", "stop_name", "route_id", "route_name",
                 "bus_id", "bus_name", "eta_minutes", "calculation_time_utc"],
    "route_status.csv": ["polled_at_utc", "route_id", "route_name", "short_name",
                         "description", "active", "num_stops"],
    "announcements.csv": ["polled_at_utc", "announcement_id", "title", "message",
                          "button_text", "button_url"],
}


def get(path, params=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds") if ts else ""


def append(name, rows, now):
    folder = OUT / f"{now:%Y-%m-%d}" if DAILY else OUT
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    new_file = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, TABLES[name])
        if new_file:
            w.writeheader()
        w.writerows(rows)


def fetch_eta(stop_id):
    try:
        return stop_id, get("/routes_eta.php", {"stop": stop_id})
    except Exception as e:
        return stop_id, {"error": repr(e)}


def poll(stamp, now):
    raw = {}
    log = []

    # Routes and stops first: names for the other tables, and which stops need ETAs.
    routes = raw["routes"] = get("/routes_routes.php", {"inactive": "true"})
    stops = raw["stops"] = get("/routes_stops.php")
    (OUT / "routes.json").write_text(json.dumps(routes))
    (OUT / "stops.json").write_text(json.dumps(stops))
    route_names = {r["id"]: r["name"] for r in routes}
    stop_names = {s["id"]: s["name"] for s in stops}
    append("route_status.csv", [{
        "polled_at_utc": stamp, "route_id": r["id"], "route_name": r["name"],
        "short_name": r.get("short_name"), "description": r.get("description"),
        "active": r.get("active"), "num_stops": len(r.get("stops") or []),
    } for r in routes], now)
    log.append(f"{sum(bool(r.get('active')) for r in routes)} active routes")

    buses = raw["buses"] = get("/routes_buses.php")
    append("buses.csv", [{
        "polled_at_utc": stamp, "bus_id": b.get("id"), "bus_name": b.get("name"),
        "route_id": b.get("route"), "route_name": route_names.get(b.get("route"), ""),
        "lat": b.get("lat"), "lon": b.get("lon"), "heading": b.get("heading"),
        "last_stop_id": b.get("lastStop"), "last_stop_name": stop_names.get(b.get("lastStop"), ""),
        "last_update_utc": iso(b.get("lastUpdate")),
    } for b in buses], now)
    log.append(f"{len(buses)} buses")

    anns = raw["announcements"] = get("/routes_announcements.php") or []
    append("announcements.csv", [{
        "polled_at_utc": stamp, "announcement_id": a.get("id"), "title": a.get("title"),
        "message": a.get("message"), "button_text": a.get("button_text"),
        "button_url": a.get("button_url"),
    } for a in anns], now)
    log.append(f"{len(anns)} announcements")

    active_stops = sorted({s for r in routes if r.get("active") for s in r.get("stops") or []})
    with ThreadPoolExecutor(ETA_WORKERS) as ex:
        etas = dict(ex.map(fetch_eta, active_stops))
    raw["etas"] = {str(k): v for k, v in etas.items()}
    rows, failed = [], 0
    for stop_id, resp in etas.items():
        if "error" in resp:
            failed += 1
            continue
        calc = iso(resp.get("calculation_time"))
        for entry in (resp.get("etas") or {}).values():
            for e in entry.get("etas") or []:
                rows.append({
                    "polled_at_utc": stamp, "stop_id": stop_id,
                    "stop_name": stop_names.get(stop_id, ""), "route_id": e.get("route"),
                    "route_name": route_names.get(e.get("route"), ""), "bus_id": e.get("bus_id"),
                    "bus_name": e.get("bus_name"), "eta_minutes": e.get("avg"),
                    "calculation_time_utc": calc,
                })
    append("etas.csv", rows, now)
    log.append(f"{len(rows)} ETAs from {len(active_stops) - failed}/{len(active_stops)} stops")

    if SAVE_RAW:
        del raw["routes"], raw["stops"]  # already saved as routes.json / stops.json
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / f"{now:%Y%m%dT%H%M%SZ}.json").write_text(json.dumps(raw))
    return ", ".join(log)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    once = "--once" in sys.argv
    while True:
        now = datetime.now(timezone.utc)
        stamp = now.isoformat(timespec="seconds")
        try:
            print(f"{stamp} recorded {poll(stamp, now)}", flush=True)
        except Exception as e:
            print(f"{stamp} ERROR {e!r}", flush=True)
            if once:
                sys.exit(1)
        if once:
            return
        time.sleep(INTERVAL - (time.time() % INTERVAL))  # align to 5-minute marks


if __name__ == "__main__":
    main()
